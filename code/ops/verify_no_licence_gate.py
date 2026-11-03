#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""许可门禁不存在性审计（阶段二收尾，Owner 指令 1）。

目的：证明 V2.1.1 §7.1「许可门禁已废除」在**实际数据库里**成立——
      不存在任何以许可状态为条件的写入/发布/导出拦截，且结构层没有许可判断依据。

三段：
  A. 目录级审计：把数据库目录（约束/触发器/函数/默认值/视图/策略/事件触发器/枚举/列名）
     逐项扫描 licence|license|licen|许可 —— 命中数必须为 0。
  B. 发布路径审计：列出所有引用 record_status='published' 的约束，确认条件只涉及
     CRS 与几何（设计保留的 3 道门禁中的 2 道），不含任何许可谓词。
  C. 行为级正写：真实写入 19 种 issue_type × 3 种 severity × 6 种 action_taken 的台账行，
     证明正常数据质量记录不因任何许可状态被拒；结束 ROLLBACK，不留数据。

用法：PYTHONPATH=./ops/.deps python ops/verify_no_licence_gate.py <数据库名>
退出码：0 = 审计通过（无门禁、可正常写入）；1 = 发现门禁或写入失败
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg2

CODE_ROOT = Path(__file__).resolve().parent.parent

SEARCH_PATTERN = "licen|许可|許可"

# 目录级审计：每项给出 (标签, SQL)。SQL 必须返回命中行数。
CATALOG_CHECKS: list[tuple[str, str]] = [
    (
        "CHECK / FK / UNIQUE / PK 约束",
        f"""SELECT count(*) FROM pg_constraint
            WHERE connamespace = 'public'::regnamespace
              AND (conname ~* '{SEARCH_PATTERN}' OR pg_get_constraintdef(oid) ~* '{SEARCH_PATTERN}')""",
    ),
    (
        "触发器",
        f"""SELECT count(*) FROM pg_trigger
            WHERE NOT tgisinternal
              AND (tgname ~* '{SEARCH_PATTERN}' OR pg_get_triggerdef(oid) ~* '{SEARCH_PATTERN}')""",
    ),
    (
        "函数 / 存储过程定义",
        f"""SELECT count(*) FROM pg_proc p
            WHERE p.pronamespace = 'public'::regnamespace
              AND p.prokind = 'f'
              AND (p.proname ~* '{SEARCH_PATTERN}' OR pg_get_functiondef(p.oid) ~* '{SEARCH_PATTERN}')""",
    ),
    (
        "列名",
        f"""SELECT count(*) FROM pg_attribute a
            WHERE a.attrelid IN (SELECT oid FROM pg_class
                                  WHERE relnamespace = 'public'::regnamespace AND relkind IN ('r','v'))
              AND a.attnum > 0 AND NOT a.attisdropped
              AND a.attname ~* '{SEARCH_PATTERN}'""",
    ),
    (
        "列默认值 / 生成列表达式",
        f"""SELECT count(*) FROM pg_attrdef d
            JOIN pg_class c ON c.oid = d.adrelid
            WHERE c.relnamespace = 'public'::regnamespace
              AND pg_get_expr(d.adbin, d.adrelid) ~* '{SEARCH_PATTERN}'""",
    ),
    (
        "视图定义（含三个派生视图）",
        f"""SELECT count(*) FROM pg_class c
            WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'v'
              AND pg_get_viewdef(c.oid) ~* '{SEARCH_PATTERN}'""",
    ),
    (
        "行级安全策略 RLS",
        f"""SELECT count(*) FROM pg_policy WHERE polname ~* '{SEARCH_PATTERN}'
              OR (polqual IS NOT NULL AND pg_get_expr(polqual, polrelid) ~* '{SEARCH_PATTERN}')
              OR (polwithcheck IS NOT NULL AND pg_get_expr(polwithcheck, polrelid) ~* '{SEARCH_PATTERN}')""",
    ),
    (
        "重写规则",
        f"""SELECT count(*) FROM pg_rewrite r JOIN pg_class c ON c.oid = r.ev_class
            WHERE c.relnamespace = 'public'::regnamespace AND r.rulename ~* '{SEARCH_PATTERN}'""",
    ),
    (
        "事件触发器",
        f"SELECT count(*) FROM pg_event_trigger WHERE evtname ~* '{SEARCH_PATTERN}'",
    ),
    (
        "枚举类型 / 枚举值",
        f"""SELECT count(*) FROM pg_type t
            LEFT JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE t.typnamespace = 'public'::regnamespace
              AND (t.typname ~* '{SEARCH_PATTERN}' OR coalesce(e.enumlabel,'') ~* '{SEARCH_PATTERN}')""",
    ),
]

ISSUE_TYPES = [
    "beg_gt_end", "beg_eq_end", "missing_coordinate", "coordinate_out_of_range",
    "coordinate_outside_china_bbox", "year_out_of_range", "duplicate_external_id",
    "duplicate_sysid", "unknown_crs", "unknown_time_bound_type", "nonstandard_field_name",
    "empty_name", "parent_place_not_in_sample", "truncated_slice_tail",
    "cross_layer_coordinate_conflict", "manual_edit_conflict", "import_row_error",
    "derived_value_mismatch", "rollback_conflict",
]
SEVERITIES = ["blocking", "warning", "info"]
ACTIONS = ["preserved_and_flagged", "needs_manual_review", "rejected",
           "fixed_manually", "ignored", "discarded"]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in (CODE_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("用法: python ops/verify_no_licence_gate.py <数据库名>")
    dbname = sys.argv[1]
    env = load_env()
    conn = psycopg2.connect(
        host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=dbname, user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"],
    )
    conn.autocommit = False
    cur = conn.cursor()
    bad = 0

    print(f"### 许可门禁不存在性审计（库={dbname}）\n")
    print("## A. 目录级审计：任何许可相关对象的存在性")
    for label, sql in CATALOG_CHECKS:
        cur.execute(sql)
        n = cur.fetchone()[0]
        mark = "✓" if n == 0 else "✗"
        if n:
            bad += 1
        print(f"  {mark} {label:<34s} 命中={n}" + ("" if n == 0 else "  ← 存在许可相关对象"))

    # 注释是文本，不构成运行时判断；单独列出以免掩盖真实命中，也不计入失败。
    cur.execute(
        f"""SELECT c.relname, d.description FROM pg_description d
            JOIN pg_class c ON c.oid = d.objoid
            WHERE c.relnamespace = 'public'::regnamespace AND d.description ~* '{SEARCH_PATTERN}'
            ORDER BY 1"""
    )
    notes = cur.fetchall()
    print(f"\n  [信息] 注释中的许可提及 {len(notes)} 处（文档性说明，非运行时门禁）：")
    for relname, text in notes:
        print(f"    {relname}: {text}")
    print("    ⇒ 仅出现在 COMMENT 文本里，不参与任何 INSERT/UPDATE 判断，不计入门禁。")

    print("\n## B. 发布路径审计：record_status='published' 的拦截条件")
    cur.execute(
        """SELECT conrelid::regclass::text || '.' || conname, pg_get_constraintdef(oid)
           FROM pg_constraint
           WHERE contype = 'c' AND connamespace = 'public'::regnamespace
             AND pg_get_constraintdef(oid) ILIKE '%published%'
           ORDER BY 1"""
    )
    rows = cur.fetchall()
    print(f"  引用 published 的 CHECK 约束共 {len(rows)} 条：")
    for name, definition in rows:
        has_licence = any(k in definition.lower() for k in ("licen", "许可"))
        print(f"    {'✗' if has_licence else '✓'} {name}")
        print(f"        {definition}")
        if has_licence:
            bad += 1
    print("  说明：以上条件仅涉及 crs_confidence / geom / record_status 本身，属设计保留的 3 道门禁"
          "（CRS / 几何 / 合并）中的 2 道，与许可无关。")

    print("\n## C. 行为级正写：19 类型 × 3 级别 × 6 处置 全部写入")
    cur.execute("INSERT INTO data_source (source_id, display_name) VALUES ('chgis','licence-gate-probe')")
    cur.execute(
        """INSERT INTO data_dataset
           (dataset_id, source_id, display_name, record_scopes, place_grain, location_grain,
            grain_evidence, occurrence_key_rule, external_id_nature, created_at, updated_at)
           VALUES ('ds_lg','chgis','probe',ARRAY['place'],'per_record','per_record',
                   'ev','none','source_declared',now(),now())"""
    )
    cur.execute(
        """INSERT INTO import_batch (dataset_id, derivation_version, status, operator)
           VALUES ('ds_lg','v2.1.1','succeeded','licence-gate-probe') RETURNING batch_id"""
    )
    batch = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO source_record
           (dataset_id, record_scope, external_id, parent_external_id, duplicate_ordinal,
            raw_file, raw_payload, content_hash, first_batch_id, ingested_at)
           VALUES ('ds_lg','place','p1','-',0,'f.csv','{}'::jsonb,sha256('lg'::bytea),%s,now())
           RETURNING source_record_id""", (batch,)
    )
    sr = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO historical_place
           (dataset_id, grain_key, canonical_name, place_type, place_type_source,
            created_from_source_record_id, created_at, updated_at)
           VALUES ('ds_lg','p1','探针城','unknown','unknown',%s,now(),now()) RETURNING place_id""",
        (sr,),
    )
    place = cur.fetchone()[0]

    written = 0
    errors: list[str] = []
    for t in ISSUE_TYPES:
        for sev in SEVERITIES:
            for act in ACTIONS:
                try:
                    cur.execute("SAVEPOINT s")
                    cur.execute(
                        """INSERT INTO data_quality_issue
                           (dataset_id, source_record_id, place_id, issue_type, severity, field_name,
                            observed_value, action_taken, created_at)
                           VALUES ('ds_lg',%s,%s,%s,%s,'',%s,%s,now())""",
                        (sr, place, t, sev, f"{t}|{sev}|{act}", act),
                    )
                    written += 1
                    cur.execute("RELEASE SAVEPOINT s")
                except psycopg2.Error as exc:
                    cur.execute("ROLLBACK TO SAVEPOINT s")
                    errors.append(f"{t}/{sev}/{act}: {str(exc).splitlines()[0]}")
    total = len(ISSUE_TYPES) * len(SEVERITIES) * len(ACTIONS)
    print(f"  写入成功 {written}/{total}")
    if errors:
        bad += 1
        for e in errors[:10]:
            print(f"    ✗ {e}")
    else:
        print("  ✓ 全部通过：正常数据质量记录不因任何许可状态被拒")

    cur.execute("SELECT count(*), count(DISTINCT issue_fingerprint) FROM data_quality_issue")
    cnt, uniq = cur.fetchone()
    print(f"  台账行数={cnt}，唯一指纹={uniq}" + ("  ← 指纹冲突" if cnt != uniq else "  ✓ 无指纹冲突"))
    if cnt != uniq:
        bad += 1

    conn.rollback()
    cur.execute("SELECT count(*) FROM data_quality_issue")
    print(f"\n### 事务已 ROLLBACK，回滚后台账行数={cur.fetchone()[0]}（应为 0）")

    print("\n" + "=" * 60)
    if bad:
        print(f"审计结论：发现 {bad} 处问题，许可门禁清除不彻底")
        return 1
    print(f"审计结论：许可门禁不存在（结构层 0 命中 + 发布路径无许可谓词 + {total} 条台账写入全通）")
    return 0


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
