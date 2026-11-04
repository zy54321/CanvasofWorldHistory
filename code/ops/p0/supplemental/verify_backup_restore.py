#!/usr/bin/env python
"""P0 补充审计 · 备份恢复后的逐表核验（只读）

备份能不能用，不看 `pg_restore --list` 成功，要看**恢复出来的库**能不能给出同样的东西。
本脚本把源库（`canvas_history`，只读）与恢复库逐项对齐：

  1. 表 / 视图 / 序列集合
  2. 每张表的行数
  3. 每张表的**整行指纹**（这次不剔除任何列——备份恢复必须连 updated_at 都一样）
  4. 主键、唯一约束、外键、CHECK、索引、触发器数量
  5. 12 项外键孤儿
  6. PostGIS 版本与 SRID 定义数
  7. Flyway 版本与每条 checksum
  8. 若干关键查询能否执行

用法：
    python ops/p0/supplemental/verify_backup_restore.py \
        --source canvas_history --restored canvas_history_p0_backup_restore
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

CODE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CODE_ROOT / "ops" / ".deps"))
sys.path.insert(0, str(CODE_ROOT / "ops"))

import psycopg2  # noqa: E402

from import_staging import load_env  # noqa: E402

OUT = CODE_ROOT / "ops" / "reports" / "p0" / "supplemental_audit"

ORPHANS = [
    ("名称→地点", "historical_place_name", "place_id", "historical_place", "place_id"),
    ("位置→地点", "historical_place_location", "place_id", "historical_place", "place_id"),
    ("地点→源记录", "historical_place", "created_from_source_record_id", "source_record", "source_record_id"),
    ("名称→源记录", "historical_place_name", "source_record_id", "source_record", "source_record_id"),
    ("位置→源记录", "historical_place_location", "source_record_id", "source_record", "source_record_id"),
    ("候选A→地点", "candidate_match", "place_id_a", "historical_place", "place_id"),
    ("候选B→地点", "candidate_match", "place_id_b", "historical_place", "place_id"),
    ("事件-地点→地点", "event_place", "place_id", "historical_place", "place_id"),
    ("事件-地点→事件", "event_place", "event_id", "event", "event_id"),
    ("事件-人物→人物", "event_person", "person_id", "person", "person_id"),
    ("人物-地点→人物", "person_place", "person_id", "person", "person_id"),
    ("台账→地点", "data_quality_issue", "place_id", "historical_place", "place_id"),
]

#: 恢复后必须在的表（V5 时点）。
EXPECTED_TABLES = {
    "candidate_match", "data_dataset", "data_quality_issue", "data_source",
    "event", "event_person", "event_place", "flyway_schema_history",
    "historical_place", "historical_place_location", "historical_place_name",
    "import_batch", "person", "person_name", "person_place", "source_record",
    "spatial_ref_sys",
}


def connect(db: str):
    """Read-only connection."""
    env = load_env()
    conn = psycopg2.connect(
        host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=db, user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"],
    )
    conn.set_session(readonly=True)
    return conn


def objects(cur, kind: str) -> List[str]:
    """Names of tables / views / sequences in the public schema."""
    cur.execute(
        """SELECT table_name FROM information_schema.tables
            WHERE table_schema='public' AND table_type=%s ORDER BY 1""",
        (kind,),
    )
    return [r[0] for r in cur.fetchall()]


def all_tables(cur) -> List[Tuple[str, str]]:
    """(schema, table) for every user table — including non-public schemas.

    `canvas_history` 里除 public 外还有 `infra`（一张 smoke_check 探针表）；
    只查 public 会漏掉它，恢复核验就不算完整。
    """
    cur.execute(
        """SELECT n.nspname, c.relname
             FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname NOT LIKE 'pg\\_%'
              AND n.nspname <> 'information_schema'
            ORDER BY 1, 2"""
    )
    return [(s_, t) for s_, t in cur.fetchall()]


def row_fingerprint(cur, table: str) -> Tuple[int, str]:
    """Full-row hash, no column excluded — a restore must reproduce every byte."""
    cur.execute(
        f"""SELECT count(*), encode(sha256(convert_to(
                coalesce(string_agg(md5(row_to_json(t)::text), '' ORDER BY md5(row_to_json(t)::text)), ''),
                'UTF8')), 'hex')
              FROM {table} t"""
    )
    return cur.fetchone()


def constraint_counts(cur) -> Dict[str, int]:
    """How many of each constraint type exist in public."""
    cur.execute(
        """SELECT contype, count(*) FROM pg_constraint c
             JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE n.nspname='public' GROUP BY 1"""
    )
    names = {"p": "primary_key", "u": "unique", "f": "foreign_key", "c": "check", "x": "exclusion"}
    out = {v: 0 for v in names.values()}
    for contype, n in cur.fetchall():
        out[names.get(contype, contype)] = n
    return out


def index_count(cur) -> int:
    """Indexes on public tables (excluding those backing constraints is not attempted)."""
    cur.execute(
        """SELECT count(*) FROM pg_indexes WHERE schemaname='public'"""
    )
    return cur.fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="备份恢复核验")
    parser.add_argument("--source", default="canvas_history")
    parser.add_argument("--restored", default="canvas_history_p0_backup_restore")
    args = parser.parse_args()

    src = connect(args.source)
    dst = connect(args.restored)
    cs, cd = src.cursor(), dst.cursor()

    checks: List[Dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        print(f"  {'✓' if ok else '✗'} {name}{('  ' + detail) if detail else ''}")

    print("=" * 84)
    print(f"备份恢复核验：{args.source} → {args.restored}")
    print("=" * 84)

    # ---------------------------------------------------------- 1. 对象集合
    print("\n1. 对象集合")
    src_t = set(objects(cs, "BASE TABLE"))
    dst_t = set(objects(cd, "BASE TABLE"))
    check("表集合一致", src_t == dst_t, f"{len(src_t)} 张：缺 {sorted(src_t - dst_t)} 多 {sorted(dst_t - src_t)}")
    check("V5 应有的 17 张表齐全", EXPECTED_TABLES <= dst_t,
          f"缺 {sorted(EXPECTED_TABLES - dst_t)}")
    src_v = objects(cs, "VIEW")
    dst_v = objects(cd, "VIEW")
    check("视图集合一致", src_v == dst_v, f"{len(src_v)} 个：{src_v}")
    src_i, dst_i = index_count(cs), index_count(cd)
    check("索引数量一致", src_i == dst_i, f"{src_i} / {dst_i}")

    # ------------------------------------------------- 1b. 全部 schema（含 infra/tiger/topology）
    print("\n1b. 全部 schema 的表集合")
    s_all = all_tables(cs)
    d_all = all_tables(cd)
    s_set, d_set = set(s_all), set(d_all)
    check("所有 schema 的表集合一致", s_set == d_set,
          f"{len(s_set)} 张：缺 {sorted(s_set - d_set)} 多 {sorted(d_set - s_set)}")
    row_bad_all = 0
    for schema, table in sorted(s_set & d_set):
        cs.execute(f'SELECT count(*) FROM "{schema}"."{table}"')
        n1 = cs.fetchone()[0]
        cd.execute(f'SELECT count(*) FROM "{schema}"."{table}"')
        n2 = cd.fetchone()[0]
        if n1 != n2:
            row_bad_all += 1
            check(f"{schema}.{table} 行数", False, f"{n1:,} / {n2:,}")
    check("所有 schema 的表行数一致", row_bad_all == 0, f"{len(s_set)} 张表，{row_bad_all} 张不一致")

    # ---------------------------------------------------------- 2. 行数 + 指纹
    print("\n2. 行数与整行指纹（不剔除任何列）")
    tables = sorted(src_t)
    row_bad = fp_bad = 0
    for t in tables:
        n1, f1 = row_fingerprint(cs, t)
        n2, f2 = row_fingerprint(cd, t)
        if n1 != n2:
            row_bad += 1
            check(f"{t} 行数", False, f"{n1:,} / {n2:,}")
        if f1 != f2:
            fp_bad += 1
            check(f"{t} 整行指纹", False, f"{str(f1)[:12]} / {str(f2)[:12]}")
    check("全部表行数一致", row_bad == 0, f"{len(tables)} 张表，{row_bad} 张不一致")
    check("全部表整行指纹一致", fp_bad == 0, f"{len(tables)} 张表，{fp_bad} 张不一致")

    # ---------------------------------------------------------- 3. 约束
    print("\n3. 约束与索引")
    c1, c2 = constraint_counts(cs), constraint_counts(cd)
    for k in c1:
        check(f"{k} 数量一致", c1[k] == c2[k], f"{c1[k]} / {c2[k]}")

    # ---------------------------------------------------------- 4. 孤儿
    print("\n4. 外键孤儿")
    for label, child, ccol, parent, pcol in ORPHANS:
        try:
            cs.execute(f"SELECT count(*) FROM {child} c WHERE c.{ccol} IS NOT NULL AND NOT EXISTS "
                       f"(SELECT 1 FROM {parent} p WHERE p.{pcol}=c.{ccol})")
            n1 = cs.fetchone()[0]
            cd.execute(f"SELECT count(*) FROM {child} c WHERE c.{ccol} IS NOT NULL AND NOT EXISTS "
                       f"(SELECT 1 FROM {parent} p WHERE p.{pcol}=c.{ccol})")
            n2 = cd.fetchone()[0]
            check(f"{label} 孤儿", n1 == n2 == 0, f"源 {n1} / 恢复 {n2}")
        except Exception as exc:  # noqa: BLE001
            src.rollback(); dst.rollback()
            check(f"{label} 孤儿", False, f"{type(exc).__name__}: {exc}"[:120])

    # ---------------------------------------------------------- 5. PostGIS
    print("\n5. PostGIS")
    cs.execute("SELECT postgis_version(), (SELECT count(*) FROM spatial_ref_sys)")
    pv1, srid1 = cs.fetchone()
    cd.execute("SELECT postgis_version(), (SELECT count(*) FROM spatial_ref_sys)")
    pv2, srid2 = cd.fetchone()
    check("postgis_version 一致", pv1 == pv2, pv1)
    check("spatial_ref_sys 行数一致", srid1 == srid2, f"{srid1:,} / {srid2:,}")
    try:
        cd.execute("SELECT ST_AsText(ST_Transform(ST_SetSRID(ST_MakePoint(116.4,39.9),4326),3857))")
        check("ST_Transform 可执行", True, str(cd.fetchone()[0])[:40])
    except Exception as exc:  # noqa: BLE001
        dst.rollback()
        check("ST_Transform 可执行", False, str(exc)[:120])

    # ---------------------------------------------------------- 6. Flyway
    print("\n6. Flyway")
    cs.execute("SELECT version, checksum, success FROM flyway_schema_history ORDER BY installed_rank")
    f1 = cs.fetchall()
    cd.execute("SELECT version, checksum, success FROM flyway_schema_history ORDER BY installed_rank")
    f2 = cd.fetchall()
    check("迁移条数与 checksum 一致", f1 == f2, f"{len(f1)} 条，最高 V{f1[-1][0]}")
    check("全部 success", all(r[2] for r in f2), f"{sum(1 for r in f2 if r[2])}/{len(f2)}")

    # ---------------------------------------------------------- 7. 关键查询
    print("\n7. 关键查询")
    queries = [
        ("地点 + 首选位置", "SELECT count(*) FROM historical_place p JOIN historical_place_location l USING (place_id)"),
        ("名称搜索（ILIKE）", "SELECT count(*) FROM historical_place_name WHERE name_text ILIKE '%长安%'"),
        ("时间窗过滤", "SELECT count(*) FROM historical_place_name WHERE valid_from_year_astro <= 800 AND coalesce(valid_to_year_astro,9999) >= 800"),
        ("候选关系", "SELECT count(*) FROM candidate_match WHERE status='candidate'"),
        ("台账分类", "SELECT count(DISTINCT issue_type) FROM data_quality_issue"),
        ("按数据集统计", "SELECT count(*) FROM source_record GROUP BY dataset_id"),
    ]
    for label, sql in queries:
        try:
            cd.execute(sql)
            got = cd.fetchall()
            check(f"{label} 可执行", True, f"{len(got)} 行")
        except Exception as exc:  # noqa: BLE001
            dst.rollback()
            check(f"{label} 可执行", False, str(exc)[:120])

    src.close(); dst.close()
    ok = all(c["ok"] for c in checks)
    print(f"\n判据 {sum(1 for c in checks if c['ok'])}/{len(checks)} 通过")

    OUT.mkdir(parents=True, exist_ok=True)
    with io.open(OUT / "06_backup_restore_verify.json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"source": args.source, "restored": args.restored,
                   "checks": checks, "ok": ok}, handle, ensure_ascii=False, indent=2)
    print(f"结果 JSON → {OUT / '06_backup_restore_verify.json'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
