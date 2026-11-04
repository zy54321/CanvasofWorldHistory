"""Issue-side artefacts and machine-readable statistics for WB-002.

This module owns everything that lands in ``设计资料/P0收敛/WB-002/issues/`` plus
the two machine-readable summaries in ``normalized/``:

* ``issues/chgis_all_records.csv`` -- the lossless 15,748-row extraction.
* ``issues/time_inversions.csv``  -- every ``BEG_YR > END_YR`` record.
* ``issues/coordinate_clusters.csv`` / ``issues/cluster_members.csv``.
* ``issues/homonyms.csv``.
* ``normalized/stats.json``  -- every count the report cites.
* ``normalized/run_manifest.json`` -- input/output digests and provenance.

Nothing here recomputes a number that :mod:`quality_checks` already produced; the
job of this module is to serialise, not to decide.
"""

from __future__ import annotations

import platform
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from chgis_extract import ChgisExtraction
from csv_io import file_sha256, file_size, write_csv, write_json
from quality_checks import (
    ClusterClassification,
    DateRuleDictionary,
    HomonymEntry,
    TimeAnomalies,
)
from chgis_migration import REVIEW_QUEUE_COLUMNS
from normalize import PIPELINE_VERSION
from time_semantics import TIME_BOUND_TYPE_DESCRIPTIONS, TIME_BOUND_TYPES

__all__ = [
    "CHGIS_ALL_RECORDS_COLUMNS",
    "TIME_INVERSIONS_COLUMNS",
    "COORDINATE_CLUSTERS_COLUMNS",
    "CLUSTER_MEMBERS_COLUMNS",
    "HOMONYMS_COLUMNS",
    "write_chgis_all_records",
    "write_time_inversions",
    "write_coordinate_clusters",
    "write_cluster_members",
    "write_homonyms",
    "write_cross_layer_disagreements",
    "write_migration_chains",
    "write_migration_review_queue",
    "build_stats_payload",
    "build_manifest_payload",
]

CHGIS_ALL_RECORDS_COLUMNS: Sequence[str] = (
    "source_dataset", "record_index", "raw_zip", "raw_dbf",
)

TIME_INVERSIONS_COLUMNS: Sequence[str] = (
    "source_dataset", "record_index", "SYS_ID", "NAME_CH", "NAME_PY",
    "BEG_YR", "END_YR", "delta_years", "BEG_RULE", "END_RULE",
    "X_COOR", "Y_COOR", "PRES_LOC", "NOTE_ID", "TYPE_PY", "LEV_RANK",
)

COORDINATE_CLUSTERS_COLUMNS: Sequence[str] = (
    "cluster_id", "coord_key", "lon", "lat", "record_count", "distinct_sysids",
    "distinct_names", "same_place_multi_period", "same_name_diff_entity",
    "diff_name_diff_entity", "suspected_duplicate", "classification",
    "source_datasets", "place_ids",
)

CLUSTER_MEMBERS_COLUMNS: Sequence[str] = (
    "cluster_id", "coord_key", "source_dataset", "record_index", "SYS_ID",
    "NAME_CH", "NAME_PY", "BEG_YR", "END_YR", "TYPE_PY", "TYPE_CH", "LEV_RANK",
    "PRES_LOC", "place_id",
)

HOMONYMS_COLUMNS: Sequence[str] = (
    "name", "coord_count", "sysid_count", "record_count",
    "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat",
    "cross_province", "province_hints",
)

CROSS_LAYER_COLUMNS: Sequence[str] = (
    "name", "BEG_YR", "END_YR", "prefecture_sys_ids", "county_sys_ids",
    "prefecture_coords", "county_coords", "max_separation_m",
)

MIGRATION_CHAINS_COLUMNS: Sequence[str] = (
    "chain_id", "name_ch", "source_dataset", "seat_count", "record_count",
    "first_beg_yr", "last_end_yr", "total_span_years", "max_leg_distance_m",
    "total_path_distance_m", "min_confidence", "sys_ids", "coords", "pres_locs",
    "years", "needs_manual_review",
)


def write_migration_chains(path: Path, chains: Sequence[Any]) -> int:
    """Write the rule-based migration chains.

    Only chains that qualify as a real migration (``seat_count >= 2`` **and** at
    least one ``location_migration_candidate`` leg) are written; single-seat
    same-entity chains are summarised in ``stats.json`` instead of flooding this
    file.  Every row is marked ``needs_manual_review=true``: nothing here is a
    conclusion, only a place to start reviewing.

    Multi-value columns use ``;`` between records and ``|`` inside one record
    (``lon|lat``, ``BEG_YR|END_YR``), so the two levels stay distinguishable
    under a single CSV delimiter.
    """
    rows = []
    for chain in chains:
        rows.append(
            {
                "chain_id": chain.chain_id,
                "name_ch": chain.name_ch,
                "source_dataset": chain.source_dataset,
                "seat_count": str(chain.seat_count),
                "record_count": str(chain.record_count),
                "first_beg_yr": "" if chain.first_beg_yr is None else str(chain.first_beg_yr),
                "last_end_yr": "" if chain.last_end_yr is None else str(chain.last_end_yr),
                "total_span_years": (
                    "" if chain.total_span_years is None else str(chain.total_span_years)
                ),
                "max_leg_distance_m": f"{chain.max_leg_distance_m:.1f}",
                "total_path_distance_m": f"{chain.total_path_distance_m:.1f}",
                "min_confidence": chain.min_confidence,
                "sys_ids": ";".join(chain.sys_ids),
                "coords": ";".join(chain.coord_keys),
                "pres_locs": ";".join(record.pres_loc for record in chain.records),
                "years": ";".join(record.year_span_key for record in chain.records),
                "needs_manual_review": "true",
            }
        )
    return write_csv(path, MIGRATION_CHAINS_COLUMNS, rows)


def write_migration_review_queue(path: Path, entries: Sequence[Any]) -> int:
    """Write ``issues/migration_review_queue.csv``.

    The file exists because ``confidence`` in ``migration_chains.csv`` and
    ``candidate_matches.csv`` encodes **year-gap tightness only**.  A leg whose
    spans touch is labelled ``high`` whether it moved 4 km or 250 km, so the
    distance has to be read separately.  ``priority`` re-sorts the accepted legs
    so the longest, most temporally contiguous ones are looked at first.

    Args:
      path: Destination file.
      entries: :class:`chgis_migration.ReviewQueueEntry` objects, already sorted.

    Returns:
      Number of data rows written.
    """
    rows = []
    for entry in entries:
        rows.append(
            {
                "priority": entry.priority,
                "name_ch": entry.name_ch,
                "source_dataset": entry.source_dataset,
                "leg_distance_m": f"{entry.leg_distance_m:.1f}",
                "gap_years": str(entry.gap_years),
                "confidence": entry.confidence,
                "from_coord": entry.from_coord,
                "to_coord": entry.to_coord,
                "from_pres_loc": entry.from_pres_loc,
                "to_pres_loc": entry.to_pres_loc,
                "review_hint": entry.review_hint,
            }
        )
    return write_csv(path, REVIEW_QUEUE_COLUMNS, rows)


def write_cross_layer_disagreements(path: Path, entries: Sequence[Any]) -> int:
    """Write ``(name, year span)`` pairs the two CHGIS layers place differently."""
    rows = []
    for entry in entries:
        rows.append(
            {
                "name": entry.name,
                "BEG_YR": entry.beg_yr,
                "END_YR": entry.end_yr,
                "prefecture_sys_ids": "|".join(entry.prefecture_sys_ids),
                "county_sys_ids": "|".join(entry.county_sys_ids),
                "prefecture_coords": "|".join(entry.prefecture_coords),
                "county_coords": "|".join(entry.county_coords),
                "max_separation_m": f"{entry.max_separation_m:.1f}",
            }
        )
    return write_csv(path, CROSS_LAYER_COLUMNS, rows)


def write_chgis_all_records(path: Path, extraction: ChgisExtraction) -> int:
    """Write the lossless 15,748-row extraction of both CHGIS DBFs.

    Columns are the provenance triplet followed by all 23 original DBF fields in
    a union order, so a field that exists in only one layer leaves an empty cell
    in the rows of the other.
    """
    columns = list(CHGIS_ALL_RECORDS_COLUMNS) + list(extraction.field_order)
    rows = []
    for record in extraction.records:
        row = {
            "source_dataset": record.source_dataset,
            "record_index": str(record.record_index),
            "raw_zip": record.raw_zip,
            "raw_dbf": record.raw_dbf,
        }
        for field_name in extraction.field_order:
            row[field_name] = record.raw.get(field_name, "")
        rows.append(row)
    return write_csv(path, columns, rows)


def write_time_inversions(
    path: Path, inversions: Sequence[Any], date_rules: DateRuleDictionary
) -> int:
    """Write every record whose ``BEG_YR`` is strictly greater than ``END_YR``.

    ``delta_years`` is ``BEG_YR - END_YR`` and is always positive here.  The raw
    years are copied unchanged: this file is an evidence list, not a repair list.
    """
    rows = []
    for record in inversions:
        beg = record.beg_year
        end = record.end_year
        delta = "" if beg is None or end is None else str(beg - end)
        rows.append(
            {
                "source_dataset": record.source_dataset,
                "record_index": str(record.record_index),
                "SYS_ID": record.sys_id_text,
                "NAME_CH": record.name_ch,
                "NAME_PY": record.name_py,
                "BEG_YR": record.raw.get("BEG_YR", ""),
                "END_YR": record.raw.get("END_YR", ""),
                "delta_years": delta,
                "BEG_RULE": record.beg_rule,
                "END_RULE": record.end_rule,
                "X_COOR": record.lon_text,
                "Y_COOR": record.lat_text,
                "PRES_LOC": record.pres_loc,
                "NOTE_ID": record.raw.get("NOTE_ID", ""),
                "TYPE_PY": record.type_py,
                "LEV_RANK": record.lev_rank,
            }
        )
    return write_csv(path, TIME_INVERSIONS_COLUMNS, rows)


def write_coordinate_clusters(
    path: Path, clusters: Sequence[ClusterClassification], place_lookup: Dict[str, str]
) -> int:
    """Write the per-coordinate summary table, ordered by record count descending."""
    rows = []
    for cluster in clusters:
        datasets = sorted({record.source_dataset for record in cluster.records})
        place_ids = sorted(
            {
                place_lookup.get(f"{record.source_dataset}:{record.record_index}", "")
                for record in cluster.records
            }
        )
        rows.append(
            {
                "cluster_id": cluster.cluster_id,
                "coord_key": cluster.coord_key,
                "lon": _fmt(cluster.lon),
                "lat": _fmt(cluster.lat),
                "record_count": str(cluster.record_count),
                "distinct_sysids": str(cluster.distinct_sysids),
                "distinct_names": str(cluster.distinct_names),
                "same_place_multi_period": str(cluster.same_place_multi_period),
                "same_name_diff_entity": str(cluster.same_name_diff_entity),
                "diff_name_diff_entity": str(cluster.diff_name_diff_entity),
                "suspected_duplicate": str(cluster.suspected_duplicate),
                "classification": cluster.classification,
                "source_datasets": "|".join(datasets),
                "place_ids": "|".join(pid for pid in place_ids if pid),
            }
        )
    return write_csv(path, COORDINATE_CLUSTERS_COLUMNS, rows)


def write_cluster_members(
    path: Path, clusters: Sequence[ClusterClassification], place_lookup: Dict[str, str]
) -> int:
    """Write one row per record that shares a coordinate with at least one other record."""
    rows = []
    for cluster in clusters:
        for record in cluster.records:
            rows.append(
                {
                    "cluster_id": cluster.cluster_id,
                    "coord_key": cluster.coord_key,
                    "source_dataset": record.source_dataset,
                    "record_index": str(record.record_index),
                    "SYS_ID": record.sys_id_text,
                    "NAME_CH": record.name_ch,
                    "NAME_PY": record.name_py,
                    "BEG_YR": record.raw.get("BEG_YR", ""),
                    "END_YR": record.raw.get("END_YR", ""),
                    "TYPE_PY": record.type_py,
                    "TYPE_CH": record.type_ch,
                    "LEV_RANK": record.lev_rank,
                    "PRES_LOC": record.pres_loc,
                    "place_id": place_lookup.get(f"{record.source_dataset}:{record.record_index}", ""),
                }
            )
    return write_csv(path, CLUSTER_MEMBERS_COLUMNS, rows)


def write_homonyms(path: Path, entries: Sequence[HomonymEntry]) -> int:
    """Write every ``NAME_CH`` observed at more than one exact coordinate."""
    rows = []
    for entry in entries:
        rows.append(
            {
                "name": entry.name,
                "coord_count": str(len(entry.coord_keys)),
                "sysid_count": str(len(entry.sysids)),
                "record_count": str(entry.record_count),
                "bbox_min_lon": _fmt(entry.bbox[0]),
                "bbox_min_lat": _fmt(entry.bbox[1]),
                "bbox_max_lon": _fmt(entry.bbox[2]),
                "bbox_max_lat": _fmt(entry.bbox[3]),
                "cross_province": "true" if entry.is_cross_province else "false",
                "province_hints": "|".join(entry.provinces),
            }
        )
    return write_csv(path, HOMONYMS_COLUMNS, rows)


def _fmt(value: float) -> str:
    """Render a float without trailing zeros, matching the main tables."""
    if value is None:
        return ""
    text = f"{value:.9f}".rstrip("0").rstrip(".")
    return text or "0"


def _build_sources_section(
    extra_extractions: Sequence[Any],
    sysid_per_dataset: Dict[str, Any],
    mcgd_rows: int,
) -> Dict[str, Any]:
    """Summarise every imported source so one key answers "what came in?".

    Args:
      extra_extractions: Pleiades and WHG extractions.
      sysid_per_dataset: Per-CHGIS-layer record counts.
      mcgd_rows: Number of MCGD sample rows read.

    Returns:
      A ``{source_id: {...}}`` mapping with per-source record and place counts.
    """
    section: Dict[str, Any] = {
        "chgis": {
            "records": sum(entry["records"] for entry in sysid_per_dataset.values()),
            "per_layer": {
                layer: {
                    "records": entry["records"],
                    "distinct_sys_id": entry["distinct_sys_id"],
                }
                for layer, entry in sorted(sysid_per_dataset.items())
            },
        },
        "mcgd": {"records": mcgd_rows},
    }
    for extraction in extra_extractions:
        entry = dict(extraction.stats)
        entry["records_total"] = len(extraction.records)
        entry["place_records"] = sum(
            1 for record in extraction.records if record.record_kind == "place"
        )
        entry["slice_files"] = extraction.slice_files
        section[extraction.source_id] = entry
    return section


def build_stats_payload(
    *,
    ingested_at: str,
    extraction: ChgisExtraction,
    time_anomalies: TimeAnomalies,
    clusters: Sequence[ClusterClassification],
    cluster_stats: Dict[str, Counter],
    homonyms: Sequence[HomonymEntry],
    homonym_stats: Dict[str, Counter],
    bundle_stats: Dict[str, Any],
    date_rules: DateRuleDictionary,
    field_quirks: Sequence[Any],
    mcgd_header_ok: bool,
    mcgd_rows: int,
    coordinate_dedup: Dict[str, int],
    time_inversion_denominator: Dict[str, int],
    cross_layer: Sequence[Any] = (),
    cross_layer_stats: Optional[Dict[str, Counter]] = None,
    migration: Optional[Dict[str, Any]] = None,
    review_queue: Sequence[Any] = (),
    extra_extractions: Sequence[Any] = (),
) -> Dict[str, Any]:
    """Assemble ``stats.json`` -- the single source of truth for report numbers.

    Every value here is produced by the pipeline; no figure in the written report
    should be typed by hand.
    """
    inversions = time_anomalies.inversions
    per_dataset_inversions = Counter(record.source_dataset for record in inversions)

    sysid_per_dataset: Dict[str, Any] = {}
    for dataset, table in extraction.tables.items():
        sys_ids = [record.sys_id_text for record in extraction.records if record.source_dataset == dataset]
        counts = Counter(sys_ids)
        sysid_per_dataset[dataset] = {
            "records": len(sys_ids),
            "distinct_sys_id": len(counts),
            "sys_id_occurrences": {f"{n}x": c for n, c in sorted(Counter(counts.values()).items())},
            "sys_ids_with_multiple_records": sum(1 for v in counts.values() if v > 1),
            "dbf_declared_record_count": table.record_count,
            "dbf_deleted_records": table.deleted_count,
        }

    chgis_dataset_sysids = {
        dataset: {record.sys_id_text for record in extraction.records if record.source_dataset == dataset}
        for dataset in extraction.tables
    }
    cross_dataset_sysid_overlap = 0
    datasets = sorted(chgis_dataset_sysids)
    for i, left in enumerate(datasets):
        for right in datasets[i + 1 :]:
            cross_dataset_sysid_overlap += len(chgis_dataset_sysids[left] & chgis_dataset_sysids[right])

    worst_clusters = [
        {
            "cluster_id": cluster.cluster_id,
            "coord_key": cluster.coord_key,
            "record_count": cluster.record_count,
            "distinct_sysids": cluster.distinct_sysids,
            "distinct_names": cluster.distinct_names,
            "same_place_multi_period": cluster.same_place_multi_period,
            "same_name_diff_entity": cluster.same_name_diff_entity,
            "diff_name_diff_entity": cluster.diff_name_diff_entity,
            "suspected_duplicate": cluster.suspected_duplicate,
            "classification": cluster.classification,
            "members": [
                {
                    "source_dataset": record.source_dataset,
                    "record_index": record.record_index,
                    "sys_id": record.sys_id_text,
                    "name_ch": record.name_ch,
                    "beg_yr": record.raw.get("BEG_YR", ""),
                    "end_yr": record.raw.get("END_YR", ""),
                    "type_py": record.type_py,
                    "pres_loc": record.pres_loc,
                }
                for record in cluster.records
            ],
        }
        for cluster in clusters[:20]
    ]

    return {
        "pipeline_version": PIPELINE_VERSION,
        "python_version": platform.python_version(),
        # ``stats.json`` carries no wall-clock field on purpose: with a pinned
        # ``--timestamp`` it must be byte-identical between runs.  The wall clock
        # lives in ``run_manifest.json`` (``run_started_utc`` /
        # ``run_finished_utc`` / ``duration_seconds``), which is provenance, not
        # measurement.
        "ingested_at": ingested_at,
        "chgis": {
            "records_total": len(extraction.records),
            "field_order": extraction.field_order,
            "declared_field_order": extraction.declared_field_order,
            "encoding": {k: v for k, v in extraction.cpg_text.items()},
            "prj": {k: v for k, v in extraction.prj_text.items()},
            "per_dataset": sysid_per_dataset,
            "distinct_sys_id_total": sum(v["distinct_sys_id"] for v in sysid_per_dataset.values()),
            "cross_dataset_sys_id_overlap": cross_dataset_sysid_overlap,
            "coordinate_dedup": coordinate_dedup,
            "field_name_quirks": [
                {
                    "source_dataset": q.source_dataset,
                    "field_name": q.field_name,
                    "expected_name": q.expected_name,
                    "note": q.note,
                }
                for q in field_quirks
            ],
        },
        "time": {
            "beg_gt_end_total": len(inversions),
            "beg_gt_end_per_dataset": dict(sorted(per_dataset_inversions.items())),
            "beg_gt_end_definition": (
                "BEG_YR and END_YR both numeric and BEG_YR > END_YR strictly; blank years and "
                "BEG_YR == END_YR are reported separately and are NOT counted here"
            ),
            "denominators": time_inversion_denominator,
            "null_beg_year": len(time_anomalies.null_beg),
            "null_end_year": len(time_anomalies.null_end),
            "beg_eq_end": len(time_anomalies.equal_years),
            "beg_eq_end_per_dataset": {
                dataset: sum(1 for r in time_anomalies.equal_years if r.source_dataset == dataset)
                for dataset in sorted(extraction.tables)
            },
            "year_out_of_range": len(time_anomalies.out_of_range),
            "year_min": time_anomalies.year_min,
            "year_max": time_anomalies.year_max,
            "per_dataset": time_anomalies.per_dataset,
            "beg_rule_counts": dict(sorted(time_anomalies.beg_rule_counts.items())),
            "end_rule_counts": dict(sorted(time_anomalies.end_rule_counts.items())),
            "date_rule_dictionary": {
                "loaded": date_rules.loaded,
                "source_member": date_rules.source_member,
                "error": date_rules.error,
                "entries": date_rules.rules,
                "undocumented_observed_codes": sorted(
                    {
                        code
                        for code in list(time_anomalies.beg_rule_counts) + list(time_anomalies.end_rule_counts)
                        if code and code not in date_rules.rules
                    }
                ),
            },
        },
        "structure": {
            "note_id_distinct": len([k for k in time_anomalies.note_id_counts if k]),
            "note_id_top_repeats": [
                {"note_id": note_id, "records": count}
                for note_id, count in time_anomalies.note_id_counts.most_common(10)
            ],
            "obj_type_counts": dict(sorted(time_anomalies.obj_type_counts.items())),
            "lev_rank_counts": dict(sorted(time_anomalies.lev_rank_counts.items())),
            "duplicate_sys_ids": {
                key: [
                    {
                        "record_index": record.record_index,
                        "name_ch": record.name_ch,
                        "beg_yr": record.raw.get("BEG_YR", ""),
                        "end_yr": record.raw.get("END_YR", ""),
                        "coord": record.coord_key,
                    }
                    for record in members
                ]
                for key, members in sorted(time_anomalies.duplicate_sysids.items())
            },
        },
        "clusters": {
            "distinct_coordinates": len(clusters),
            "size_histogram": {str(k): v for k, v in sorted(cluster_stats["size_histogram"].items())},
            "classifications": dict(sorted(cluster_stats["classifications"].items())),
            "pairwise": dict(cluster_stats["pairwise"]),
            "max_cluster_size": max((c.record_count for c in clusters), default=0),
            "top_20": worst_clusters,
        },
        "homonyms": {
            "totals": dict(homonym_stats["totals"]),
            "coord_count_histogram": {
                str(k): v for k, v in sorted(homonym_stats["coord_count_histogram"].items())
            },
            "multi_coordinate_share_pct": round(
                100.0
                * homonym_stats["totals"]["multi_coordinate_names"]
                / max(1, homonym_stats["totals"]["distinct_names"]),
                4,
            ),
            "definition": (
                "exact NAME_CH string equality, empty names excluded, no TYPE_CH qualification; "
                "a name counts as multi-coordinate when it occurs at 2 or more distinct exact "
                "(X_COOR,Y_COOR) pairs"
            ),
        },
        "mcgd": {
            "source_rows": mcgd_rows,
            "places": bundle_stats.get("place_counts", {}).get("mcgd", 0),
            "header_matches_expected": mcgd_header_ok,
        },
        "cross_layer_disagreements": {
            **(dict(cross_layer_stats["totals"]) if cross_layer_stats else {}),
            "definition": (
                "same NAME_CH and the same raw (BEG_YR,END_YR) pair present in BOTH chgis_pref "
                "and chgis_cnty but at different coordinates"
            ),
            "examples": [
                {
                    "name": entry.name,
                    "year_span": f"{entry.beg_yr}-{entry.end_yr}",
                    "prefecture_coords": entry.prefecture_coords,
                    "county_coords": entry.county_coords,
                    "max_separation_m": round(entry.max_separation_m, 1),
                }
                for entry in list(cross_layer)[:10]
            ],
        },
        "migration": migration or {},
        "review_queue": {
            "rows": len(review_queue),
            "priority_counts": dict(
                sorted(Counter(entry.priority for entry in review_queue).items())
            ),
            "definition": (
                "one row per accepted location_migration_candidate leg; sorted by "
                "priority ASC (P1 -> P2 -> P3), then leg_distance_m DESC, then "
                "gap_years ASC, so the file opens on the legs that most need a human. "
                "A distance-descending view is still available by sorting the "
                "leg_distance_m column. priority: P1 = leg>100km and "
                "confidence=high; P2 = (50-100km and high) or (>100km and medium); "
                "P3 = everything else"
            ),
            "confidence_meaning": (
                "confidence reflects year-gap tightness ONLY -- it is not an "
                "assessment of whether the migration really happened"
            ),
            "top_5_by_distance": [
                {
                    "priority": entry.priority,
                    "name_ch": entry.name_ch,
                    "source_dataset": entry.source_dataset,
                    "leg_distance_m": round(entry.leg_distance_m, 1),
                    "gap_years": entry.gap_years,
                    "confidence": entry.confidence,
                }
                for entry in list(review_queue)[:5]
            ],
        },
        "sources": _build_sources_section(extra_extractions, sysid_per_dataset, mcgd_rows),
        "time_bound_type": {
            "vocabulary": list(TIME_BOUND_TYPES),
            "distribution": dict(
                sorted(bundle_stats.get("time_bound_type_counts", {}).items())
            ),
            "denominator": bundle_stats.get("time_bound_type_denominator", {}),
            "place_level_distribution": dict(
                sorted(bundle_stats.get("place_time_bound_type_counts", {}).items())
            ),
            "place_level_derivation": dict(
                sorted(bundle_stats.get("place_time_derivation_counts", {}).items())
            ),
            "snapshot_basis_counts": dict(
                sorted(bundle_stats.get("snapshot_basis_counts", {}).items())
            ),
            "descriptions": dict(TIME_BOUND_TYPE_DESCRIPTIONS),
            "note": (
                "time_bound_type replaced time_basis in pipeline revision 1.2.0; it "
                "states what kind of claim the two year columns make, not how tight "
                "the interval is"
            ),
        },
        "data_datasets": {
            "rows": bundle_stats.get("data_datasets_rows", 0),
            "dataset_ids": bundle_stats.get("data_datasets_ids", []),
        },
        "tables": bundle_stats,
    }


def build_manifest_payload(
    *,
    project_root: Path,
    run_started_utc: str,
    run_finished_utc: str,
    duration_seconds: float,
    ingested_at: str,
    input_paths: Sequence[Path],
    input_sha256: Dict[str, str],
    output_paths: Sequence[Path],
    output_row_counts: Dict[str, int],
    step_timings: Sequence[Dict[str, Any]],
    astro_assertions: Sequence[str],
    pip_freeze_note: str,
) -> Dict[str, Any]:
    """Assemble ``run_manifest.json``.

    ``run_manifest.json`` itself is excluded from the output digest list, because
    a file cannot contain its own hash.
    """
    outputs = []
    for path in output_paths:
        outputs.append(
            {
                "path": str(path.relative_to(project_root)).replace("\\", "/"),
                "bytes": file_size(path),
                "sha256": file_sha256(path),
                "rows": output_row_counts.get(str(path), 0),
            }
        )
    return {
        "pipeline_version": PIPELINE_VERSION,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "run_started_utc": run_started_utc,
        "run_finished_utc": run_finished_utc,
        "duration_seconds": round(duration_seconds, 3),
        "ingested_at": ingested_at,
        "third_party_packages": pip_freeze_note,
        "steps": list(step_timings),
        "astro_year_assertions": list(astro_assertions),
        "inputs": [
            {
                "path": str(path.relative_to(project_root)).replace("\\", "/"),
                "bytes": file_size(path),
                "sha256": input_sha256.get(str(path), ""),
            }
            for path in input_paths
        ],
        "outputs": outputs,
        "reproducibility": (
            "Run twice with the same --timestamp value and all 16 data outputs (7 normalized "
            "tables + 8 issues files + stats.json) are byte-identical. This manifest is the only "
            "file that differs, and only in run_started_utc, run_finished_utc, duration_seconds "
            "and its own digests."
        ),
    }
