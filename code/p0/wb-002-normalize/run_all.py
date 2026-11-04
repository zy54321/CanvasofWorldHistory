"""WB-002 historical-geodata normalisation pipeline -- single entry point.

Usage
-----
    python code/p0/wb-002-normalize/run_all.py

Optional arguments::

    --timestamp 2026-11-02T00:00:00Z   pin the ingest timestamp so two runs are
                                       byte-identical (also read from the
                                       WB002_RUN_TIMESTAMP environment variable)
    --project-root PATH                override the auto-detected project root
    --quiet                            suppress per-step chatter

The pipeline is read-only with respect to ``设计资料/P0验证/WB-002/sample_data/``.
It hashes every source file before and after the run and fails loudly if a byte
changed, so an accidental in-place modification cannot slip through unnoticed.

Pipeline stages
---------------
1. hash the read-only inputs
2. parse the CHGIS ``xtra_date_rules`` workbook (self-checking, never guessed)
3. extract 15,748 CHGIS point records from the two DBFs
4. extract 960 MCGD sample rows
5. verify the astronomical-year conversion assertions
6. run time / cluster / homonym quality analysis
7. build the six staging tables
8. write ``normalized/`` and ``issues/``
9. re-hash the inputs and compare
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Local modules live beside this file; make the import work regardless of cwd.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from chgis_extract import (  # noqa: E402
    CHGIS_DATASETS,
    citation_from_readme,
    extract_all,
    read_chgis_readme,
)
from chgis_migration import (  # noqa: E402
    analyse_migrations,
    build_review_queue,
    verify_xinxing_jun,
    verify_zhongshan_guo,
)
from csv_io import file_sha256, write_csv, write_json  # noqa: E402

from mcgd_extract import MCGD_SOURCE_DATASET, extract_mcgd  # noqa: E402
from pleiades_extract import PLEIADES_SLICE_DIR, SLICE_FILES, extract_pleiades  # noqa: E402
from normalize import TABLE_COLUMNS, PIPELINE_VERSION, build_bundle  # noqa: E402
from quality_checks import (  # noqa: E402
    analyse_time_anomalies,
    build_coordinate_clusters,
    build_homonym_stats,
    detect_field_name_quirks,
    find_cross_layer_disagreements,
    load_date_rule_dictionary,
    verify_astro_conversion,
)
from whg_extract import WHG_PLACE_DIR, extract_whg  # noqa: E402
from report_stats import (  # noqa: E402
    build_manifest_payload,
    build_stats_payload,
    write_chgis_all_records,
    write_cluster_members,
    write_coordinate_clusters,
    write_cross_layer_disagreements,
    write_homonyms,
    write_migration_chains,
    write_migration_review_queue,
    write_time_inversions,
)

#: Fallback CHGIS citation, used only when the README has no ``Citation:`` line.
FALLBACK_CHGIS_CITATION = (
    'CHGIS, Version: 6. (c) Fairbank Center for Chinese Studies of Harvard University '
    "and the Center for Historical Geographical Studies at Fudan University, 2016."
)

#: Table name -> file name inside ``normalized/``.
TABLE_FILES: Dict[str, str] = {
    "historical_places": "historical_places.csv",
    "historical_place_locations": "historical_place_locations.csv",
    "historical_place_names": "historical_place_names.csv",
    "source_records": "source_records.csv",
    "data_quality_issues": "data_quality_issues.csv",
    "candidate_matches": "candidate_matches.csv",
    "data_datasets": "data_datasets.csv",
}


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a ``Z`` suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class StepTimer:
    """Collect per-stage wall-clock durations for the manifest."""

    def __init__(self, quiet: bool = False) -> None:
        self._steps: List[Dict[str, Any]] = []
        self._quiet = quiet
        self._run_start = time.perf_counter()
        self._last = self._run_start

    def mark(self, name: str, detail: str = "") -> None:
        """Close the current stage and record its duration."""
        now = time.perf_counter()
        elapsed = now - self._last
        self._last = now
        self._steps.append({"step": name, "seconds": round(elapsed, 3), "detail": detail})
        if not self._quiet:
            suffix = f"  [{detail}]" if detail else ""
            print(f"  {elapsed:7.3f}s  {name}{suffix}")

    @property
    def steps(self) -> List[Dict[str, Any]]:
        """Recorded stages in execution order."""
        return list(self._steps)

    @property
    def total_seconds(self) -> float:
        """Total wall-clock time since the timer was created."""
        return time.perf_counter() - self._run_start


def resolve_project_root(explicit: Optional[str]) -> Path:
    """Locate the project root, defaulting to four levels above this script."""
    if explicit:
        root = Path(explicit).resolve()
        if not (root / "设计资料").is_dir():
            raise SystemExit(f"--project-root {root} does not contain 设计资料/")
        return root
    root = _HERE.parents[2]
    if not (root / "设计资料").is_dir():
        raise SystemExit(
            f"could not auto-detect the project root from {_HERE}; pass --project-root"
        )
    return root


def collect_input_paths(sample_dir: Path) -> List[Path]:
    """List every read-only input whose digest must be verified twice.

    Four sources are covered: CHGIS (two zips + dictionary + README + EULA),
    MCGD (CSV + Zenodo record), Pleiades (five slices + fetch log) and WHG (seven
    API responses + ``sources.json``).  The Pleiades slices live under
    ``P0收敛/WB-002/sample_data_pleiades/`` rather than ``sample_data/`` but they
    are just as read-only, so they are hashed on the same footing.
    """
    root = sample_dir.parents[3]
    paths = [sample_dir / "chgis" / dataset.zip_name for dataset in CHGIS_DATASETS]
    paths.append(sample_dir / "mcgd" / "MCGD_Data2026_08_25.csv.head-960rows.sample.csv")
    paths.append(sample_dir / "mcgd" / "zenodo_record_22094815.json")
    paths.append(sample_dir / "chgis" / "CHGIS_data_dictionary.zip")
    paths.append(sample_dir / "chgis" / "CHGIS_V6_README.txt")
    paths.append(sample_dir / "chgis" / "api" / "dataset_FDLFJ3_EULA.json")
    pleiades_dir = root / PLEIADES_SLICE_DIR
    paths.append(pleiades_dir / "FETCH_LOG.tsv")
    paths.extend(pleiades_dir / file_name for _logical, file_name, _kind in SLICE_FILES)
    whg_dir = root / WHG_PLACE_DIR
    paths.append(whg_dir / "sources.json")
    paths.extend(sorted((whg_dir / "place").glob("*.json")))
    return [path for path in paths if path.is_file()]


def hash_paths(paths: Sequence[Path]) -> Dict[str, str]:
    """Hash every path into a ``{absolute path: sha256}`` mapping."""
    return {str(path): file_sha256(path) for path in paths}


def compute_coordinate_dedup(records: Sequence[Any]) -> Dict[str, int]:
    """Measure coordinate uniqueness under several definitions.

    Four definitions are reported so the reader can reconcile any figure quoted
    elsewhere:

      * ``per_dataset_exact_string`` -- sum over datasets of distinct
        ``"X_COOR|Y_COOR"`` text pairs **where both coordinates parsed**.  This
        is the definition that yields 1,715 (prefecture) + 4,887 (county) =
        6,602, because ten county rows hold the DBF overflow marker
        ``**********`` instead of coordinates.
      * ``per_dataset_raw_text_including_overflow`` -- the same sum but treating
        ``**********|**********`` as one distinct value, which yields
        1,715 + 4,888 = 6,603.
      * ``combined_exact_string`` -- distinct pairs across both datasets at once,
        which removes the 589 coordinates shared by a prefecture seat and a county
        seat sitting at the same point.
      * ``combined_numeric_rounded_6dp`` -- distinct
        ``(round(lon,6), round(lat,6))`` tuples; equal to the exact-string count
        because the DBF stores exactly six decimals, which is the evidence that
        the choice of dedup definition does not change any result.
    """
    per_dataset: Dict[str, set] = {}
    per_dataset_raw: Dict[str, set] = {}
    combined_text: set = set()
    combined_raw: set = set()
    combined_numeric: set = set()
    for record in records:
        raw_key = f"{record.lon_text}|{record.lat_text}"
        if record.lon_text or record.lat_text:
            per_dataset_raw.setdefault(record.source_dataset, set()).add(raw_key)
            combined_raw.add(raw_key)
        key = record.coord_key
        if key is None:
            continue
        per_dataset.setdefault(record.source_dataset, set()).add(key)
        combined_text.add(key)
        combined_numeric.add((round(record.lon or 0.0, 6), round(record.lat or 0.0, 6)))
    result = {f"per_dataset_exact_string[{dataset}]": len(values) for dataset, values in per_dataset.items()}
    result.update(
        {
            f"per_dataset_raw_text_including_overflow[{dataset}]": len(values)
            for dataset, values in per_dataset_raw.items()
        }
    )
    result["per_dataset_exact_string_sum"] = sum(len(v) for v in per_dataset.values())
    result["per_dataset_raw_text_including_overflow_sum"] = sum(len(v) for v in per_dataset_raw.values())
    result["combined_exact_string"] = len(combined_text)
    result["combined_raw_text_including_overflow"] = len(combined_raw)
    result["combined_numeric_rounded_6dp"] = len(combined_numeric)
    result["shared_between_datasets"] = result["per_dataset_exact_string_sum"] - len(combined_text)
    return result


def run(
    project_root: Path, timestamp: Optional[str], quiet: bool
) -> Tuple[Path, Path, Dict[str, Any]]:
    """Execute the whole pipeline and return ``(normalized_dir, issues_dir, stats)``."""
    timer = StepTimer(quiet=quiet)
    sample_dir = project_root / "设计资料" / "P0验证" / "WB-002" / "sample_data"
    out_root = project_root / "设计资料" / "P0收敛" / "WB-002"
    normalized_dir = out_root / "normalized"
    issues_dir = out_root / "issues"

    if not sample_dir.is_dir():
        raise SystemExit(f"sample data directory not found: {sample_dir}")

    ingested_at = timestamp or os.environ.get("WB002_RUN_TIMESTAMP") or utc_now_iso()
    run_started_utc = utc_now_iso()

    if not quiet:
        print(f"WB-002 normalisation ({PIPELINE_VERSION})")
        print(f"  project root : {project_root}")
        print(f"  input root   : {sample_dir.relative_to(project_root)}")
        print(f"  ingested_at  : {ingested_at}")
        print()

    # --- 1. input digests ------------------------------------------------
    input_paths = collect_input_paths(sample_dir)
    input_sha_before = hash_paths(input_paths)
    timer.mark("hash inputs (before)", f"{len(input_paths)} files")

    # --- 2. date rule dictionary ----------------------------------------
    date_rules = load_date_rule_dictionary(sample_dir)
    if date_rules.loaded:
        timer.mark(
            "parse CHGIS date-rule dictionary",
            f"{len(date_rules.rules)} rules from {date_rules.source_member}",
        )
    else:
        timer.mark("parse CHGIS date-rule dictionary", f"FAILED: {date_rules.error}")

    # --- 3. CHGIS extraction --------------------------------------------
    extraction = extract_all(sample_dir, project_root)
    per_dataset = Counter(record.source_dataset for record in extraction.records)
    timer.mark(
        "extract CHGIS DBF records",
        ", ".join(f"{k}={v}" for k, v in sorted(per_dataset.items())),
    )

    readme = read_chgis_readme(sample_dir)
    chgis_citation = citation_from_readme(readme) or FALLBACK_CHGIS_CITATION
    timer.mark("read CHGIS README (citation)", chgis_citation[:60] + "...")

    # --- 4. MCGD extraction ---------------------------------------------
    mcgd = extract_mcgd(sample_dir, project_root)
    timer.mark("extract MCGD sample rows", f"rows={len(mcgd.records)}")

    # --- 4b. Pleiades + WHG extraction -----------------------------------
    pleiades = extract_pleiades(project_root)
    timer.mark(
        "extract Pleiades GIS slices",
        f"rows={len(pleiades.records)}, places={pleiades.stats['record_kinds'].get('places', 0)}, "
        f"discarded_tails={pleiades.stats['discarded_tail_row_count']}",
    )
    whg = extract_whg(project_root)
    timer.mark(
        "extract WHG API samples",
        f"rows={len(whg.records)}, places={whg.stats['place_records']}, "
        f"schemas={whg.stats['schema_counts']}",
    )
    extra_extractions = [pleiades, whg]

    # --- 5. astro assertions --------------------------------------------
    astro_lines = verify_astro_conversion()
    timer.mark("verify astronomical-year conversion", f"{len(astro_lines)} assertions passed")

    # --- 6. quality analysis --------------------------------------------
    time_anomalies = analyse_time_anomalies(extraction.records)
    timer.mark(
        "analyse time anomalies",
        f"beg>end={len(time_anomalies.inversions)} "
        f"(pref={sum(1 for r in time_anomalies.inversions if r.source_dataset == 'chgis_pref')}, "
        f"cnty={sum(1 for r in time_anomalies.inversions if r.source_dataset == 'chgis_cnty')})",
    )

    clusters, cluster_stats = build_coordinate_clusters(extraction.records)
    timer.mark(
        "build coordinate clusters",
        f"clusters={len(clusters)}, max_size={cluster_stats['size_histogram'] and max(cluster_stats['size_histogram'])}",
    )

    homonyms, homonym_stats = build_homonym_stats(extraction.records)
    timer.mark(
        "analyse homonyms",
        f"multi_coord_names={len(homonyms)}/{homonym_stats['totals']['distinct_names']}",
    )

    field_quirks = detect_field_name_quirks(extraction.declared_field_order)
    timer.mark("detect field-name quirks", f"{len(field_quirks)} found")

    cross_layer, cross_layer_stats = find_cross_layer_disagreements(extraction.records)
    timer.mark(
        "find cross-layer disagreements",
        f"{cross_layer_stats['totals']['pairs']} (name,year-span) pairs placed differently",
    )

    # --- 6b. rule-based migration analysis -------------------------------
    # Must run before build_bundle: its edges are appended to candidate_matches.
    migration = analyse_migrations(extraction.records)
    review_queue = build_review_queue(migration)
    timer.mark(
        "analyse migration chains",
        f"{migration.stats['adjacent_pairs_total']} adjacent pairs, "
        f"{migration.stats['migration_chains']} migration chains, "
        f"{len(review_queue)} legs queued for review",
    )

    xinxing = verify_xinxing_jun(migration)
    zhongshan = verify_zhongshan_guo(migration)
    for label, result in (("新兴郡", xinxing), ("中山国", zhongshan)):
        verdict = "PASS" if result["passed"] else "FAIL"
        # Failures are always printed, even under --quiet: a silent regression is
        # worse than a noisy log.
        if quiet and result["passed"]:
            continue
        print(f"  [ground-truth] {label}: {verdict}")
        if label == "新兴郡":
            print(
                f"                 seats={result['seat_count']} coords={result['observed_seats']}"
            )
            print(
                f"                 foreign seat excluded from chain="
                f"{result['foreign_seat_excluded_from_chain']}; "
                f"homonym legs={len(result['homonym_edges'])}"
            )
        else:
            print(
                f"                 cross-layer edges={result['cross_layer_edges']}; "
                f"chains={[c['seat_count'] for c in result['chains_for_name']]}; "
                f"migration_chains={result['migration_chain_count']}"
            )
    ground_truth = {"xinxing_jun": xinxing, "zhongshan_guo": zhongshan}
    timer.mark(
        "verify migration ground truth",
        f"新兴郡={'PASS' if xinxing['passed'] else 'FAIL'}, "
        f"中山国={'PASS' if zhongshan['passed'] else 'FAIL'}",
    )

    # --- 7. build tables -------------------------------------------------
    bundle = build_bundle(
        chgis_records=extraction.records,
        mcgd_records=mcgd.records,
        date_rules=date_rules,
        chgis_attribution=chgis_citation,
        ingested_at=ingested_at,
        mcgd_csv_relative=mcgd.csv_path_relative,
        mcgd_doi=mcgd.zenodo_doi,
        field_quirks=field_quirks,
        migration_edges=migration.edges,
        extra_extractions=extra_extractions,
    )
    timer.mark(
        "build seven staging tables",
        ", ".join(f"{name}={len(rows)}" for name, rows in bundle.tables.items()),
    )

    # --- 8. write outputs ------------------------------------------------
    normalized_dir.mkdir(parents=True, exist_ok=True)
    issues_dir.mkdir(parents=True, exist_ok=True)
    output_paths: List[Path] = []
    row_counts: Dict[str, int] = {}

    for table_name, file_name in TABLE_FILES.items():
        path = normalized_dir / file_name
        written = write_csv(path, TABLE_COLUMNS[table_name], bundle.tables[table_name])
        row_counts[str(path)] = written
        output_paths.append(path)
    timer.mark("write normalized/*.csv", f"{len(TABLE_FILES)} tables")

    all_records_path = issues_dir / "chgis_all_records.csv"
    row_counts[str(all_records_path)] = write_chgis_all_records(all_records_path, extraction)
    output_paths.append(all_records_path)

    inversions_path = issues_dir / "time_inversions.csv"
    row_counts[str(inversions_path)] = write_time_inversions(
        inversions_path, time_anomalies.inversions, date_rules
    )
    output_paths.append(inversions_path)

    clusters_path = issues_dir / "coordinate_clusters.csv"
    row_counts[str(clusters_path)] = write_coordinate_clusters(
        clusters_path, clusters, bundle.place_lookup
    )
    output_paths.append(clusters_path)

    members_path = issues_dir / "cluster_members.csv"
    row_counts[str(members_path)] = write_cluster_members(
        members_path, clusters, bundle.place_lookup
    )
    output_paths.append(members_path)

    homonyms_path = issues_dir / "homonyms.csv"
    row_counts[str(homonyms_path)] = write_homonyms(homonyms_path, homonyms)
    output_paths.append(homonyms_path)

    cross_layer_path = issues_dir / "cross_layer_disagreements.csv"
    row_counts[str(cross_layer_path)] = write_cross_layer_disagreements(
        cross_layer_path, cross_layer
    )
    output_paths.append(cross_layer_path)

    chains_path = issues_dir / "migration_chains.csv"
    row_counts[str(chains_path)] = write_migration_chains(
        chains_path, migration.migration_chains
    )
    output_paths.append(chains_path)

    review_path = issues_dir / "migration_review_queue.csv"
    row_counts[str(review_path)] = write_migration_review_queue(review_path, review_queue)
    output_paths.append(review_path)
    timer.mark("write issues/*.csv", f"{len(output_paths) - len(TABLE_FILES)} files")

    # --- 9. stats.json ---------------------------------------------------
    coordinate_dedup = compute_coordinate_dedup(extraction.records)
    inversion_denominator = {
        dataset: {
            "records": sum(1 for r in extraction.records if r.source_dataset == dataset),
            "records_with_both_years": sum(
                1
                for r in extraction.records
                if r.source_dataset == dataset and r.beg_year is not None and r.end_year is not None
            ),
            "beg_gt_end": sum(
                1 for r in time_anomalies.inversions if r.source_dataset == dataset
            ),
        }
        for dataset in sorted(extraction.tables)
    }

    stats = build_stats_payload(
        ingested_at=ingested_at,
        extraction=extraction,
        time_anomalies=time_anomalies,
        clusters=clusters,
        cluster_stats=cluster_stats,
        homonyms=homonyms,
        homonym_stats=homonym_stats,
        bundle_stats=bundle.stats,
        date_rules=date_rules,
        field_quirks=field_quirks,
        mcgd_header_ok=mcgd.header_matches_expected,
        mcgd_rows=len(mcgd.records),
        coordinate_dedup=coordinate_dedup,
        time_inversion_denominator=inversion_denominator,
        cross_layer=cross_layer,
        cross_layer_stats=cross_layer_stats,
        migration={**migration.stats, "ground_truth": ground_truth},
        review_queue=review_queue,
        extra_extractions=extra_extractions,
    )
    stats["provenance"] = {
        "chgis_citation": chgis_citation,
        "chgis_encoding": dict(extraction.cpg_text),
        "chgis_prj": dict(extraction.prj_text),
        "mcgd_doi": mcgd.zenodo_doi,
        "mcgd_title": mcgd.zenodo_title,
        "mcgd_header": mcgd.header,
        "mcgd_header_matches_expected": mcgd.header_matches_expected,
        "mcgd_csv_sha256": mcgd.csv_sha256,
        "mcgd_rows": len(mcgd.records),
        "mcgd_distinct_loc_id": len({r.loc_id for r in mcgd.records}),
        "mcgd_distinct_name_id": len({r.name_id for r in mcgd.records}),
        "mcgd_code_values": dict(
            sorted(Counter(r.code for r in mcgd.records).items())
        ),
        "mcgd_province_count": len({r.prov_zh for r in mcgd.records}),
        "pleiades_attribution_note": pleiades.attribution_note,
        "pleiades_slice_files": pleiades.slice_files,
        "whg_attribution_note": whg.attribution_note,
        "whg_files": whg.stats["per_file"],
    }
    stats["astro_assertions"] = astro_lines
    stats["issues"] = {
        "date_rule_dictionary_parsed": date_rules.loaded,
        "date_rule_dictionary_error": date_rules.error,
        "mcgd_crs_declared": False,
        "field_name_quirks": [f"{q.source_dataset}:{q.field_name}->{q.expected_name}" for q in field_quirks],
    }
    stats["output_row_counts"] = {
        Path(path).name: count for path, count in sorted(row_counts.items())
    }

    stats_path = normalized_dir / "stats.json"
    write_json(stats_path, stats)
    timer.mark("write stats.json", f"{len(stats)} top-level keys")

    # --- 10. re-hash inputs and write the manifest ----------------------
    input_sha_after = hash_paths(input_paths)
    changed = [
        path for path in input_sha_before if input_sha_before[path] != input_sha_after.get(path)
    ]
    timer.mark("hash inputs (after)", "unchanged" if not changed else f"CHANGED: {changed}")

    manifest = build_manifest_payload(
        project_root=project_root,
        run_started_utc=run_started_utc,
        run_finished_utc=utc_now_iso(),
        duration_seconds=timer.total_seconds,
        ingested_at=ingested_at,
        input_paths=input_paths,
        input_sha256=input_sha_before,
        output_paths=output_paths + [stats_path],
        output_row_counts=row_counts,
        step_timings=timer.steps,
        astro_assertions=astro_lines,
        pip_freeze_note=(
            "none: the pipeline imports only the Python standard library "
            "(argparse, csv, dataclasses, datetime, hashlib, json, math, platform, "
            "struct, sys, time, traceback, xml.etree.ElementTree, zipfile)"
        ),
    )
    manifest["input_integrity"] = {
        "verified": not changed,
        "before": {Path(p).name: digest for p, digest in sorted(input_sha_before.items())},
        "after": {Path(p).name: digest for p, digest in sorted(input_sha_after.items())},
        "changed_files": [Path(p).name for p in changed],
    }
    manifest["migration_ground_truth"] = ground_truth
    manifest_path = normalized_dir / "run_manifest.json"
    write_json(manifest_path, manifest)
    timer.mark("write run_manifest.json")

    failed_checks = [
        name
        for name, result in (("新兴郡", xinxing), ("中山国", zhongshan))
        if not result["passed"]
    ]
    if failed_checks:
        # Deliberately not fatal and deliberately not "fixed": the point of the
        # regression is to report that the rules do not reproduce a known case,
        # so the actual output stays on disk for inspection.
        print()
        print("  WARNING: ground-truth regression FAILED for: " + ", ".join(failed_checks))
        print("           Thresholds were NOT tuned to fit the case. Observed values are in")
        print("           stats.json -> migration.ground_truth and run_manifest.json.")

    if changed:
        raise SystemExit(
            "FATAL: read-only source files changed during the run: " + ", ".join(changed)
        )

    if not quiet:
        print()
        print(f"  total: {timer.total_seconds:.2f}s")
        print(f"  output: {normalized_dir}")
        print(f"          {issues_dir}")

    return normalized_dir, issues_dir, stats


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        prog="wb-002-normalize",
        description="Normalise CHGIS V6 and MCGD sample data into a traceable staging dataset.",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help=(
            "ISO-8601 timestamp stamped onto every output row. Pin it to make two runs "
            "byte-identical. Also read from WB002_RUN_TIMESTAMP. Defaults to now (UTC)."
        ),
    )
    parser.add_argument("--project-root", default=None, help="Project root containing 设计资料/")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-step chatter")
    args = parser.parse_args(argv)

    try:
        project_root = resolve_project_root(args.project_root)
        run(project_root, args.timestamp, args.quiet)
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - surface a full traceback for diagnosis
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
