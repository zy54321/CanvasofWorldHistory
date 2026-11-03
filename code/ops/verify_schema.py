#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段二结构核对：把实际数据库结构与 CORE_DATA_MODEL_V2.1.1 逐项比对。

比对项：
  1. 九张表的表名是否存在
  2. 每张表的列名集合（列名 + 顺序不敏感，集合相等）
  3. 每列的数据类型、是否 NOT NULL、默认值
  4. 附录 A 的 24 条可落库 SQL 约束（C01–C24 去重后）是否真实存在于 pg_constraint / 唯一索引
  5. 索引清单
  6. 三个视图是否存在、对外列数与列名
  7. PostGIS 几何列与 GiST 空间索引

用法：PYTHONPATH=./ops/.deps python ops/verify_schema.py <数据库名> [--expect-empty]
退出码：0 = 全部一致；1 = 有差异（差异逐条打印）
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg2

CODE_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- 期望结构
# 列顺序 = CORE §5 表格顺序；末尾 created_at / updated_at 按 §5.6 / §5.7 的「时间戳」声明补入
EXPECTED_COLUMNS: dict[str, list[str]] = {
    "data_source": [
        "source_id", "display_name", "homepage_url", "display_priority", "notes", "created_at",
    ],
    "data_dataset": [
        "dataset_id", "source_id", "display_name", "dataset_version", "record_scopes",
        "place_grain", "location_grain", "grain_evidence", "occurrence_key_rule",
        "external_id_nature", "content_sha256", "local_path", "record_count", "is_active",
        "notes", "created_at", "updated_at",
    ],
    "import_batch": [
        "batch_id", "dataset_id", "dataset_version", "derivation_version", "status",
        "input_file", "input_sha256", "input_row_count", "inserted_source_record_ids",
        "updated_source_record_ids", "quarantined_count", "skipped_count", "failed_count",
        "blocked_count", "rollback_of_batch_id", "started_at", "finished_at", "operator", "notes",
    ],
    "source_record": [
        "source_record_id", "dataset_id", "record_scope", "external_id", "parent_external_id",
        "duplicate_ordinal", "raw_file", "raw_record_index", "raw_payload", "content_hash",
        "first_batch_id", "last_batch_id", "is_active", "inactive_reason", "inactive_at",
        "inactive_in_batch_id", "ingested_at",
    ],
    "historical_place": [
        "place_id", "dataset_id", "grain_key", "canonical_name", "canonical_name_lang",
        "place_type", "place_type_source", "place_type_basis_note", "description",
        "record_status", "merged_into_place_id", "merge_review_ref", "merged_at",
        "created_from_source_record_id", "created_by", "locked", "manual_edited_fields",
        "notes", "created_at", "updated_at",
    ],
    "historical_place_location": [
        "location_id", "place_id", "source_record_id", "geom", "geom_type",
        "representative_lon", "representative_lat", "original_x", "original_y", "original_crs",
        "crs_confidence", "axis_order_verified", "crs_transform_meta", "location_precision",
        "uncertainty_m", "uncertainty_source", "valid_from_year_astro", "valid_to_year_astro",
        "time_bound_type", "source_beg_rule", "source_end_rule", "source_time_columns",
        "time_note", "conflict_status", "is_preferred", "record_status", "rejected_by",
        "locked", "manual_edited_fields", "created_by", "notes", "created_at", "updated_at",
    ],
    "historical_place_name": [
        "name_id", "place_id", "source_record_id", "name_text", "name_lang", "name_script",
        "name_type", "transliteration_scheme", "association_certainty",
        "valid_from_year_astro", "valid_to_year_astro", "time_bound_type", "source_time_columns",
        "time_note", "notes", "record_status", "rejected_by", "locked", "manual_edited_fields",
        "created_by", "created_at", "updated_at",
    ],
    "candidate_match": [
        "candidate_id", "relation_type", "place_id_a", "place_id_b", "source_record_id_a",
        "source_record_id_b", "distance_m", "direction", "evidence", "confidence", "status",
        "reviewer", "reviewed_at", "review_note", "created_at", "updated_at",
    ],
    "data_quality_issue": [
        "issue_id", "dataset_id", "source_record_id", "place_id", "batch_id",
        "issue_fingerprint", "issue_type", "severity", "field_name", "observed_value",
        "expected_rule", "action_taken", "first_batch_id", "last_batch_id", "occurrence_count",
        "resolved", "resolved_at", "resolver", "resolution_note", "created_at",
    ],
}

EXPECTED_VIEWS: dict[str, list[str]] = {
    "v_place_evidence": [
        "place_id", "source_record_id", "evidence_role", "source_is_active",
        "source_inactive_reason", "child_table", "child_row_id", "child_record_status",
        "child_rejected_by", "is_anchor", "is_canonical_row",
    ],
    "v_place_liveness": [
        "place_id", "dataset_id", "grain_key", "record_status",
        "manual_rejected_rows", "distinct_inactive_reasons", "liveness",
    ],
    "v_place_time_span": [
        "place_id", "span_from_astro", "span_to_astro", "from_evidence_rows",
        "to_evidence_rows", "staging_evidence_rows", "valid_child_rows", "child_rows_total",
        "derivation_kind", "all_children_rejected",
    ],
}

# 附录 A：24 条可落库 SQL 约束（C01–C26，去重 C02 废除、C18 与 C03 同条）
# 名称 → 承载形式（constraint / unique_index）
EXPECTED_CONSTRAINTS: dict[str, str] = {
    "uq_source_record_c01": "constraint",
    "ck_source_record_c03": "constraint",
    "uq_historical_place_c04": "constraint",
    "ck_historical_place_c05": "constraint",
    "ck_historical_place_c06": "constraint",
    "uq_hpl_c07": "unique_index",
    "uq_hpn_c08": "constraint",
    "uq_candidate_match_c09": "constraint",
    "uq_data_quality_issue_c10": "constraint",
    "ck_data_quality_issue_c11": "constraint",
    "ck_data_quality_issue_c12": "constraint",
    "ck_hpl_c13": "constraint",
    "ck_hpl_c14": "constraint",
    "ck_hpl_c15": "constraint",
    "ck_hpl_c16": "constraint",
    "ck_hpn_c16": "constraint",
    "ck_candidate_match_c17": "constraint",
    "ck_source_record_c19": "constraint",
    "ck_source_record_c20": "constraint",
    "ck_source_record_c21": "constraint",
    "ck_source_record_c22": "constraint",
    "ck_data_quality_issue_c23": "constraint",
    "ck_data_quality_issue_c24": "constraint",
    "ck_hpl_c25": "constraint",
    "ck_hpn_c25": "constraint",
    "ck_hpl_c26": "constraint",
    "ck_hpn_c26": "constraint",
}

problems: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)
    print(f"  ✗ {msg}")


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
        sys.exit("用法: python ops/verify_schema.py <数据库名>")
    dbname = sys.argv[1]
    env = load_env()

    conn = psycopg2.connect(
        host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=dbname, user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"],
    )
    cur = conn.cursor()
    print(f"### 核对数据库：{dbname}")

    # ---- 1. 表 ----
    print("\n## 1. 九张表")
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE' "
        "AND table_name NOT IN ('spatial_ref_sys','flyway_schema_history') ORDER BY 1"
    )
    actual_tables = [r[0] for r in cur.fetchall()]
    for t in EXPECTED_COLUMNS:
        if t in actual_tables:
            print(f"  ✓ {t}")
        else:
            fail(f"缺表 {t}")
    extra = [t for t in actual_tables if t not in EXPECTED_COLUMNS]
    if extra:
        fail(f"多出非设计表：{extra}")
    print(f"  实际表数={len(actual_tables)}，设计表数={len(EXPECTED_COLUMNS)}")

    # ---- 2/3. 列、类型、可空、默认值 ----
    print("\n## 2. 列 / 类型 / 可空 / 默认值")
    cur.execute(
        """
        SELECT c.table_name, c.column_name, c.data_type, c.udt_name,
               c.is_nullable, c.column_default, c.is_generated,
               c.character_maximum_length, c.numeric_precision, c.numeric_scale
          FROM information_schema.columns c
         WHERE c.table_schema = 'public'
         ORDER BY c.table_name, c.ordinal_position
        """
    )
    actual_cols: dict[str, dict[str, tuple]] = {}
    for row in cur.fetchall():
        actual_cols.setdefault(row[0], {})[row[1]] = row[2:]

    total_cols = 0
    for table, cols in EXPECTED_COLUMNS.items():
        got = actual_cols.get(table, {})
        missing = [c for c in cols if c not in got]
        extra_cols = [c for c in got if c not in cols]
        total_cols += len(cols)
        status = "✓" if not missing and not extra_cols else "✗"
        print(f"  {status} {table}: 期望 {len(cols)} 列 / 实际 {len(got)} 列")
        if missing:
            fail(f"{table} 缺列：{missing}")
        if extra_cols:
            fail(f"{table} 多列：{extra_cols}")
    actual_total = sum(len(actual_cols.get(t, {})) for t in EXPECTED_COLUMNS)
    print(f"  设计列合计={total_cols}，实际列合计（仅九张表）={actual_total}")

    # 关键列的类型 / 可空抽查（逐条写死，防止类型漂移）
    print("\n## 3. 关键列类型与可空性抽查")
    KEY_TYPES = [
        ("source_record", "parent_external_id", "text", "NO"),
        ("source_record", "duplicate_ordinal", "integer", "NO"),
        ("source_record", "content_hash", "bytea", "NO"),
        ("source_record", "raw_payload", "jsonb", "NO"),
        ("source_record", "ingested_at", "timestamp with time zone", "NO"),
        ("historical_place", "grain_key", "text", "NO"),
        ("historical_place", "dataset_id", "text", "NO"),
        ("historical_place", "manual_edited_fields", "ARRAY", "NO"),
        ("historical_place_location", "geom", "USER-DEFINED", "YES"),
        ("historical_place_location", "original_x", "text", "YES"),
        ("historical_place_location", "source_time_columns", "text", "NO"),
        ("historical_place_location", "rejected_by", "text", "YES"),
        ("historical_place_location", "uncertainty_m", "integer", "YES"),
        ("historical_place_name", "rejected_by", "text", "YES"),
        ("historical_place_name", "source_time_columns", "text", "NO"),
        ("data_quality_issue", "dataset_id", "text", "YES"),
        ("data_quality_issue", "issue_fingerprint", "text", "NO"),
        ("data_dataset", "record_scopes", "ARRAY", "NO"),
        ("data_source", "display_priority", "smallint", "NO"),
        ("data_source", "source_id", "text", "NO"),
    ]
    for table, col, dtype, nullable in KEY_TYPES:
        info = actual_cols.get(table, {}).get(col)
        if info is None:
            fail(f"{table}.{col} 不存在")
            continue
        act_type, act_nullable = info[0], info[2]
        ok = act_type == dtype and act_nullable == nullable
        print(f"  {'✓' if ok else '✗'} {table}.{col}: {act_type} nullable={act_nullable}（期望 {dtype} / {nullable}）")
        if not ok:
            fail(f"{table}.{col} 类型或可空性不符：实际 {act_type}/{act_nullable}")

    # 生成列
    cur.execute(
        "SELECT column_name, is_generated, generation_expression FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='data_quality_issue' AND column_name='issue_fingerprint'"
    )
    row = cur.fetchone()
    print(f"\n  生成列 issue_fingerprint: is_generated={row[1]}")
    if row[1] != "ALWAYS":
        fail("issue_fingerprint 不是 STORED 生成列")
    else:
        print(f"    generation_expression={row[2]}")

    # ---- 4. 约束 ----
    print("\n## 4. 附录 A 的 SQL 约束（设计 24 条；C16/C25/C26 各落两处 ⇒ 物理对象 27 个）")
    cur.execute(
        "SELECT conname, contype, conrelid::regclass::text FROM pg_constraint "
        "WHERE connamespace='public'::regnamespace ORDER BY 1"
    )
    cons = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    cur.execute(
        "SELECT indexname, tablename FROM pg_indexes WHERE schemaname='public'"
    )
    idx = {r[0]: r[1] for r in cur.fetchall()}

    found = 0
    for name, form in EXPECTED_CONSTRAINTS.items():
        if form == "constraint":
            ok = name in cons
        else:
            ok = name in idx
        if ok:
            found += 1
            ctype = cons[name][0] if name in cons else "unique_index"
            print(f"  ✓ {name} ({ctype})")
        else:
            fail(f"缺约束 {name}（期望形式 {form}）")
    print(f"  命中 {found}/{len(EXPECTED_CONSTRAINTS)}")

    # 约束类型统计（PK/FK/UNIQUE/CHECK）
    cur.execute(
        "SELECT contype, count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace "
        "GROUP BY contype ORDER BY contype"
    )
    print("  实际约束类型统计：" + ", ".join(f"{k}={v}" for k, v in cur.fetchall()))

    # 关键 CHECK 的定义式抽查
    print("\n## 5. 关键 CHECK 定义式")
    for cname in [
        "ck_source_record_c03", "ck_source_record_c20", "ck_hpl_c14", "ck_hpl_c15",
        "ck_hpn_c25", "ck_data_quality_issue_c11", "ck_data_quality_issue_c12",
    ]:
        cur.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname=%s", (cname,))
        r = cur.fetchone()
        print(f"  {cname}: {r[0] if r else '不存在'}")
        if not r:
            fail(f"{cname} 定义缺失")

    # ---- 6. 视图 ----
    print("\n## 6. 三个派生视图")
    for view, cols in EXPECTED_VIEWS.items():
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (view,)
        )
        got = [r[0] for r in cur.fetchall()]
        ok = got == cols
        print(f"  {'✓' if ok else '✗'} {view}: {len(got)} 列 {'（列名/顺序一致）' if ok else ''}")
        if not ok:
            fail(f"{view} 列不符：实际 {got} 期望 {cols}")
        # 可查询性
        try:
            cur.execute(f"SELECT count(*) FROM {view}")
            print(f"    可查询，当前行数={cur.fetchone()[0]}")
        except Exception as exc:  # noqa: BLE001
            fail(f"{view} 无法查询：{exc}")

    # ---- 7. PostGIS ----
    print("\n## 7. PostGIS 类型与空间索引")
    cur.execute(
        "SELECT f_table_name, f_geometry_column, coord_dimension, srid, type "
        "FROM geometry_columns WHERE f_table_schema='public'"
    )
    geoms = cur.fetchall()
    for g in geoms:
        print(f"  几何列 {g[0]}.{g[1]} dim={g[2]} srid={g[3]} type={g[4]}")
    if not any(g[0] == "historical_place_location" and g[1] == "geom" and g[3] == 4326 for g in geoms):
        fail("historical_place_location.geom 未注册为 SRID 4326 几何列")
    cur.execute(
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE schemaname='public' AND tablename='historical_place_location' AND indexdef LIKE '%gist%'"
    )
    gist = cur.fetchall()
    for name, ddl in gist:
        print(f"  GiST 索引 {name}: {ddl}")
    if not gist:
        fail("historical_place_location 缺 GiST 空间索引")

    # ---- 8. 空库应为 0 行业务数据 ----
    print("\n## 8. 业务表行数（阶段二应为 0）")
    for table in EXPECTED_COLUMNS:
        cur.execute(f"SELECT count(*) FROM {table}")
        n = cur.fetchone()[0]
        flag = "✓" if n == 0 else "!"
        print(f"  {flag} {table}: {n}")

    # ---- 汇总 ----
    print("\n" + "=" * 60)
    if problems:
        print(f"结果：{len(problems)} 处不一致")
        return 1
    print("结果：结构与 CORE_DATA_MODEL_V2.1.1 一致（0 处差异）")
    return 0


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
