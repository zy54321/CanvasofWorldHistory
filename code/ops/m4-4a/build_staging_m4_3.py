#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""M4-4a 归一化入口：五个抽取源 → ``code/data/staging_m4_3`` 的七张 CSV。

为什么需要这个入口
------------------
``p0/wb-002-normalize/run_all.py`` 把输出路径写死在
``设计资料/P0收敛/WB-002/normalized``，且只认识四个抽取源（CHGIS / MCGD /
Pleiades 切片 / WHG）。M4-4a 要求把 Pleiades GIS 4.1 全量并入，并且**另存**到
``code/data/staging_m4_3/``、**不覆盖** ``code/data/staging/``。因此这里按现有
流水线的调用顺序重放同一套函数，只换输出目录、只多挂一个抽取源。

没有修改 ``run_all.py``：它的既有输出与语义保持原样，是 M0–M3 已验收路径。
本脚本与 `run_all.run()` 的前七个阶段逐行对应，差异只有三处，都写在
``DIFFERENCES_FROM_RUN_ALL`` 里。

用法
----
    cd code
    python ops/m4-4a/build_staging_m4_3.py                 # 用固定时间戳，可重复
    python ops/m4-4a/build_staging_m4_3.py --timestamp 2026-11-04T00:00:00Z
    python ops/m4-4a/build_staging_m4_3.py --out-dir /tmp/x # 供一致性测试用

输出
----
``<out-dir>/`` 下：
  historical_places.csv / historical_place_names.csv /
  historical_place_locations.csv / source_records.csv /
  data_quality_issues.csv / candidate_matches.csv / data_datasets.csv
  manifest.json      运行清单（输入指纹、输出指纹、行数、来源统计）
  SHA256SUMS.txt     七个 CSV 的 sha256（便于外部核对）
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import platform
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

CODE_ROOT = Path(__file__).resolve().parents[2]
NORMALIZE_DIR = CODE_ROOT / "p0" / "wb-002-normalize"
if str(NORMALIZE_DIR) not in sys.path:
    sys.path.insert(0, str(NORMALIZE_DIR))

from chgis_extract import (  # noqa: E402
    CHGIS_DATASETS,
    citation_from_readme,
    extract_all,
    read_chgis_readme,
)
from chgis_migration import analyse_migrations  # noqa: E402
from csv_io import file_sha256, file_size, write_csv, write_json  # noqa: E402
from mcgd_extract import extract_mcgd  # noqa: E402
from normalize import PIPELINE_VERSION, TABLE_COLUMNS, build_bundle  # noqa: E402
from pleiades_extract import (  # noqa: E402
    PLEIADES_FULL_DIR,
    PLEIADES_SLICE_DIR,
    SLICE_FILES,
    extract_pleiades,
    extract_pleiades_full,
)
from quality_checks import (  # noqa: E402
    detect_field_name_quirks,
    load_date_rule_dictionary,
    verify_astro_conversion,
)
from whg_extract import WHG_PLACE_DIR, extract_whg  # noqa: E402

#: 与 ``run_all.run()`` 的差异，逐条列在这里，便于审查时一眼看清。
DIFFERENCES_FROM_RUN_ALL: Tuple[str, ...] = (
    "输出目录：code/data/staging_m4_3/（run_all 写 设计资料/P0收敛/WB-002/normalized）",
    "多挂第五个抽取源 pleiades_gis_4_1（run_all 只有切片）",
    "不写 issues/*.csv 与 stats.json 的簇/同名分析段：本轮交付物是七张 CSV + manifest",
)

#: 表名 -> 输出文件名。
TABLE_FILES: Dict[str, str] = {
    "historical_places": "historical_places.csv",
    "historical_place_names": "historical_place_names.csv",
    "historical_place_locations": "historical_place_locations.csv",
    "source_records": "source_records.csv",
    "data_quality_issues": "data_quality_issues.csv",
    "candidate_matches": "candidate_matches.csv",
    "data_datasets": "data_datasets.csv",
}

#: 默认时间戳。固定值让两次运行逐字节相同（CSV 里有 ingested_at / created_at）。
DEFAULT_TIMESTAMP = "2026-11-04T00:00:00Z"

#: 与 run_all 一致的回退引用串。
FALLBACK_CHGIS_CITATION = (
    'CHGIS, Version: 6. (c) Fairbank Center for Chinese Studies of Harvard University '
    "and the Center for Historical Geographical Studies at Fudan University, 2016."
)


def utc_now_iso() -> str:
    """Current UTC time as ISO-8601 with a ``Z`` suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def collect_input_paths(project_root: Path, sample_dir: Path) -> List[Path]:
    """Every read-only input whose digest must be identical before and after.

    Same four source families as ``run_all.collect_input_paths`` plus the 19
    files of the v4.1 package.
    """
    paths = [sample_dir / "chgis" / dataset.zip_name for dataset in CHGIS_DATASETS]
    paths.append(sample_dir / "mcgd" / "MCGD_Data2026_08_25.csv.head-960rows.sample.csv")
    paths.append(sample_dir / "mcgd" / "zenodo_record_22094815.json")
    paths.append(sample_dir / "chgis" / "CHGIS_data_dictionary.zip")
    paths.append(sample_dir / "chgis" / "CHGIS_V6_README.txt")
    paths.append(sample_dir / "chgis" / "api" / "dataset_FDLFJ3_EULA.json")

    pleiades_dir = project_root / PLEIADES_SLICE_DIR
    paths.append(pleiades_dir / "FETCH_LOG.tsv")
    paths.extend(pleiades_dir / file_name for _logical, file_name, _kind in SLICE_FILES)

    whg_dir = project_root / WHG_PLACE_DIR
    paths.append(whg_dir / "sources.json")
    paths.extend(sorted((whg_dir / "place").glob("*.json")))

    full_dir = CODE_ROOT / PLEIADES_FULL_DIR
    paths.extend(sorted(p for p in full_dir.iterdir() if p.is_file()))
    return [path for path in paths if path.is_file()]


def hash_paths(paths: Sequence[Path]) -> Dict[str, str]:
    """Hash every path into ``{absolute path: sha256}``."""
    return {str(path): file_sha256(path) for path in paths}


def _digest_of_sorted_ids(values: Sequence[str]) -> str:
    """Stable digest of an id list, so the manifest need not carry 2,552 ids."""
    joined = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()


def _shapely_version() -> str:
    """shapely version used for geometry repair, or ``absent``."""
    try:
        import shapely  # noqa: PLC0415

        return shapely.__version__
    except ImportError:
        return "absent"


def run(project_root: Path, out_dir: Path, timestamp: str, quiet: bool) -> Dict[str, Any]:
    """Build the seven staging tables and write them to ``out_dir``."""
    started_at = utc_now_iso()
    clock = time.perf_counter()

    sample_dir = project_root / "设计资料" / "P0验证" / "WB-002" / "sample_data"
    if not sample_dir.is_dir():
        raise SystemExit(f"sample data directory not found: {sample_dir}")
    full_dir = CODE_ROOT / PLEIADES_FULL_DIR
    if not full_dir.is_dir():
        raise SystemExit(f"Pleiades v4.1 directory not found: {full_dir}")

    def say(message: str = "") -> None:
        if not quiet:
            print(message)

    say(f"M4-4a staging build ({PIPELINE_VERSION})")
    say(f"  project root : {project_root}")
    say(f"  out dir      : {out_dir}")
    say(f"  ingested_at  : {timestamp}")
    say()

    # --- 1. input digests ---------------------------------------------------
    input_paths = collect_input_paths(project_root, sample_dir)
    input_sha_before = hash_paths(input_paths)
    say(f"  [1] hashed {len(input_paths)} read-only inputs")

    # --- 2. CHGIS date rules ------------------------------------------------
    date_rules = load_date_rule_dictionary(sample_dir)
    if not date_rules.loaded:
        raise SystemExit(f"CHGIS date-rule dictionary failed to load: {date_rules.error}")
    say(f"  [2] date rules: {len(date_rules.rules)} entries from {date_rules.source_member}")

    # --- 3. CHGIS -----------------------------------------------------------
    chgis = extract_all(sample_dir, project_root)
    readme = read_chgis_readme(sample_dir)
    chgis_citation = citation_from_readme(readme) or FALLBACK_CHGIS_CITATION
    say(f"  [3] CHGIS records: {len(chgis.records):,}")

    # --- 4. MCGD + Pleiades slice + WHG ------------------------------------
    mcgd = extract_mcgd(sample_dir, project_root)
    say(f"  [4] MCGD rows: {len(mcgd.records):,}")

    pleiades_slice = extract_pleiades(project_root)
    say(
        f"  [5] Pleiades slice records: {len(pleiades_slice.records):,} "
        f"(places={pleiades_slice.stats['record_kinds'].get('places', 0):,})"
    )

    whg = extract_whg(project_root)
    say(f"  [6] WHG records: {len(whg.records):,}")

    # --- 5. Pleiades v4.1 full ---------------------------------------------
    # 重叠集合从**切片抽取结果**现算，不读旧 CSV：切片抽取器是确定性的，
    # 它产出的 2,643 个地点就是库里 pleiades_gis_4_1_slice 的 2,643 个地点。
    slice_place_ids = {
        record.external_id
        for record in pleiades_slice.records
        if record.record_kind == "place"
    }
    v41_all_ids = set()
    with (full_dir / "places.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = (row.get("id") or "").strip()
            if value:
                v41_all_ids.add(value)
    superseded_ids = sorted(v41_all_ids & slice_place_ids)
    new_ids = sorted(v41_all_ids - slice_place_ids)

    # 交叉核对：与既有 code/data/staging 的切片地点集合必须一致
    legacy_csv = CODE_ROOT / "data" / "staging" / "source_records.csv"
    legacy_slice_ids: Optional[set] = None
    if legacy_csv.is_file():
        legacy_slice_ids = set()
        with legacy_csv.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if (
                    row.get("dataset_id") == "pleiades_gis_4_1_slice"
                    and row.get("external_id_type") == "pleiades_place_id"
                ):
                    legacy_slice_ids.add((row.get("external_id") or "").strip())
        if legacy_slice_ids != slice_place_ids:
            raise SystemExit(
                "切片地点集合与既有 staging 不一致："
                f"抽取 {len(slice_place_ids)} / CSV {len(legacy_slice_ids)}；"
                "M4-4a 不允许在切片口径上引入任何漂移"
            )

    pleiades_full = extract_pleiades_full(full_dir, new_ids, superseded_ids)
    say(
        f"  [7] Pleiades v4.1 records: {len(pleiades_full.records):,} "
        f"(places={pleiades_full.stats['record_kinds']['places']:,}, "
        f"new={pleiades_full.stats['places_new']:,}, "
        f"superseded={pleiades_full.stats['places_superseded']:,})"
    )

    extra_extractions = [pleiades_slice, whg, pleiades_full]

    # --- 6. sanity gates ----------------------------------------------------
    astro_lines = verify_astro_conversion()
    field_quirks = detect_field_name_quirks(chgis.declared_field_order)
    migration = analyse_migrations(chgis.records)
    say(
        f"  [8] astro assertions {len(astro_lines)}; field quirks {len(field_quirks)}; "
        f"migration edges {len(migration.edges):,}"
    )

    # --- 7. build tables ----------------------------------------------------
    bundle = build_bundle(
        chgis_records=chgis.records,
        mcgd_records=mcgd.records,
        date_rules=date_rules,
        chgis_attribution=chgis_citation,
        ingested_at=timestamp,
        mcgd_csv_relative=mcgd.csv_path_relative,
        mcgd_doi=mcgd.zenodo_doi,
        field_quirks=field_quirks,
        migration_edges=migration.edges,
        extra_extractions=extra_extractions,
    )
    say(
        "  [9] tables: "
        + ", ".join(f"{name}={len(rows):,}" for name, rows in bundle.tables.items())
    )

    # --- 8. write ------------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[Dict[str, Any]] = []
    for table_name, file_name in TABLE_FILES.items():
        path = out_dir / file_name
        rows_written = write_csv(path, TABLE_COLUMNS[table_name], bundle.tables[table_name])
        outputs.append(
            {
                "table": table_name,
                "file": file_name,
                "rows": rows_written,
                "bytes": file_size(path),
                "sha256": file_sha256(path),
            }
        )
    say(f"  [10] wrote {len(outputs)} CSV files to {out_dir}")

    # --- 9. re-hash inputs --------------------------------------------------
    input_sha_after = hash_paths(input_paths)
    changed = [
        path for path in input_sha_before if input_sha_before[path] != input_sha_after.get(path)
    ]
    say(f"  [11] inputs re-hashed: {'unchanged' if not changed else 'CHANGED'}")

    manifest: Dict[str, Any] = {
        "kind": "m4-4a-staging-build",
        "pipeline_version": PIPELINE_VERSION,
        "run_started_utc": started_at,
        "run_finished_utc": utc_now_iso(),
        "duration_seconds": round(time.perf_counter() - clock, 3),
        "ingested_at": timestamp,
        "out_dir": str(out_dir),
        "differences_from_run_all": list(DIFFERENCES_FROM_RUN_ALL),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "shapely": _shapely_version(),
            "note": (
                "归一化脚本只用标准库；shapely 仅被 Pleiades 全量几何分支使用"
                "（面有效性/修复、面内点、线长中点），来自 code/ops/.deps"
            ),
        },
        "inputs": {
            "count": len(input_paths),
            "verified_unchanged": not changed,
            "changed_files": [Path(p).name for p in changed],
            "files": [
                {
                    "path": str(Path(p).relative_to(project_root))
                    if str(p).startswith(str(project_root))
                    else str(p),
                    "bytes": file_size(Path(p)),
                    "sha256": input_sha_before[str(p)],
                }
                for p in input_paths
            ],
        },
        "outputs": outputs,
        "row_counts": {item["table"]: item["rows"] for item in outputs},
        "datasets": {
            "declared": [row["dataset_id"] for row in bundle.tables["data_datasets"]],
            "count": len(bundle.tables["data_datasets"]),
        },
        "pleiades_sets": {
            "v41_places_all": len(v41_all_ids),
            "slice_places": len(slice_place_ids),
            "overlap": len(superseded_ids),
            "new": len(new_ids),
            "overlap_ids_sha256": _digest_of_sorted_ids(superseded_ids),
            "new_ids_sha256": _digest_of_sorted_ids(new_ids),
            "legacy_slice_ids_cross_checked": legacy_slice_ids is not None,
        },
        "sources": {
            "chgis": {
                "records": len(chgis.records),
                "per_dataset": dict(sorted(Counter(r.source_dataset for r in chgis.records).items())),
                "citation": chgis_citation,
            },
            "mcgd": {"rows": len(mcgd.records), "doi": mcgd.zenodo_doi},
            "pleiades_slice": {
                "records": len(pleiades_slice.records),
                "files": [
                    {k: v for k, v in item.items() if k != "header"}
                    for item in pleiades_slice.slice_files
                ],
            },
            "whg": {"records": len(whg.records), "files": whg.stats.get("per_file", [])},
            "pleiades_gis_4_1": {
                "records": len(pleiades_full.records),
                "stats": pleiades_full.stats,
                "files": [
                    {k: v for k, v in item.items() if k != "header"}
                    for item in pleiades_full.slice_files
                ],
            },
        },
        "bundle_stats": bundle.stats,
        "astro_assertions": astro_lines,
        "migration_edges": len(migration.edges),
    }
    write_json(out_dir / "manifest.json", manifest)

    sums = "\n".join(f"{item['sha256']}  {item['file']}" for item in outputs) + "\n"
    (out_dir / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")

    if changed:
        raise SystemExit(
            "FATAL: read-only inputs changed during the run: " + ", ".join(changed)
        )

    say()
    say(f"  total: {manifest['duration_seconds']}s")
    for item in outputs:
        say(f"    {item['file']:36s} {item['rows']:>9,} rows  {item['sha256'][:16]}…")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        prog="build-staging-m4-3",
        description="Build the seven M4-4a staging tables (five sources) into code/data/staging_m4_3.",
    )
    parser.add_argument("--timestamp", default=DEFAULT_TIMESTAMP,
                        help=f"ingested_at stamp; default {DEFAULT_TIMESTAMP} keeps runs byte-identical")
    parser.add_argument("--out-dir", default=str(CODE_ROOT / "data" / "staging_m4_3"))
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve() if args.project_root else CODE_ROOT.parent
    if not (project_root / "设计资料").is_dir():
        raise SystemExit(f"project root does not contain 设计资料/: {project_root}")

    run(project_root, Path(args.out_dir).resolve(), args.timestamp, args.quiet)
    return 0


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
