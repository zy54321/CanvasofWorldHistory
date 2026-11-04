#!/usr/bin/env python
"""M4-5 · 重建 Pleiades 4.1 暂存并做双重可复现核验

做四件事，全部只读地对待 ``data/staging_m4_3``（M4-4a 已验收的产物）：

1. **两次独立构建**：一次到 ``data/staging_m4_5``，一次到系统临时目录；
   七个 CSV 必须逐字节相同，否则"可复现"这句话不成立。
2. **与已验收暂存的差异界定**：只允许地点级时间四列变化，且行数、主键列序
   与其余六张表完全相同。
3. **变更方向核验**：connection 只会把包络拉宽，所以移除它之后每一处变化都
   只能是"变窄"或"变空"，**不允许出现变宽**。
4. **与导入器规则对齐**：调用 :mod:`audit_time_envelope` 的重算逻辑，
   要求新暂存的 57,967 个地点中，地点级时间与"仅 name+location 包络"
   的差异为 0。

用法：
    python ops/m4-5/build_and_verify.py
    python ops/m4-5/build_and_verify.py --json ops/reports/m4-5/build_verify.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

CODE_ROOT = Path(__file__).resolve().parents[2]
BUILDER = CODE_ROOT / "ops" / "m4-4a" / "build_staging_m4_3.py"
ACCEPTED = CODE_ROOT / "data" / "staging_m4_3"
TARGET = CODE_ROOT / "data" / "staging_m4_5"

#: 七张表的固定文件名，顺序即报告中出现的顺序。
TABLES = (
    "historical_places.csv",
    "historical_place_names.csv",
    "historical_place_locations.csv",
    "source_records.csv",
    "data_quality_issues.csv",
    "candidate_matches.csv",
    "data_datasets.csv",
)

#: 允许变化的列：地点级时间的四列。
TIME_COLUMNS = (
    "valid_from_year_astro",
    "valid_to_year_astro",
    "time_bound_type",
    "time_derivation",
)


def sha256(path: Path) -> str:
    """Hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out_dir: Path) -> None:
    """Run the M4-4a builder into ``out_dir`` (fixed timestamp, deterministic)."""
    cmd = [sys.executable, str(BUILDER), "--out-dir", str(out_dir), "--quiet"]
    result = subprocess.run(cmd, cwd=str(CODE_ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"构建失败（exit {result.returncode}）\n{result.stdout}\n{result.stderr}"
        )


def read_rows(path: Path) -> List[Dict[str, str]]:
    """Read a CSV as dicts, preserving order."""
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def diff_places(old_dir: Path, new_dir: Path) -> Dict[str, Any]:
    """Cell-level diff of ``historical_places.csv`` plus byte identity of the rest."""
    header_old, old_rows = (lambda r: (r.fieldnames, list(r)))(
        csv.DictReader(io.open(old_dir / "historical_places.csv", encoding="utf-8-sig", newline=""))
    )
    header_new, new_rows = (lambda r: (r.fieldnames, list(r)))(
        csv.DictReader(io.open(new_dir / "historical_places.csv", encoding="utf-8-sig", newline=""))
    )

    same_header = header_old == header_new
    same_order = len(old_rows) == len(new_rows) and all(
        o["place_id"] == n["place_id"] for o, n in zip(old_rows, new_rows)
    )

    by_field: Counter = Counter()
    by_dataset: Counter = Counter()
    places = set()
    cells: List[Dict[str, Any]] = []
    for old, new in zip(old_rows, new_rows):
        for column in header_old:
            if old[column] == new[column]:
                continue
            by_field[column] += 1
            by_dataset[old["source_dataset"]] += 1
            places.add(old["place_id"])
            cells.append(
                {
                    "place_id": old["place_id"],
                    "source_dataset": old["source_dataset"],
                    "primary_external_id": old["primary_external_id"],
                    "column": column,
                    "before": old[column],
                    "after": new[column],
                }
            )

    def as_int(text: str) -> Optional[int]:
        text = (text or "").strip()
        return int(text) if text else None

    direction = Counter()
    for cell in cells:
        if cell["column"] not in ("valid_from_year_astro", "valid_to_year_astro"):
            continue
        before, after = as_int(cell["before"]), as_int(cell["after"])
        if after is None:
            direction["blanked"] += 1
        elif before is None:
            direction["gained_value"] += 1
        elif cell["column"] == "valid_from_year_astro":
            direction["narrowed" if after > before else "widened"] += 1
        else:
            direction["narrowed" if after < before else "widened"] += 1

    others = {
        name: sha256(old_dir / name) == sha256(new_dir / name)
        for name in TABLES
        if name != "historical_places.csv"
    }

    return {
        "header_unchanged": same_header,
        "row_order_unchanged": same_order,
        "rows_before": len(old_rows),
        "rows_after": len(new_rows),
        "changed_cells": len(cells),
        "changed_places": len(places),
        "changed_by_column": dict(sorted(by_field.items())),
        "changed_by_dataset": dict(sorted(by_dataset.items())),
        "direction": dict(sorted(direction.items())),
        "non_time_columns_changed": [
            column for column in by_field if column not in TIME_COLUMNS
        ],
        "other_tables_byte_identical": others,
        "cells": cells,
    }


def run_audit(staging: Path) -> Dict[str, Any]:
    """Re-run the envelope audit against ``staging`` and return its summary."""
    cmd = [
        sys.executable,
        str(CODE_ROOT / "ops" / "m4-5" / "audit_time_envelope.py"),
        "--staging",
        str(staging),
    ]
    result = subprocess.run(cmd, cwd=str(CODE_ROOT), capture_output=True, text=True)
    # 审计脚本用 exit code 2 表示"存在无法解释的差异"，是判据而不是崩溃
    if result.returncode not in (0, 2):
        raise SystemExit(f"审计执行失败：\n{result.stdout}\n{result.stderr}")
    for line in result.stdout.splitlines():
        if line.startswith("暂存地点"):
            # 形如：暂存地点 57,967；差异 820 条 / 629 个地点
            rows = re.search(r"差异\s*([\d,]+)\s*条", line)
            places = re.search(r"/\s*([\d,]+)\s*个地点", line)
            if not rows or not places:
                raise SystemExit(f"审计汇总行无法解析：{line}")
            return {
                "mismatch_rows": int(rows.group(1).replace(",", "")),
                "mismatch_places": int(places.group(1).replace(",", "")),
                "exit": result.returncode,
                "stdout_tail": result.stdout.strip().splitlines()[-8:],
            }
    raise SystemExit(f"审计输出无法解析：\n{result.stdout}")


def main() -> int:
    parser = argparse.ArgumentParser(description="M4-5 重建暂存并双重核验")
    parser.add_argument("--json", help="核验结果 JSON 输出路径")
    parser.add_argument("--skip-build", action="store_true", help="复用已有 staging_m4_5")
    args = parser.parse_args()

    print("=" * 78)
    print("M4-5 重建与核验")
    print("=" * 78)

    if not args.skip_build:
        print("\n[1/4] 构建 A → data/staging_m4_5 …", flush=True)
        if TARGET.exists():
            shutil.rmtree(TARGET)
        build(TARGET)
        print("[2/4] 构建 B → 临时目录 …", flush=True)
        with tempfile.TemporaryDirectory(prefix="m4_5_build_b_") as tmp:
            other = Path(tmp) / "staging"
            build(other)
            same = {name: sha256(TARGET / name) == sha256(other / name) for name in TABLES}
            reproducible = all(same.values())
            print("      七张表逐字节一致：", "是" if reproducible else "否")
            for name, ok in same.items():
                if not ok:
                    print(f"        DIFF {name}")
    else:
        reproducible = None
        same = {}

    print("\n[3/4] 与已验收暂存 staging_m4_3 的差异界定 …", flush=True)
    diff = diff_places(ACCEPTED, TARGET)
    print(f"      行数 {diff['rows_before']:,} → {diff['rows_after']:,}；"
          f"变化单元格 {diff['changed_cells']:,} / {diff['changed_places']:,} 个地点")
    print(f"      按列：{diff['changed_by_column']}")
    print(f"      方向：{diff['direction']}")
    print(f"      非时间列变化：{diff['non_time_columns_changed'] or '无'}")
    print(f"      其余六张表逐字节相同："
          f"{all(diff['other_tables_byte_identical'].values())}")

    print("\n[4/4] 与导入器规则重算对齐 …", flush=True)
    audit = run_audit(TARGET)
    print(f"      地点级时间与「仅 name+location 包络」的差异："
          f"{audit['mismatch_rows']} 条 / {audit['mismatch_places']} 个地点")

    checks = {
        "reproducible_two_builds": reproducible is None or reproducible,
        "header_unchanged": diff["header_unchanged"],
        "row_order_unchanged": diff["row_order_unchanged"],
        "only_time_columns_changed": not diff["non_time_columns_changed"],
        "other_tables_byte_identical": all(diff["other_tables_byte_identical"].values()),
        "no_envelope_widened": diff["direction"].get("widened", 0) == 0,
        "mismatch_is_zero": audit["mismatch_rows"] == 0,
    }
    ok = all(checks.values())
    print("\n判据：")
    for name, value in checks.items():
        print(f"  {'✓' if value else '✗'} {name}")

    payload = {
        "target": str(TARGET),
        "accepted": str(ACCEPTED),
        "two_builds_identical": same or None,
        "diff": {k: v for k, v in diff.items() if k != "cells"},
        "audit": audit,
        "checks": checks,
        "ok": ok,
    }
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        with io.open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"\n结果 JSON：{out}")

    print("\n" + ("全部通过" if ok else "存在未通过项"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
