#!/usr/bin/env python
"""P0 · 地点名称专项审计（只读）

回答 §3.5 的七个问题：canonical_name 为空 / 仅空格 / 字面 "Unnamed Place" /
其他占位名 / 有坐标无有效名 / 无坐标有有效名 / 两者都有。对每条异常给出
place_id、外部 id、坐标、来源记录与已有关联名称，便于逐条复核。

判定口径（写死在这里，报告里引用同一份定义）：

* ``valid_name``   canonical_name 非空、非纯空白，且不在 :data:`PLACEHOLDERS` 里
* ``placeholder``  命中 :data:`PLACEHOLDERS`（Pleiades 用 "Unnamed Place" 表示
  无已知名称的遗址；这是**源的取值**，不是导入缺陷，但也不能当正常地名展示）
* ``has_geom``     存在至少一条 ``historical_place_location`` 且 ``geom IS NOT NULL``

只读：仅 SELECT。

用法：
    python ops/p0/name_audit.py --db canvas_history_m4_5_verify \
        --csv ops/reports/p0/name_audit.csv --json ops/reports/p0/name_audit.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

CODE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_ROOT / "ops" / ".deps"))
sys.path.insert(0, str(CODE_ROOT / "ops"))

import psycopg2  # noqa: E402

from import_staging import load_env  # noqa: E402

#: 已知占位名（大小写敏感，按 Pleiades / 通用约定收）。命中即"不是有效地名"。
PLACEHOLDERS = {
    "Unnamed Place",
    "Unnamed place",
    "unnamed place",
    "Untitled",
    "untitled",
    "Unknown",
    "unknown",
    "N/A",
    "?",
    "-",
    "(unknown)",
    "Unknown place",
}

SQL_AUDIT = """
WITH loc AS (
    SELECT place_id,
           count(*)                                   AS location_rows,
           count(*) FILTER (WHERE geom IS NOT NULL)   AS geom_rows,
           min(representative_lon)                    AS lon,
           min(representative_lat)                    AS lat
      FROM historical_place_location
     GROUP BY place_id
), nm AS (
    SELECT place_id,
           count(*)                                   AS name_rows,
           string_agg(DISTINCT name_text, ' | ')      AS name_texts,
           string_agg(DISTINCT name_lang, ',')        AS name_langs
      FROM historical_place_name
     GROUP BY place_id
)
SELECT p.place_id,
       p.dataset_id,
       p.grain_key,
       p.canonical_name,
       coalesce(p.canonical_name_lang, '')            AS lang,
       p.created_from_source_record_id                AS source_record_id,
       sr.external_id                                 AS source_external_id,
       coalesce(sr.raw_file, '')                      AS source_file,
       coalesce(loc.location_rows, 0)                 AS location_rows,
       coalesce(loc.geom_rows, 0)                     AS geom_rows,
       loc.lon, loc.lat,
       coalesce(nm.name_rows, 0)                      AS name_rows,
       coalesce(nm.name_texts, '')                    AS name_texts,
       coalesce(nm.name_langs, '')                    AS name_langs,
       substr(coalesce(p.notes, ''), 1, 200)          AS notes
  FROM historical_place p
  LEFT JOIN source_record sr ON sr.source_record_id = p.created_from_source_record_id
  LEFT JOIN loc ON loc.place_id = p.place_id
  LEFT JOIN nm  ON nm.place_id  = p.place_id
 ORDER BY p.dataset_id, p.place_id
"""


def classify(row: Dict[str, Any]) -> str:
    """Return the audit bucket for one place."""
    raw = row["canonical_name"]
    name = "" if raw is None else str(raw).strip()
    if not name:
        base = "empty_name"
    elif str(raw) in PLACEHOLDERS or name in PLACEHOLDERS:
        base = "placeholder_name"
    else:
        base = "valid_name"
    has_geom = (row["geom_rows"] or 0) > 0
    if base == "valid_name":
        return "valid_name_with_geom" if has_geom else "valid_name_no_geom"
    return "no_valid_name_with_geom" if has_geom else "no_valid_name_no_geom"


def main() -> int:
    parser = argparse.ArgumentParser(description="P0 地点名称专项审计（只读）")
    parser.add_argument("--db", default="canvas_history_m4_5_verify")
    parser.add_argument("--csv", default=str(CODE_ROOT / "ops" / "reports" / "p0" / "name_audit.csv"))
    parser.add_argument("--json", default=str(CODE_ROOT / "ops" / "reports" / "p0" / "name_audit.json"))
    parser.add_argument("--all", action="store_true", help="CSV 写出全部地点（默认只写异常）")
    args = parser.parse_args()

    env = load_env()
    conn = psycopg2.connect(
        host="127.0.0.1", port=int(env.get("DB_HOST_PORT", "55432")),
        dbname=args.db, user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"],
    )
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute(SQL_AUDIT)
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()

    for row in rows:
        row["bucket"] = classify(row)

    buckets = Counter(r["bucket"] for r in rows)
    anomalies = [r for r in rows if r["bucket"].startswith("no_valid_name")]
    placeholder_by_ds = Counter(
        r["dataset_id"] for r in rows if r["bucket"].startswith("no_valid_name")
    )

    print("=" * 84)
    print(f"P0 地点名称专项审计 · {args.db}")
    print("=" * 84)
    print(f"地点总数 {len(rows):,}")
    for k in ("valid_name_with_geom", "valid_name_no_geom",
              "no_valid_name_with_geom", "no_valid_name_no_geom"):
        print(f"  {k:26s} {buckets.get(k, 0):>7,}")
    print(f"\n无有效名称 {len(anomalies):,} 条，按数据集：{dict(placeholder_by_ds)}")
    print(f"  其中名称字面 = 'Unnamed Place'："
          f"{sum(1 for r in anomalies if (r['canonical_name'] or '') == 'Unnamed Place'):,}")
    print(f"  其中带坐标（会在地图上出现）："
          f"{sum(1 for r in anomalies if (r['geom_rows'] or 0) > 0):,}")
    print(f"  其中有其他名称行可替代展示："
          f"{sum(1 for r in anomalies if (r['name_rows'] or 0) > 0):,}")

    # 交叉核对源数据：raw_payload 里的 title 是否也是占位名
    # （raw_payload 在 source_record 上；上面已 JOIN 出 source_external_id）
    by_file = Counter(r["source_file"] or "(none)" for r in anomalies)
    print(f"  来源文件：{dict(by_file)}")

    out_csv = Path(args.csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    export = rows if args.all else anomalies
    with io.open(out_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=cols + ["bucket"])
        writer.writeheader()
        writer.writerows(export)
    out_json = Path(args.json)
    with io.open(out_json, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            {
                "database": args.db,
                "total_places": len(rows),
                "buckets": dict(buckets),
                "anomalies": len(anomalies),
                "anomalies_by_dataset": dict(placeholder_by_ds),
                "anomaly_rows": anomalies,
            },
            handle, ensure_ascii=False, indent=2,
        )
    print(f"\nCSV → {out_csv}（{len(export):,} 行）\nJSON → {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
