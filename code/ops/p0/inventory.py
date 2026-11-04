#!/usr/bin/env python
"""P0 · 全项目数据库只读盘点

对一个 PostgreSQL 实例里的**每一个**非模板数据库做一次结构化盘点，输出 JSON + 控制台摘要。
全程只读：只执行 SELECT / 元数据查询，不建表、不写行、不跑 Migration。

每个库记录：
  1. Flyway 版本、迁移条数与每条的 checksum / success / 执行时间
  2. public 模式下每张表的行数
  3. 关键表的主键范围（单列 bigint PK）与外键孤儿数
  4. 关键表的内容指纹（按 PK 排序，剔除按设计会变的列）
  5. 数据集构成（source_record.dataset_id、historical_place.dataset_id）
  6. 人物/事件/政权三类"非地点"数据的来源性质（created_by / record_status / 时间）

用法：
    python ops/p0/inventory.py --json ops/reports/p0/inventory.json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

CODE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_ROOT / "ops" / ".deps"))
sys.path.insert(0, str(CODE_ROOT / "ops"))

import psycopg2  # noqa: E402

from import_staging import load_env  # noqa: E402

#: 业务表全集（按 M0–M4 的模型顺序）。
BUSINESS_TABLES = [
    "data_source", "data_dataset", "source_record", "import_batch",
    "historical_place", "historical_place_name", "historical_place_location",
    "candidate_match", "data_quality_issue",
    "person", "person_name", "person_place",
    "event", "event_place", "event_person", "person_event_role",
    "historical_polity", "event_polity", "polity_name",
]

#: 指纹口径：剔除"按设计会变"的列（时间戳、批次指针、出现次数、几何单独处理）。
VOLATILE = {
    "created_at", "updated_at", "last_batch_id", "first_batch_id",
    "occurrence_count", "ingested_at",
}

#: (表, 主键列) —— 用于范围统计。
PK_COLUMNS = {
    "historical_place": "place_id",
    "historical_place_name": "name_id",
    "historical_place_location": "location_id",
    "source_record": "source_record_id",
    "candidate_match": "candidate_match_id",
    "data_quality_issue": "issue_type",  # 无自增 PK 时退化为分组计数
    "person": "person_id",
    "event": "event_id",
    "historical_polity": "polity_id",
}

#: 外键孤儿检查： (说明, 子表, 子列, 父表, 父列)
ORPHAN_CHECKS = [
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
    ("事件-政权→政权", "event_polity", "polity_id", "historical_polity", "polity_id"),
]


def connect(dbname: str):
    """Open a read-only connection to ``dbname``."""
    env = load_env()
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=dbname,
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
    )
    conn.set_session(readonly=True)
    return conn


def list_databases() -> List[str]:
    """Every non-template database in the instance."""
    conn = connect("postgres")
    cur = conn.cursor()
    cur.execute(
        "SELECT datname FROM pg_database WHERE datistemplate=false ORDER BY datname"
    )
    names = [r[0] for r in cur.fetchall()]
    conn.close()
    return names


def table_columns(cur, table: str) -> Dict[str, str]:
    """``column_name -> data_type`` for one table (empty dict if absent)."""
    cur.execute(
        """SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s""",
        (table,),
    )
    return dict(cur.fetchall())


def scalar(cur, sql: str, params: Any = None) -> Any:
    """First column of the first row, or ``None``."""
    try:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:  # noqa: BLE001 - 结构缺失时返回 None，不中断整库盘点
        return None


def fingerprint(cur, table: str, columns: Dict[str, str], pk: str) -> Optional[Dict[str, Any]]:
    """Content fingerprint that ignores columns the pipeline legitimately rewrites."""
    keep = [c for c in columns if c not in VOLATILE]
    # 必须把 VOLATILE 列**真正从 JSON 里减掉**；只统计列数是没用的（曾因此误报差异）。
    drop = " - ".join(f"'{c}'" for c in sorted(VOLATILE & set(columns)))
    base = f"(row_to_json(t)::jsonb{(' - ' + drop) if drop else ''}"
    if "geom" in columns:
        base += " - 'geom' || jsonb_build_object('geom_ewkb', encode(ST_AsEWKB(t.geom),'hex'))"
    expr = base + ")::text"
    sql = (
        f"SELECT count(*), encode(sha256(convert_to(coalesce(string_agg(j,'|' ORDER BY id),''),'UTF8')),'hex') "
        f"  FROM (SELECT t.{pk} AS id, {expr} AS j FROM {table} t) q"
    )
    try:
        cur.execute(sql)
        rows, digest = cur.fetchone()
        return {"rows": rows, "sha256": digest, "columns": len(keep)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"[:200]}


def inventory_db(dbname: str) -> Dict[str, Any]:
    """Collect everything the report needs about one database."""
    info: Dict[str, Any] = {"database": dbname}
    conn = connect(dbname)
    cur = conn.cursor()

    # ---- Flyway
    cur.execute(
        """SELECT version, description, checksum, success, installed_on, execution_time
             FROM flyway_schema_history ORDER BY installed_rank"""
    )
    info["flyway"] = [
        {
            "version": v, "description": d, "checksum": c, "success": s,
            "installed_on": str(t), "execution_time_ms": ms,
        }
        for v, d, c, s, t, ms in cur.fetchall()
    ]
    info["flyway_max"] = info["flyway"][-1]["version"] if info["flyway"] else None

    # ---- 表与行数
    cur.execute(
        """SELECT table_name FROM information_schema.tables
            WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name"""
    )
    tables = [r[0] for r in cur.fetchall()]
    info["tables"] = {}
    for t in tables:
        n = scalar(cur, f"SELECT count(*) FROM {t}")
        info["tables"][t] = n

    info["business_tables_present"] = {t: info["tables"].get(t) for t in BUSINESS_TABLES}

    # ---- 主键范围
    info["pk_range"] = {}
    for table, pk in PK_COLUMNS.items():
        cols = table_columns(cur, table)
        if not cols or pk not in cols:
            continue
        if pk == "issue_type":
            continue
        info["pk_range"][table] = {
            "column": pk,
            "min": scalar(cur, f"SELECT min({pk}) FROM {table}"),
            "max": scalar(cur, f"SELECT max({pk}) FROM {table}"),
        }

    # ---- 孤儿
    info["orphans"] = {}
    for label, child, child_col, parent, parent_col in ORPHAN_CHECKS:
        ccols = table_columns(cur, child)
        pcols = table_columns(cur, parent)
        if not ccols or not pcols or child_col not in ccols or parent_col not in pcols:
            continue
        n = scalar(
            cur,
            f"""SELECT count(*) FROM {child} c
                 WHERE c.{child_col} IS NOT NULL
                   AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE p.{parent_col}=c.{child_col})""",
        )
        info["orphans"][label] = n

    # ---- 指纹
    info["fingerprints"] = {}
    for table in ("historical_place", "historical_place_name", "historical_place_location",
                  "source_record", "candidate_match", "event", "person", "historical_polity"):
        cols = table_columns(cur, table)
        pk = PK_COLUMNS.get(table)
        if not cols or not pk or pk not in cols:
            continue
        info["fingerprints"][table] = fingerprint(cur, table, cols, pk)

    # ---- 数据集构成
    if table_columns(cur, "source_record"):
        cur.execute("SELECT dataset_id, count(*) FROM source_record GROUP BY 1 ORDER BY 1")
        info["source_record_by_dataset"] = dict(cur.fetchall())
    if table_columns(cur, "historical_place"):
        cur.execute("SELECT dataset_id, count(*) FROM historical_place GROUP BY 1 ORDER BY 1")
        info["place_by_dataset"] = dict(cur.fetchall())
        cur.execute("SELECT record_status, count(*) FROM historical_place GROUP BY 1")
        info["place_by_status"] = dict(cur.fetchall())
        cur.execute("SELECT created_by, count(*) FROM historical_place GROUP BY 1")
        info["place_by_created_by"] = dict(cur.fetchall())
    if table_columns(cur, "data_quality_issue"):
        cur.execute("SELECT issue_type, count(*) FROM data_quality_issue GROUP BY 1 ORDER BY 2 DESC")
        info["issues_by_type"] = dict(cur.fetchall())
    batch_cols = table_columns(cur, "import_batch")
    if batch_cols:
        # V2 早期批次表用 started_at，V5 之后才有 created_at；两者都不在就只数行
        stamp = next((c for c in ("created_at", "started_at", "started") if c in batch_cols), None)
        if stamp:
            cur.execute(f"SELECT count(*), min({stamp}), max({stamp}) FROM import_batch")
            n, lo, hi = cur.fetchone()
            info["import_batches"] = {"count": n, "first": str(lo), "last": str(hi), "stamp": stamp}
        else:
            info["import_batches"] = {"count": scalar(cur, "SELECT count(*) FROM import_batch")}

    # ---- 非地点数据（人物 / 事件 / 政权）的来源性质
    for table in ("person", "event", "historical_polity"):
        cols = table_columns(cur, table)
        if not cols:
            continue
        cur.execute(f"SELECT count(*) FROM {table}")
        total = cur.fetchone()[0]
        detail: Dict[str, Any] = {"rows": total}
        if "created_by" in cols:
            cur.execute(f"SELECT created_by, count(*) FROM {table} GROUP BY 1 ORDER BY 1")
            detail["by_created_by"] = dict(cur.fetchall())
        if "record_status" in cols:
            cur.execute(f"SELECT record_status, count(*) FROM {table} GROUP BY 1 ORDER BY 1")
            detail["by_status"] = dict(cur.fetchall())
        if total:
            title_col = "title" if table == "event" else "canonical_name"
            if title_col in cols:
                cur.execute(
                    f"SELECT min(created_at), max(created_at) FROM {table}"
                    if "created_at" in cols else "SELECT NULL, NULL"
                )
                lo, hi = cur.fetchone()
                detail["created_range"] = [str(lo), str(hi)]
                cur.execute(f"SELECT {title_col} FROM {table} ORDER BY 1 LIMIT 200")
                detail["titles_sample"] = [r[0] for r in cur.fetchall()]
        info[f"{table}_provenance"] = detail

    # ---- 关联行数（用于"功能是否真的有数据"）
    for table in ("event_place", "event_person", "person_place", "event_polity", "person_name", "polity_name"):
        if table in info["tables"]:
            continue
        info.setdefault("relation_tables_missing", []).append(table)

    conn.close()
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description="P0 全项目数据库盘点（只读）")
    parser.add_argument("--json", default=str(CODE_ROOT / "ops" / "reports" / "p0" / "inventory.json"))
    parser.add_argument("--only", nargs="*", help="只盘点名字里包含这些片段的库")
    args = parser.parse_args()

    names = list_databases()
    if args.only:
        names = [n for n in names if any(k in n for k in args.only)]

    result: Dict[str, Any] = {"databases": []}
    print("=" * 96)
    print(f"{'database':38s} {'flyway':>6s} {'place':>8s} {'name':>8s} {'loc':>8s} {'sr':>8s} {'event':>6s} {'person':>6s} {'polity':>6s}")
    print("=" * 96)
    for dbname in names:
        if dbname == "postgres":
            continue
        try:
            info = inventory_db(dbname)
        except Exception as exc:  # noqa: BLE001
            print(f"{dbname:38s}  ERROR {type(exc).__name__}: {exc}")
            result["databases"].append({"database": dbname, "error": f"{type(exc).__name__}: {exc}"})
            continue
        bt = info["business_tables_present"]
        print(
            f"{dbname:38s} {str(info['flyway_max'] or '-'):>6s} "
            f"{(bt.get('historical_place') or 0):>8,} {(bt.get('historical_place_name') or 0):>8,} "
            f"{(bt.get('historical_place_location') or 0):>8,} {(bt.get('source_record') or 0):>8,} "
            f"{(bt.get('event') or 0):>6,} {(bt.get('person') or 0):>6,} {(bt.get('historical_polity') or 0):>6,}"
        )
        result["databases"].append(info)

    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(f"\n盘点 {len(result['databases'])} 个库 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
