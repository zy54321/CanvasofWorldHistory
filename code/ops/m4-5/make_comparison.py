#!/usr/bin/env python
"""M4-5 · 生成"修复前后 820 条差异对照"

把三份证据拼成一张表，每条差异一行：

* ``before``  修复前暂存（staging_m4_3）的地点级时间值
* ``after``   修复后暂存（staging_m4_5）的地点级时间值
* ``rule``    按导入器规则（仅 name+location 子行包络）重算出的值
* ``driver``  给出旧值的那条 connection 记录（connection id / 类型 / 年份）
* ``effect``  差异方向：narrowed（收窄）/ blanked（清空）

结论列 ``verdict`` 只有两种取值：
* ``fixed``          after == rule，差异消失
* ``still_broken``   after != rule，问题仍在（必须为 0）

用法：
    python ops/m4-5/make_comparison.py
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

CODE_ROOT = Path(__file__).resolve().parents[2]
REPORTS = CODE_ROOT / "ops" / "reports" / "m4-5"
NEW = CODE_ROOT / "data" / "staging_m4_5"
OLD = CODE_ROOT / "data" / "staging_m4_3"


def read_rows(path: Path) -> List[Dict[str, str]]:
    """Read a staging CSV as dicts."""
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def value_of(place: Dict[str, str], field: str) -> str:
    """Read one place-level time cell as text (blank stays blank)."""
    return (place.get(field) or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="M4-5 修复前后对照")
    parser.add_argument("--json", default=str(REPORTS / "mismatch_820_before_after.json"))
    parser.add_argument("--csv", default=str(REPORTS / "mismatch_820_before_after.csv"))
    args = parser.parse_args()

    before = json.load(io.open(REPORTS / "audit_before.json", encoding="utf-8"))
    details: List[Dict[str, Any]] = before["details"]

    new_index = {r["place_id"]: r for r in read_rows(NEW / "historical_places.csv")}
    old_index = {r["place_id"]: r for r in read_rows(OLD / "historical_places.csv")}

    rows: List[Dict[str, Any]] = []
    verdicts = Counter()
    effects = Counter()
    for item in details:
        pid = item["place_id"]
        field = item["field"]
        new_value = value_of(new_index[pid], field)
        rule = item["recomputed_importer"]
        rule_text = "" if rule is None else str(rule)
        driver = item["driver"] or {}
        effect = "blanked" if not new_value else "narrowed"
        verdict = "fixed" if new_value == rule_text else "still_broken"
        verdicts[verdict] += 1
        effects[effect] += 1
        rows.append(
            {
                "place_id": pid,
                "source_dataset": item["source_dataset"],
                "primary_external_id": item["primary_external_id"],
                "canonical_name": item["canonical_name"],
                "field": field,
                "before_staging": item["staged"],
                "after_staging": new_value,
                "rule_value": rule_text,
                "change": effect,
                "driver_kind": driver.get("kind", ""),
                "driver_connection_id": driver.get("connection_id", ""),
                "driver_connection_type": driver.get("connection_type", ""),
                "driver_connects_to": driver.get("connects_to", ""),
                "driver_year_astro": driver.get("value", ""),
                "driver_raw_file": driver.get("raw_file", ""),
                "driver_raw_index": driver.get("raw_record_index", ""),
                "place_time_bound_type_before": old_index[pid]["time_bound_type"],
                "place_time_bound_type_after": new_index[pid]["time_bound_type"],
                "verdict": verdict,
            }
        )

    # 按地点、字段排序，便于逐条比对
    rows.sort(key=lambda r: (r["place_id"], r["field"]))

    out_csv = Path(args.csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with io.open(out_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "rows": len(rows),
        "places": len({r["place_id"] for r in rows}),
        "by_dataset": dict(sorted(Counter(r["source_dataset"] for r in rows).items())),
        "by_field": dict(sorted(Counter(r["field"] for r in rows).items())),
        "by_verdict": dict(sorted(verdicts.items())),
        "by_effect": dict(sorted(effects.items())),
        "driver_kinds": dict(sorted(Counter(r["driver_kind"] for r in rows).items())),
        "still_broken": [r for r in rows if r["verdict"] != "fixed"][:20],
        "csv": str(out_csv),
    }
    with io.open(args.json, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"summary": summary, "rows": rows}, handle, ensure_ascii=False, indent=2)

    print("=" * 78)
    print("M4-5 修复前后对照")
    print("=" * 78)
    print(f"差异 {summary['rows']:,} 条 / {summary['places']:,} 个地点")
    print(f"  按数据集：{summary['by_dataset']}")
    print(f"  按字段：  {summary['by_field']}")
    print(f"  按结论：  {summary['by_verdict']}")
    print(f"  按变化：  {summary['by_effect']}")
    print(f"  驱动记录：{summary['driver_kinds']}")
    print(f"\nCSV → {out_csv}")
    broke = [r for r in rows if r["verdict"] != "fixed"]
    if broke:
        print(f"\n仍未解决 {len(broke)} 条，前 5 条：")
        for r in broke[:5]:
            print(f"  {r['place_id']} {r['field']} after={r['after_staging']!r} rule={r['rule_value']!r}")
    return 0 if not broke else 1


if __name__ == "__main__":
    raise SystemExit(main())
