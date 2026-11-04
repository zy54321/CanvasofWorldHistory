"""Pleiades GIS CSV slice extraction (WB-002 task B).

The sample lives in ``设计资料/P0收敛/WB-002/sample_data_pleiades/`` and consists
of five HTTP Range slices, each cut at a fixed byte limit.  Three facts about the
slices drive the whole module:

**1. Every slice except ``time_periods.csv`` ends mid-record.**
Each file was fetched with ``bytes=0-1048575`` (or ``bytes=0-524287``), so the
final CSV record has fewer fields than the header.  That record is *truncated
data*, not a data defect, and it is discarded and counted as
``issue_type='truncated_slice_tail'`` rather than being coerced into a row.

**2. Axis order comes from two different conventions in the same dataset.**
``places.csv`` carries *named* columns ``representative_latitude`` /
``representative_longitude``; ``location_points.csv`` carries WKT, and WKT is
X Y.  ``gis_README.md`` line 13 states plainly "Set X =
``representative_longitude`` and Y = ``representative_latitude``", so WKT X is
longitude.  Getting this backwards would mirror the whole ancient world.

**3. The time columns are TPQ/TAQ, and there is no year zero.**
``gis_README.md`` documents ``year_after_which`` as terminus post quem and
``year_before_which`` as terminus ante quem, and states "There is no year zero".
So the values use the same convention as CHGIS and go through the same
astronomical conversion.  ``places.csv`` in the shipped slice has **no** time
columns at all, even though the README says the fields apply to it -- the
place-level bound therefore has to be aggregated from child rows.
"""

from __future__ import annotations

import csv
import hashlib
import io
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from datasets import PLEIADES_ATTRIBUTION
from extra_record import ExtraExtraction, ExtraRecord, parse_wkt_point, wkt_has_z
from time_semantics import parse_signed_year

__all__ = [
    "PLEIADES_SOURCE_ID",
    "PLEIADES_SOURCE_DATASET",
    "PLEIADES_DATASET_ID",
    "PLEIADES_ATTRIBUTION",
    "PLEIADES_SLICE_DIR",
    "SLICE_FILES",
    "extract_pleiades",
    # M4-4a
    "PLEIADES_FULL_SOURCE_DATASET",
    "PLEIADES_FULL_DATASET_ID",
    "PLEIADES_FULL_DIR",
    "extract_pleiades_full",
]

#: ``source_id`` written on every Pleiades row.
PLEIADES_SOURCE_ID = "pleiades"

#: ``source_dataset`` written on every Pleiades row.
PLEIADES_SOURCE_DATASET = "pleiades_gis_4_1_slice"

#: Registry id; kept equal to ``source_dataset`` because the slice is one
#: dataset with one licence.
PLEIADES_DATASET_ID = "pleiades_gis_4_1_slice"

#: Directory of the slices, relative to the project root.
PLEIADES_SLICE_DIR = Path("设计资料") / "P0收敛" / "WB-002" / "sample_data_pleiades"

#: ``(logical name, physical file name, record kind)`` for every slice, in the
#: order that fixes row numbering.  ``time_periods`` is a reference vocabulary.
SLICE_FILES: Tuple[Tuple[str, str, str], ...] = (
    ("places", "places.csv.range-0-1048575", "place"),
    ("names", "names.csv.range-0-1048575", "name"),
    ("location_points", "location_points.csv.range-0-1048575", "location"),
    ("connections", "connections.csv.range-0-524287", "connection"),
    ("time_periods", "time_periods.csv.range-0-999999", "reference"),
)

#: Pleiades ``name_type`` -> the staging vocabulary.  Anything not listed is an
#: alternate name; ``geographic`` is the dataset's default toponym class.
_NAME_TYPE_MAP: Dict[str, str] = {
    "geographic": "primary",
    "label": "alternate",
    "ethnic": "alternate",
    "associated_modern": "alternate",
    "undefined": "alternate",
    "unknown": "alternate",
}


def _read_csv_slice(
    path: Path, label: str
) -> Tuple[List[str], List[Dict[str, str]], List[Dict[str, Any]], str]:
    """Parse one truncated CSV slice.

    Args:
      path: Physical file path.
      label: Logical file name used in messages and stats.

    Returns:
      ``(header, rows, discarded, sha256)``.  ``rows`` are complete records.
      ``discarded`` holds one dict per rejected record with the parsed field
      count, the expected field count, and the leading cells, so the rejection
      is auditable rather than mysterious.
    """
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header: List[str] = []
    rows: List[Dict[str, str]] = []
    discarded: List[Dict[str, Any]] = []
    for position, values in enumerate(reader):
        if position == 0:
            header = list(values)
            continue
        if len(values) == len(header):
            rows.append(dict(zip(header, values)))
        else:
            discarded.append(
                {
                    "file": path.name,
                    "label": label,
                    "parsed_fields": len(values),
                    "expected_fields": len(header),
                    "leading_cells": " | ".join(values[:3])[:200],
                }
            )
    return header, rows, discarded, digest


def _pick_name(columns: Dict[str, str]) -> Tuple[str, str]:
    """Choose the display name for a ``names.csv`` row.

    Preference order is attested form, then the first romanised form, then the
    Pleiades ``title`` (which is a label, not necessarily the attested spelling).
    The choice is recorded so a reviewer knows which column was used.

    Returns:
      ``(name, basis)``.
    """
    for column in ("attested_form", "romanized_form_1", "romanized_form_2", "title"):
        value = (columns.get(column) or "").strip()
        if value:
            return value, column
    return "", "none"


def extract_pleiades(project_root: Path) -> ExtraExtraction:
    """Read every Pleiades slice and normalise it.

    Args:
      project_root: Project root containing ``设计资料/``.

    Returns:
      An :class:`ExtraExtraction` whose ``records`` mix ``place``, ``name``,
      ``location``, ``connection`` and ``reference`` kinds.  The caller groups by
      kind; nothing here decides identity.

    Raises:
      SystemExit: If the slice directory is missing, because silently continuing
        would produce an empty source that looks like a legitimate zero.
    """
    slice_dir = project_root / PLEIADES_SLICE_DIR
    if not slice_dir.is_dir():
        raise SystemExit(f"Pleiades slice directory not found: {slice_dir}")

    extraction = ExtraExtraction(
        source_id=PLEIADES_SOURCE_ID,
        source_dataset=PLEIADES_SOURCE_DATASET,
        dataset_id=PLEIADES_DATASET_ID,
        attribution_note=(
            "Licence CC BY 3.0 covers the whole data/gis directory "
            "(datasets_docs/LICENSE_CC-BY-3.0.txt); the repository README states "
            "'All content is distributed under the terms of a Creative Commons "
            "Attribution license (cc-by)'."
        ),
    )
    records: List[ExtraRecord] = []
    discarded_total = 0
    per_kind: Dict[str, int] = {}
    name_type_counts: Dict[str, int] = {}
    time_bound_counts: Dict[str, int] = {}

    # Place ids present in the places.csv slice.  Child rows referring to any
    # other id are real Pleiades rows whose parent simply fell outside the 1 MB
    # window, so they are kept in source_records and flagged, never dropped.
    place_ids: set = set()

    for logical, file_name, kind in SLICE_FILES:
        path = slice_dir / file_name
        if not path.is_file():
            raise SystemExit(f"Pleiades slice file missing: {path}")
        header, rows, discarded, digest = _read_csv_slice(path, logical)
        discarded_total += len(discarded)
        per_kind[logical] = len(rows)
        extraction.slice_files.append(
            {
                "file": file_name,
                "label": logical,
                "bytes": path.stat().st_size,
                "columns": len(header),
                "parsed_rows": len(rows),
                "discarded_rows": len(discarded),
                "sha256": digest,
                "header": header,
            }
        )
        extraction.stats.setdefault("discarded_tail_rows", []).extend(discarded)

        raw_file = f"sample_data_pleiades/{file_name}"
        for index, row in enumerate(rows, start=1):
            if kind == "place":
                place_ids.add((row.get("id") or "").strip())

        for index, row in enumerate(rows, start=1):
            if kind == "place":
                record = _build_place(row, index, raw_file)
            elif kind == "name":
                record = _build_name(row, index, raw_file)
            elif kind == "location":
                record = _build_location(row, index, raw_file)
            elif kind == "connection":
                record = _build_connection(row, index, raw_file)
            else:
                record = _build_reference(row, index, raw_file)
            records.append(record)
            if kind == "name":
                chosen = record.name_type
                name_type_counts[chosen] = name_type_counts.get(chosen, 0) + 1
            if kind in ("name", "location", "connection"):
                time_bound_counts[record.time_bound_type] = (
                    time_bound_counts.get(record.time_bound_type, 0) + 1
                )

    # Second pass: flag children whose parent place is outside the slice.
    not_in_sample = 0
    for record in records:
        if record.record_kind == "place":
            continue
        if record.parent_external_id and record.parent_external_id not in place_ids:
            not_in_sample += 1
            record.quality_flags.append("parent_place_not_in_sample")

    placement = {record.record_kind for record in records}
    missing_coord = sum(
        1
        for record in records
        if record.record_kind == "place" and not record.has_coordinate
    )
    z_points = sum(
        1 for record in records if record.record_kind == "location" and wkt_has_z(record.geom_wkt)
    )

    extraction.records = records
    extraction.stats.update(
        {
            "source_id": PLEIADES_SOURCE_ID,
            "dataset_id": PLEIADES_DATASET_ID,
            "from_slice": "1MB_head",
            "record_kinds": per_kind,
            "record_kind_total": len(records),
            "place_ids_in_places_slice": len(place_ids),
            "discarded_tail_row_count": discarded_total,
            "parent_place_not_in_sample_rows": not_in_sample,
            "places_without_coordinate": missing_coord,
            "location_points_with_z_ordinate": z_points,
            "name_type_counts": dict(sorted(name_type_counts.items())),
            "child_time_bound_type_counts": dict(sorted(time_bound_counts.items())),
            "places_table_has_time_columns": False,
            "places_table_time_note": (
                "places.csv in the shipped slice carries no year_after_which / "
                "year_before_which columns, although gis_README.md lists those "
                "fields as applying to places.csv; place-level bounds are "
                "therefore aggregated from names.csv and location_points.csv "
                "(time_derivation='tpq_taq_of_children')"
            ),
            "year_zero_convention": (
                "gis_README.md: 'a signed integer indicating a year in the "
                "proleptic Julian calendar. There is no year zero.' -- the same "
                "convention as CHGIS, so astro_year() applies unchanged"
            ),
            "qualities_present": sorted(placement),
        }
    )
    return extraction



def _pleiades_time_bound_type(tpq, taq):
    """Classify a Pleiades ``(year_after_which, year_before_which)`` pair.

    ``year_after_which`` is terminus post quem and ``year_before_which`` is
    terminus ante quem, so the pair is a *bound*, not an attested span.  One
    degenerate case needs its own label: when the two bounds are the same year
    the interval collapses to a point, and calling that ``tpq_taq`` invites a
    reader to see a 0-year span; calling it ``exact`` is worse, because the
    source never claimed the entity existed only in that year.  ``bounded`` is
    the label that says "a bound, whose two ends happen to coincide".
    In the shipped slice this affects exactly two rows (both ``1500-1500``).

    Args:
      tpq: Parsed terminus post quem, or ``None``.
      taq: Parsed terminus ante quem, or ``None``.

    Returns:
      One of ``tpq_taq`` / ``bounded`` / ``unknown``.
    """
    if tpq is None and taq is None:
        return "unknown"
    if tpq is not None and taq is not None and tpq == taq:
        return "bounded"
    return "tpq_taq"


def _coerce_float(text: str) -> Optional[float]:
    """Parse a coordinate string, returning ``None`` for blank or malformed."""
    stripped = (text or "").strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _build_place(row: Dict[str, str], index: int, raw_file: str) -> ExtraRecord:
    """Normalise one ``places.csv`` row into a ``place`` record."""
    lon = _coerce_float(row.get("representative_longitude", ""))
    lat = _coerce_float(row.get("representative_latitude", ""))
    flags: List[str] = []
    if lon is None or lat is None:
        flags.append("missing_coordinate")
    else:
        if not (-180.0 <= lon <= 180.0):
            flags.append("coordinate_out_of_range")
        if not (-90.0 <= lat <= 90.0):
            flags.append("coordinate_out_of_range")
    record = ExtraRecord(
        dataset_id=PLEIADES_DATASET_ID,
        source_id=PLEIADES_SOURCE_ID,
        source_dataset=PLEIADES_SOURCE_DATASET,
        record_kind="place",
        record_index=index,
        raw_file=raw_file,
        raw={k: v for k, v in row.items()},
        external_id=(row.get("id") or "").strip(),
        external_id_type="pleiades_place_id",
        name=(row.get("title") or "").strip(),
        name_lang="und",
        name_script="",
        name_type="primary",
        place_type="unknown",
        lon=lon,
        lat=lat,
        lon_text=(row.get("representative_longitude") or "").strip(),
        lat_text=(row.get("representative_latitude") or "").strip(),
        geom_wkt="",
        location_precision=(row.get("location_precision") or "").strip(),
        uncertainty_m="",
        time_bound_type="unknown",
        valid_from_year=None,
        valid_to_year=None,
        time_rule_code="",
        quality_flags=flags,
        notes=(
            "Pleiades place (places.csv). axis_order_verified: X/Y are taken from the "
            "*named* columns representative_longitude / "
            "representative_latitude, matching gis_README.md line 13 'Set X = "
            "representative_longitude and Y = representative_latitude'. "
            "no time columns in this file so time_bound_type='unknown' here and the "
            "place-level bound is aggregated from child rows. "
            f"place_type_left_unknown: Pleiades has no place-type column in the GIS "
            f"export; location_precision is the dataset's own word "
            f"({(row.get('location_precision') or '').strip() or '<blank>'})."
            + (
                " bounding_box_wkt kept in raw_payload_json (a polygon, not "
                "promoted to a location row)"
                if (row.get("bounding_box_wkt") or "").strip()
                else ""
            )
        ),
    )
    return record


def _build_name(row: Dict[str, str], index: int, raw_file: str) -> ExtraRecord:
    """Normalise one ``names.csv`` row, which carries a TPQ/TAQ pair."""
    name, basis = _pick_name(row)
    raw_type = (row.get("name_type") or "").strip()
    tpq = parse_signed_year(row.get("year_after_which", ""))
    taq = parse_signed_year(row.get("year_before_which", ""))
    bound_type = _pleiades_time_bound_type(tpq, taq)
    flags: List[str] = []
    if not name:
        flags.append("empty_name")
    language = (row.get("language_tag") or "").strip() or "und"
    return ExtraRecord(
        dataset_id=PLEIADES_DATASET_ID,
        source_id=PLEIADES_SOURCE_ID,
        source_dataset=PLEIADES_SOURCE_DATASET,
        record_kind="name",
        record_index=index,
        raw_file=raw_file,
        raw={k: v for k, v in row.items()},
        external_id=(row.get("id") or "").strip(),
        external_id_type="pleiades_name_id",
        parent_external_id=(row.get("place_id") or "").strip(),
        name=name,
        name_lang=language,
        name_script="",
        name_type=_NAME_TYPE_MAP.get(raw_type, "alternate"),
        place_type="unknown",
        time_bound_type=bound_type,
        valid_from_year=tpq,
        valid_to_year=taq,
        time_rule_code="year_after_which|year_before_which",
        quality_flags=flags,
        notes=(
            f"Pleiades name (names.csv). display name taken from '{basis}'; "
            f"pleiades_name_type={raw_type or '<blank>'}; "
            "year_after_which is terminus post quem and year_before_which is "
            "terminus ante quem per gis_README.md, so the pair is a bound, not an "
            "attested span"
            + (
                "; the two bounds are the same year, so the pair is labelled "
                "'bounded' rather than 'tpq_taq' to avoid reading a coincident "
                "bound as a 0-year existence claim"
                if bound_type == "bounded"
                else ""
            )
            + (
                "; language_tag blank in source, stored as 'und'"
                if not (row.get("language_tag") or "").strip()
                else ""
            )
        ),
    )


def _build_location(row: Dict[str, str], index: int, raw_file: str) -> ExtraRecord:
    """Normalise one ``location_points.csv`` row (WKT geometry)."""
    wkt = (row.get("geometry_wkt") or "").strip()
    point = parse_wkt_point(wkt)
    lon = point[0] if point else None
    lat = point[1] if point else None
    flags: List[str] = []
    if lon is None or lat is None:
        flags.append("missing_coordinate")
    else:
        if not (-180.0 <= lon <= 180.0):
            flags.append("coordinate_out_of_range")
        if not (-90.0 <= lat <= 90.0):
            flags.append("coordinate_out_of_range")
    if wkt_has_z(wkt):
        flags.append("z_ordinate_discarded")
    tpq = parse_signed_year(row.get("year_after_which", ""))
    taq = parse_signed_year(row.get("year_before_which", ""))
    bound_type = _pleiades_time_bound_type(tpq, taq)
    accuracy = (row.get("accuracy_radius") or "").strip()
    return ExtraRecord(
        dataset_id=PLEIADES_DATASET_ID,
        source_id=PLEIADES_SOURCE_ID,
        source_dataset=PLEIADES_SOURCE_DATASET,
        record_kind="location",
        record_index=index,
        raw_file=raw_file,
        raw={k: v for k, v in row.items()},
        external_id=(row.get("id") or "").strip(),
        external_id_type="pleiades_location_id",
        parent_external_id=(row.get("place_id") or "").strip(),
        name=(row.get("title") or "").strip(),
        name_lang="und",
        name_script="",
        name_type="alternate",
        place_type="unknown",
        lon=lon,
        lat=lat,
        lon_text=f"{point[0]}" if point else "",
        lat_text=f"{point[1]}" if point else "",
        geom_wkt=wkt,
        location_precision=(row.get("location_precision") or "").strip(),
        uncertainty_m=accuracy,
        time_bound_type=bound_type,
        valid_from_year=tpq,
        valid_to_year=taq,
        time_rule_code="year_after_which|year_before_which",
        quality_flags=flags,
        notes=(
            "Pleiades location point (location_points.csv). geometry_wkt is WKT, whose "
            "axis order is X Y = longitude latitude; gis_README.md line 13 confirms X "
            "= representative_longitude, so no axis swap is applied. "
            "one-to-many: several location rows can share one place_id. "
            "accuracy_radius, when present, is the source's own horizontal accuracy in "
            "metres and is copied into uncertainty_m verbatim"
            + ("; the WKT carries a Z ordinate which was discarded as this table is 2D"
               if wkt_has_z(wkt) else "")
        ),
    )


def _build_connection(row: Dict[str, str], index: int, raw_file: str) -> ExtraRecord:
    """Normalise one ``connections.csv`` row."""
    target = (row.get("connects_to") or "").strip()
    target_id = target.rstrip("/").rsplit("/", 1)[-1] if target else ""
    tpq = parse_signed_year(row.get("year_after_which", ""))
    taq = parse_signed_year(row.get("year_before_which", ""))
    bound_type = _pleiades_time_bound_type(tpq, taq)
    return ExtraRecord(
        dataset_id=PLEIADES_DATASET_ID,
        source_id=PLEIADES_SOURCE_ID,
        source_dataset=PLEIADES_SOURCE_DATASET,
        record_kind="connection",
        record_index=index,
        raw_file=raw_file,
        raw={k: v for k, v in row.items()},
        external_id=(row.get("id") or "").strip(),
        external_id_type="pleiades_connection_id",
        parent_external_id=(row.get("place_id") or "").strip(),
        name=(row.get("title") or "").strip(),
        name_lang="und",
        name_script="",
        name_type="alternate",
        place_type="unknown",
        time_bound_type=bound_type,
        valid_from_year=tpq,
        valid_to_year=taq,
        time_rule_code="year_after_which|year_before_which",
        notes=(
            "Pleiades connection (connections.csv). connection_type is the source's own "
            "edge label; connects_to is an absolute Pleiades URI and the trailing path "
            "segment is extracted as the target place id. Stored as a source assertion: "
            "it is neither merged nor turned into a place."
        ),
        connection_type=(row.get("connection_type") or "").strip(),
        connects_to_external_id=target_id,
    )


def _build_reference(row: Dict[str, str], index: int, raw_file: str) -> ExtraRecord:
    """Normalise one ``time_periods.csv`` row (reference vocabulary)."""
    return ExtraRecord(
        dataset_id=PLEIADES_DATASET_ID,
        source_id=PLEIADES_SOURCE_ID,
        source_dataset=PLEIADES_SOURCE_DATASET,
        record_kind="reference",
        record_index=index,
        raw_file=raw_file,
        raw={k: v for k, v in row.items()},
        external_id=(row.get("key") or "").strip(),
        external_id_type="pleiades_time_period_key",
        name=(row.get("term") or "").strip(),
        name_lang="en",
        name_script="Latn",
        name_type="alternate",
        place_type="unknown",
        notes=(
            "Pleiades time-period vocabulary row. Reference data only: no place, no "
            "location, no candidate row is created from it. lower_bound/upper_bound are "
            "free-text ('2600000 BC') and are NOT parsed into years."
        ),
    )


# ===========================================================================
# M4-4a：Pleiades GIS 4.1 全量数据集
# ===========================================================================
#
# 与上面的 1 MB 切片抽取器并列存在、互不调用改动：
#
#   ``extract_pleiades()``       读 ``设计资料/P0收敛/WB-002/sample_data_pleiades/``
#                                的 5 个 HTTP Range 切片，产出 12,445 条记录，
#                                数据集 ``pleiades_gis_4_1_slice``。
#   ``extract_pleiades_full()``  读 ``code/data/raw/pleiades_gis_4_1/gis/`` 的
#                                完整 19 文件包，产出 ``pleiades_gis_4_1`` 数据集。
#
# 全量分支多出来的四件事，全部有明确数据依据：
#
#   1. **几何是三种，不是一种。** points / linestrings / polygons 三个文件各有
#      自己的 WKT 列，必须分别落到 Point / LineString / Polygon（修复后可能是
#      MultiPolygon）。切片只有 points。
#   2. **无效多边形要修。** 整包 5 条 ``ST_IsValid=false``，其中 4 条属于 NEW
#      集合。修复规则与 PostGIS ``ST_MakeValid`` + ``ST_CollectionExtract(...,3)``
#      等价（同为 GEOS），结果类型按实际面片数写 Polygon 或 MultiPolygon。
#   3. **代表点要合成。** 3,317 个 NEW 地点有 ``representative_latitude/longitude``
#      却没有任何 location 行。``historical_place`` 没有坐标列，地图只认
#      ``historical_place_location.representative_lon/lat``，不合成则不可见。
#      合成行使用 places.csv 的原始坐标，**不用 bbox 中心替代**。
#   4. **连接全量保留。** 13,603 行一行不少；两端解析不到的一律打
#      ``connection_endpoint_missing`` 标记，由 normalize 开台账，不在这里丢弃。

#: ``source_dataset`` / ``dataset_id`` of the full v4.1 dataset.
PLEIADES_FULL_SOURCE_DATASET = "pleiades_gis_4_1"
PLEIADES_FULL_DATASET_ID = "pleiades_gis_4_1"

#: Directory of the extracted v4.1 GIS files, relative to the **code root**
#: (i.e. ``code/``), because that is where the archive was unpacked.
PLEIADES_FULL_DIR = Path("data") / "raw" / "pleiades_gis_4_1" / "gis"

#: ``(logical name, physical file name)`` in reading order.  The order fixes
#: ``source_record_id`` allocation, and inside it the location order is
#: points -> representative points -> linestrings -> polygons so that
#: ``ORDER BY location_id LIMIT 1`` in the map query always sees the most
#: precise row first.
FULL_FILES: Tuple[Tuple[str, str], ...] = (
    ("places", "places.csv"),
    ("names", "names.csv"),
    ("location_points", "location_points.csv"),
    ("location_linestrings", "location_linestrings.csv"),
    ("location_polygons", "location_polygons.csv"),
    ("connections", "connections.csv"),
    ("places_accuracy", "places_accuracy.csv"),
    ("places_place_types", "places_place_types.csv"),
)

#: Geometry kind implied by each location file.
LOCATION_FILE_KIND: Dict[str, str] = {
    "location_points": "Point",
    "location_linestrings": "LineString",
    "location_polygons": "Polygon",
}

#: ``places_accuracy.min_accuracy_meters`` uses ``-1`` to mean "unknown".
ACCURACY_UNKNOWN_SENTINEL = -1.0


def _shapely_modules():
    """Import shapely, falling back to the vendored ``code/ops/.deps`` copy.

    Only the full-dataset extractor needs a geometry engine.  The slice
    extractor stays standard-library-only, which is why the import is lazy: a
    machine that only runs the old pipeline keeps working unchanged.

    Returns:
      ``(shapely, shapely.wkt)`` module pair.

    Raises:
      SystemExit: When shapely is absent even from the vendor directory, because
        continuing would silently mis-handle 4,385 polygons and 5,265 lines.
    """
    try:
        import shapely  # noqa: PLC0415 - deliberate lazy import
        from shapely import wkt as shapely_wkt  # noqa: PLC0415

        return shapely, shapely_wkt
    except ImportError:
        vendor = Path(__file__).resolve().parents[2] / "ops" / ".deps"
        if vendor.is_dir() and str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))
        try:
            import shapely  # noqa: PLC0415
            from shapely import wkt as shapely_wkt  # noqa: PLC0415

            return shapely, shapely_wkt
        except ImportError as exc:  # pragma: no cover - environment problem
            raise SystemExit(
                "Pleiades 全量几何处理需要 shapely；已在 sys.path 追加 "
                f"{vendor} 仍无法导入：{exc}"
            ) from exc


def _read_full_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]], str, int, List[Dict[str, Any]]]:
    """Parse one *complete* CSV file of the v4.1 package.

    Unlike :func:`_read_csv_slice` there is no truncation to explain, so a short
    record is a genuine defect and is reported rather than explained away.

    Returns:
      ``(header, rows, sha256, bytes, short_records)``.
    """
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header: List[str] = next(reader, [])
    rows: List[Dict[str, str]] = []
    short: List[Dict[str, Any]] = []
    for position, values in enumerate(reader, start=2):
        if len(values) == len(header):
            rows.append(dict(zip(header, values)))
        else:
            short.append(
                {
                    "file": path.name,
                    "physical_line": position,
                    "parsed_fields": len(values),
                    "expected_fields": len(header),
                    "leading_cells": " | ".join(values[:3])[:200],
                }
            )
    return header, rows, digest, len(raw), short


def _place_key(value: str) -> str:
    """Normalise a place reference to its bare id.

    ``connects_to`` is an absolute URI (``https://pleiades.stoa.org/places/433032``)
    while ``place_id`` columns hold the bare id, so comparing them without
    normalising invents 13,603 false orphans.  ``/errata/991384`` is not a place
    and normalises to ``991384``, which simply fails the "is a known place"
    test downstream -- that is the intended outcome.
    """
    text = (value or "").strip()
    if not text:
        return ""
    if "/" in text:
        return text.rstrip("/").rsplit("/", 1)[-1]
    return text


def _has_z_dimension(wkt: str) -> bool:
    """True when a WKT of any geometry type declares or carries a Z ordinate."""
    text = (wkt or "").strip()
    if not text:
        return False
    head = text[: text.find("(")] if "(" in text else text
    if "Z" in head.upper().split():
        return True
    return wkt_has_z(text)


def _wkt_2d(shapely, shapely_wkt, text: str):
    """Parse WKT and force it to two dimensions.

    ``historical_place_location.geom`` is ``geometry(Geometry,4326)`` -- 2D.  The
    package carries 8 ``POINT Z``, 11 ``LINESTRING Z`` and 91 ``POLYGON Z`` rows,
    so the Z ordinate is dropped *explicitly* and flagged on the row rather than
    left for PostGIS to reject.

    Returns:
      The parsed 2D geometry, or ``None`` when the text is not parseable.
    """
    try:
        geom = shapely_wkt.loads(text)
    except Exception:  # noqa: BLE001 - GEOS raises several unrelated types
        return None
    if geom.is_empty:
        return None
    if geom.has_z:
        geom = shapely.force_2d(geom)
    return geom


def _polygon_payload(shapely, geom) -> Tuple[str, Any]:
    """Classify a polygon after repair.

    ``ST_MakeValid`` can return a GeometryCollection (a polygon plus dangling
    lines) or a MultiPolygon.  ``ST_CollectionExtract(...,3)`` keeps only the
    polygonal parts, and the stored ``geom_type`` must match what is left: one
    part -> ``Polygon``, several parts -> ``MultiPolygon``.

    Returns:
      ``(geom_type, geometry)`` with ``geom_type`` empty when no polygonal part
      survives.
    """
    parts = [part for part in shapely.get_parts(geom) if part.geom_type == "Polygon"]
    if not parts:
        return "", None
    if len(parts) == 1:
        return "Polygon", parts[0]
    return "MultiPolygon", shapely.MultiPolygon(parts)


def _location_geometry(wkt: str, file_kind: str) -> Dict[str, Any]:
    """Turn one location row's WKT into the staging fields that describe it.

    Args:
      wkt: Verbatim ``geometry_wkt`` cell.
      file_kind: ``Point`` / ``LineString`` / ``Polygon`` -- the file the row
        came from, which must agree with the WKT type.

    Returns:
      A dict with ``geom_type`` (may be ``MultiPolygon`` after repair),
      ``geom_wkt`` (2D, repaired when needed), ``lon``/``lat`` (representative
      point), ``flags`` and ``note``.  ``geom_type`` is ``""`` when the row
      cannot be used, in which case ``flags`` explains why.
    """
    text = (wkt or "").strip()
    flags: List[str] = []
    note_parts: List[str] = []
    if not text:
        return {"geom_type": "", "geom_wkt": "", "lon": None, "lat": None,
                "flags": ["empty_geometry"], "note": "geometry_wkt 为空"}

    if _has_z_dimension(text):
        flags.append("z_ordinate_discarded")
        note_parts.append("原始 WKT 带 Z 序，已降为二维（表列是 geometry(Geometry,4326)）")

    if file_kind == "Point":
        point = parse_wkt_point(text)
        lon = point[0] if point else None
        lat = point[1] if point else None
        if lon is None or lat is None:
            return {"geom_type": "", "geom_wkt": text, "lon": None, "lat": None,
                    "flags": flags + ["missing_coordinate"],
                    "note": "POINT WKT 无法解析出 x/y"}
        return {"geom_type": "Point", "geom_wkt": text, "lon": lon, "lat": lat,
                "flags": flags, "note": "; ".join(note_parts)}

    shapely, shapely_wkt = _shapely_modules()
    geom = _wkt_2d(shapely, shapely_wkt, text)
    if geom is None:
        return {"geom_type": "", "geom_wkt": text, "lon": None, "lat": None,
                "flags": flags + ["unparseable_geometry"],
                "note": "WKT 无法被 GEOS 解析或为空几何"}

    observed = geom.geom_type
    allowed = {"LineString"} if file_kind == "LineString" else {"Polygon", "MultiPolygon"}
    if observed not in allowed:
        return {"geom_type": "", "geom_wkt": text, "lon": None, "lat": None,
                "flags": flags + ["unexpected_geometry_type"],
                "note": (
                    f"{file_kind} 文件里出现 {observed}，与文件语义不符，未入库"
                    "（几何类型以 WKT 为准，但不接受跨文件类型混入）"
                )}

    if observed in ("Polygon", "MultiPolygon"):
        if not geom.is_valid:
            reason = shapely.is_valid_reason(geom)
            repaired = shapely.make_valid(geom)
            geom_type, cleaned = _polygon_payload(shapely, repaired)
            if cleaned is None:
                return {"geom_type": "", "geom_wkt": text, "lon": None, "lat": None,
                        "flags": flags + ["geometry_unrepairable"],
                        "note": f"ST_IsValid=false（{reason}），ST_MakeValid 后无面片残留"}
            flags.append("geometry_invalid_repaired")
            note_parts.append(
                f"源 WKT 无效（{reason}），经 GEOS MakeValid + 只取面片后修复为 {geom_type}"
            )
            geom = cleaned
            observed = geom_type
        else:
            geom_type = "Polygon"
        lon, lat = geom.representative_point().x, geom.representative_point().y
        note_parts.append("代表点由 ST_PointOnSurface 等价算法（面内点）在入库前算出")
    else:  # LineString
        geom_type = "LineString"
        point = geom.interpolate(0.5, normalized=True)
        lon, lat = point.x, point.y
        note_parts.append(
            "代表点由 ST_LineInterpolatePoint(geom, 0.5) 等价算法（线长中点）在入库前算出"
        )

    try:
        wkt_2d = shapely.to_wkt(geom, rounding_precision=-1, trim=True)
    except Exception:  # noqa: BLE001
        wkt_2d = text
    return {"geom_type": geom_type, "geom_wkt": wkt_2d, "lon": lon, "lat": lat,
            "flags": flags, "note": "; ".join(note_parts)}


def _full_location_record(
    row: Dict[str, str],
    index: int,
    raw_file: str,
    place_id: str,
    geometry: Dict[str, Any],
    synthetic: bool,
    accuracy_m: Optional[float],
) -> ExtraRecord:
    """Build one ``location`` record for the full dataset (real or synthesised)."""
    lon = geometry["lon"]
    lat = geometry["lat"]
    flags = list(geometry["flags"])
    if lon is None or lat is None:
        if "missing_coordinate" not in flags:
            flags.append("missing_coordinate")
    else:
        if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
            flags.append("coordinate_out_of_range")

    tpq = parse_signed_year(row.get("year_after_which", ""))
    taq = parse_signed_year(row.get("year_before_which", ""))
    bound_type = _pleiades_time_bound_type(tpq, taq)

    uncertainty = ""
    note_parts = [geometry["note"]] if geometry["note"] else []
    if synthetic:
        if accuracy_m is None or accuracy_m == ACCURACY_UNKNOWN_SENTINEL:
            flags.append("accuracy_unknown_sentinel")
            note_parts.append(
                "places_accuracy.min_accuracy_meters = -1（未知哨兵）⇒ uncertainty_m 写 NULL，"
                "并记 accuracy_unknown_sentinel 台账"
            )
        else:
            uncertainty = f"{accuracy_m:g}"
            note_parts.append(
                f"uncertainty_m 取自 places_accuracy.min_accuracy_meters={accuracy_m:g}"
            )
        note_parts.append(
            "representative point synthesised (A2): places.csv 的 "
            "representative_latitude/longitude 原样使用，未用 bounding_box 中心替代"
        )
    else:
        radius = (row.get("accuracy_radius") or "").strip()
        if radius and _coerce_float(radius) is not None:
            uncertainty = radius

    return ExtraRecord(
        dataset_id=PLEIADES_FULL_DATASET_ID,
        source_id=PLEIADES_SOURCE_ID,
        source_dataset=PLEIADES_FULL_SOURCE_DATASET,
        record_kind="location",
        record_index=index,
        raw_file=raw_file,
        raw={k: v for k, v in row.items()},
        external_id=(
            f"{place_id}-representative" if synthetic else (row.get("id") or "").strip()
        ),
        external_id_type=(
            "pleiades_representative_point" if synthetic else "pleiades_location_id"
        ),
        parent_external_id=place_id,
        name=(row.get("title") or "").strip(),
        name_lang="und",
        name_script="",
        name_type="alternate",
        place_type="unknown",
        lon=lon,
        lat=lat,
        lon_text=(f"{lon:.9f}".rstrip("0").rstrip(".") if lon is not None else ""),
        lat_text=(f"{lat:.9f}".rstrip("0").rstrip(".") if lat is not None else ""),
        geom_wkt=geometry["geom_wkt"],
        location_precision=(row.get("location_precision") or "").strip(),
        uncertainty_m=uncertainty,
        original_crs="EPSG:4326",
        crs_confidence="confirmed",
        time_bound_type=bound_type,
        valid_from_year=tpq,
        valid_to_year=taq,
        time_rule_code="year_after_which|year_before_which",
        quality_flags=flags,
        notes=(
            f"Pleiades v4.1 {geometry['geom_type'] or 'geometry'}"
            f"（{'合成代表点' if synthetic else raw_file}）。"
            "X/Y = longitude/latitude：WKT 轴序为 X Y，gis_README.md 亦写明 "
            "X=representative_longitude。"
            + ("；" + "；".join(note_parts) if note_parts else "")
        ),
    )


def extract_pleiades_full(
    gis_dir: Path,
    new_place_ids: Optional[Sequence[str]] = None,
    superseded_place_ids: Optional[Sequence[str]] = None,
) -> ExtraExtraction:
    """Read the complete Pleiades GIS 4.1 package and normalise it.

    The 2,552 places that already have a row in the older slice snapshot are
    *not* skipped: their ``place`` records are still emitted so that every one of
    the 41,480 source rows is traceable, but they are reported through
    ``stats['superseded_place_ids']`` so that the normaliser creates no second
    ``historical_places`` row for them.  Their child rows (names, locations) are
    not emitted at all, because the same place already carries the children that
    were imported from the slice -- importing them again would double every name
    without adding information (increment plan A).

    Args:
      gis_dir: Directory holding the 19 extracted files.
      new_place_ids: Place ids that will become new ``historical_places`` rows.
        ``None`` means "every place in the package".
      superseded_place_ids: Place ids that already exist in the slice snapshot.

    Returns:
      An :class:`ExtraExtraction` with place / name / location / connection
      records, ordered places -> names -> points -> representative points ->
      linestrings -> polygons -> connections.

    Raises:
      SystemExit: On a missing directory or file, because an empty extraction
        would look like a legitimate zero.
    """
    gis_dir = Path(gis_dir)
    if not gis_dir.is_dir():
        raise SystemExit(f"Pleiades v4.1 GIS directory not found: {gis_dir}")

    extraction = ExtraExtraction(
        source_id=PLEIADES_SOURCE_ID,
        source_dataset=PLEIADES_FULL_SOURCE_DATASET,
        dataset_id=PLEIADES_FULL_DATASET_ID,
        attribution_note=(
            "Pleiades Datasets v4.1 (Zenodo 15540082), data/gis CSV package; "
            "CC BY 3.0 per datasets_docs/LICENSE_CC-BY-3.0.txt. 授权由 Owner 负责，"
            "来源信息不参与任何准入判定。"
        ),
    )

    tables: Dict[str, List[Dict[str, str]]] = {}
    short_total = 0
    for logical, file_name in FULL_FILES:
        path = gis_dir / file_name
        if not path.is_file():
            raise SystemExit(f"Pleiades v4.1 file missing: {path}")
        header, rows, digest, size, short = _read_full_csv(path)
        tables[logical] = rows
        short_total += len(short)
        extraction.slice_files.append(
            {
                "file": file_name,
                "label": logical,
                "bytes": size,
                "columns": len(header),
                "parsed_rows": len(rows),
                "discarded_rows": len(short),
                "sha256": digest,
                "header": header,
            }
        )
        extraction.stats.setdefault("short_records", []).extend(short)

    place_rows = tables["places"]
    place_index: Dict[str, int] = {}
    for index, row in enumerate(place_rows, start=1):
        place_index[(row.get("id") or "").strip()] = index
    all_ids = set(place_index)
    all_ids.discard("")

    new_set = set(new_place_ids) if new_place_ids is not None else set(all_ids)
    sup_set = set(superseded_place_ids or ())
    unknown_new = sorted(new_set - all_ids)
    unknown_sup = sorted(sup_set - all_ids)
    if unknown_new or unknown_sup:
        raise SystemExit(
            "Pleiades 4.1 集合划分与 places.csv 不一致："
            f"NEW 中不存在的 id {len(unknown_new)} 个（示例 {unknown_new[:3]}）；"
            f"重叠集中不存在的 id {len(unknown_sup)} 个（示例 {unknown_sup[:3]}）"
        )
    if new_set & sup_set:
        raise SystemExit(
            f"NEW 与重叠集相交 {len(new_set & sup_set)} 个，集合划分不自洽"
        )

    # 地点级精度汇总，只用于合成代表点的 uncertainty_m
    min_accuracy: Dict[str, Optional[float]] = {}
    accuracy_precision: Dict[str, str] = {}
    for row in tables["places_accuracy"]:
        pid = (row.get("place_id") or "").strip()
        min_accuracy[pid] = _coerce_float(row.get("min_accuracy_meters", ""))
        accuracy_precision[pid] = (row.get("location_precision") or "").strip()

    # places.csv 与 places_accuracy.csv 的精度列是否一致（两文件都声明了该字段）
    precision_disagreements = 0
    for row in place_rows:
        pid = (row.get("id") or "").strip()
        own = (row.get("location_precision") or "").strip()
        other = accuracy_precision.get(pid, "")
        if other and own and own != other:
            precision_disagreements += 1

    # 多值类型：只有汇总文本可以承载，逐行关系留在归档（见 M4-3 承载矩阵 §四）
    place_types: Dict[str, List[str]] = defaultdict(list)
    for row in tables["places_place_types"]:
        pid = (row.get("place_id") or "").strip()
        value = (row.get("place_type") or "").strip()
        if pid and value:
            place_types[pid].append(value)
    for pid in place_types:
        place_types[pid] = sorted(set(place_types[pid]))

    # ---- 地名/位置/连接：子行只导 NEW 集合 ------------------------------
    have_location: set = set()
    name_records: List[ExtraRecord] = []
    point_records: List[ExtraRecord] = []
    line_records: List[ExtraRecord] = []
    polygon_records: List[ExtraRecord] = []
    geometry_counts: Counter = Counter()
    invalid_repaired: List[Dict[str, str]] = []
    skipped_unusable: List[Dict[str, str]] = []

    for index, row in enumerate(tables["names"], start=1):
        pid = _place_key(row.get("place_id"))
        if pid not in new_set:
            continue
        name, basis = _pick_name(row)
        raw_type = (row.get("name_type") or "").strip()
        tpq = parse_signed_year(row.get("year_after_which", ""))
        taq = parse_signed_year(row.get("year_before_which", ""))
        bound_type = _pleiades_time_bound_type(tpq, taq)
        flags: List[str] = []
        if not name:
            flags.append("empty_name")
        language = (row.get("language_tag") or "").strip() or "und"
        note_bits = [
            f"display name 取自 '{basis}'",
            f"pleiades_name_type={raw_type or '<blank>'}",
            "year_after_which=TPQ / year_before_which=TAQ（gis_README.md），区间是界不是实测跨度",
        ]
        if not (row.get("language_tag") or "").strip():
            note_bits.append("language_tag 空 ⇒ name_lang 写 und")
        if bound_type == "bounded":
            note_bits.append("两端同一年 ⇒ 记 bounded，不记 0 年 exact")
        name_records.append(
            ExtraRecord(
                dataset_id=PLEIADES_FULL_DATASET_ID,
                source_id=PLEIADES_SOURCE_ID,
                source_dataset=PLEIADES_FULL_SOURCE_DATASET,
                record_kind="name",
                record_index=index,
                raw_file="names.csv",
                raw={k: v for k, v in row.items()},
                external_id=(row.get("id") or "").strip(),
                external_id_type="pleiades_name_id",
                parent_external_id=pid,
                name=name,
                name_lang=language,
                name_script="",
                name_type=_NAME_TYPE_MAP.get(raw_type, "alternate"),
                place_type="unknown",
                time_bound_type=bound_type,
                valid_from_year=tpq,
                valid_to_year=taq,
                time_rule_code="year_after_which|year_before_which",
                quality_flags=flags,
                notes=("Pleiades v4.1 name (names.csv)；" + "；".join(note_bits)),
            )
        )

    for logical, target in (
        ("location_points", point_records),
        ("location_linestrings", line_records),
        ("location_polygons", polygon_records),
    ):
        file_kind = LOCATION_FILE_KIND[logical]
        raw_file = dict(FULL_FILES)[logical]
        for index, row in enumerate(tables[logical], start=1):
            pid = _place_key(row.get("place_id"))
            if pid not in new_set:
                continue
            geometry = _location_geometry(row.get("geometry_wkt", ""), file_kind)
            if not geometry["geom_type"]:
                skipped_unusable.append(
                    {
                        "file": raw_file,
                        "row": str(index),
                        "id": (row.get("id") or "").strip(),
                        "place_id": pid,
                        "flags": "|".join(geometry["flags"]),
                        "note": geometry["note"],
                    }
                )
                continue
            have_location.add(pid)
            geometry_counts[geometry["geom_type"]] += 1
            if "geometry_invalid_repaired" in geometry["flags"]:
                invalid_repaired.append(
                    {
                        "file": raw_file,
                        "row": str(index),
                        "id": (row.get("id") or "").strip(),
                        "place_id": pid,
                        "geom_type": geometry["geom_type"],
                        "note": geometry["note"],
                    }
                )
            target.append(
                _full_location_record(
                    row, index, raw_file, pid, geometry,
                    synthetic=False,
                    accuracy_m=min_accuracy.get(pid),
                )
            )

    # ---- A2：有代表点、却没有任何 location 行的 NEW 地点 ------------------
    rep_records: List[ExtraRecord] = []
    rep_precision: Counter = Counter()
    rep_sentinel = 0
    for index, row in enumerate(place_rows, start=1):
        pid = (row.get("id") or "").strip()
        if pid not in new_set or pid in have_location:
            continue
        lon = _coerce_float(row.get("representative_longitude", ""))
        lat = _coerce_float(row.get("representative_latitude", ""))
        if lon is None or lat is None:
            continue

        # 合成行的 raw 载荷 = places.csv 该行 + 两个派生键。
        # `place_id` 是必需的：导入器按 raw_payload.place_id 派生
        # source_record.parent_external_id；places.csv 只有 `id`，没有 `place_id`。
        payload = {k: v for k, v in row.items()}
        payload["place_id"] = pid
        payload["_derived_from"] = (
            "places.csv:representative_latitude,representative_longitude"
        )
        payload["_synthetic"] = "representative_point"

        flags: List[str] = []
        if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
            flags.append("coordinate_out_of_range")
        accuracy = min_accuracy.get(pid)
        if accuracy is None or accuracy == ACCURACY_UNKNOWN_SENTINEL:
            rep_sentinel += 1
        rep_precision[(row.get("location_precision") or "").strip() or "unknown"] += 1
        rep_records.append(
            _full_location_record(
                payload, index, "places.csv", pid,
                {
                    "geom_type": "Point",
                    "geom_wkt": f"POINT({lon} {lat})",
                    "lon": lon,
                    "lat": lat,
                    "flags": flags,
                    "note": "合成代表点（A2），来源 places.csv 的代表坐标",
                },
                synthetic=True,
                accuracy_m=accuracy,
            )
        )

    # ---- connections：13,603 行一行不丢 ----------------------------------
    connection_records: List[ExtraRecord] = []
    dangling: List[Dict[str, str]] = []
    self_loops = 0
    for index, row in enumerate(tables["connections"], start=1):
        a = _place_key(row.get("place_id"))
        b = _place_key(row.get("connects_to"))
        tpq = parse_signed_year(row.get("year_after_which", ""))
        taq = parse_signed_year(row.get("year_before_which", ""))
        bound_type = _pleiades_time_bound_type(tpq, taq)
        flags: List[str] = []
        note_bits = [
            "connects_to 是绝对 URI，尾段归一为地点 id（不把 URI 当 id）",
            f"connection_type={(row.get('connection_type') or '').strip() or '<blank>'}",
        ]
        if not a and not b:
            flags.append("connection_endpoint_missing")
            note_bits.append("整行字段全空，两端都无法解析")
            dangling.append({"row": str(index), "id": "", "place_id": "", "connects_to": ""})
        elif a not in all_ids or b not in all_ids:
            flags.append("connection_endpoint_missing")
            bad = "place_id" if a not in all_ids else "connects_to"
            note_bits.append(f"{bad} 端不在 places.csv（{a or '<blank>'} → {b or '<blank>'}）")
            dangling.append(
                {
                    "row": str(index),
                    "id": (row.get("id") or "").strip(),
                    "place_id": a,
                    "connects_to": (row.get("connects_to") or "").strip(),
                }
            )
        elif a == b:
            self_loops += 1
            note_bits.append("两端同一地点：源数据自环，入库不生成候选关系")

        connection_records.append(
            ExtraRecord(
                dataset_id=PLEIADES_FULL_DATASET_ID,
                source_id=PLEIADES_SOURCE_ID,
                source_dataset=PLEIADES_FULL_SOURCE_DATASET,
                record_kind="connection",
                record_index=index,
                raw_file="connections.csv",
                raw={k: v for k, v in row.items()},
                external_id=(row.get("id") or "").strip(),
                external_id_type="pleiades_connection_id",
                parent_external_id=a,
                name=(row.get("title") or "").strip(),
                name_lang="und",
                name_script="",
                name_type="alternate",
                place_type="unknown",
                time_bound_type=bound_type,
                valid_from_year=tpq,
                valid_to_year=taq,
                time_rule_code="year_after_which|year_before_which",
                quality_flags=flags,
                notes=("Pleiades v4.1 connection (connections.csv)；" + "；".join(note_bits)),
                connection_type=(row.get("connection_type") or "").strip(),
                connects_to_external_id=b,
            )
        )

    # ---- places：41,480 行全部保留（含 2,552 条重叠） ---------------------
    place_records: List[ExtraRecord] = []
    place_precision: Counter = Counter()
    missing_rep = 0
    for index, row in enumerate(place_rows, start=1):
        pid = (row.get("id") or "").strip()
        lon = _coerce_float(row.get("representative_longitude", ""))
        lat = _coerce_float(row.get("representative_latitude", ""))
        has_rep = lon is not None and lat is not None
        has_bbox = bool((row.get("bounding_box_wkt") or "").strip())
        precision = (row.get("location_precision") or "").strip() or "unknown"
        types = place_types.get(pid, [])
        flags: List[str] = []
        if not has_rep:
            flags.append("missing_coordinate")
            if pid in new_set:
                missing_rep += 1
        else:
            if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
                flags.append("coordinate_out_of_range")
        if pid in new_set:
            place_precision[precision] += 1
        place_records.append(
            ExtraRecord(
                dataset_id=PLEIADES_FULL_DATASET_ID,
                source_id=PLEIADES_SOURCE_ID,
                source_dataset=PLEIADES_FULL_SOURCE_DATASET,
                record_kind="place",
                record_index=index,
                raw_file="places.csv",
                raw={k: v for k, v in row.items()},
                external_id=pid,
                external_id_type="pleiades_place_id",
                name=(row.get("title") or "").strip(),
                name_lang="und",
                name_script="",
                name_type="primary",
                # 5 值域里只有 settlement 有数据依据；其余一律 unknown
                place_type=("settlement" if "settlement" in types else "unknown"),
                lon=lon,
                lat=lat,
                lon_text=(row.get("representative_longitude") or "").strip(),
                lat_text=(row.get("representative_latitude") or "").strip(),
                geom_wkt="",
                location_precision=precision,
                time_bound_type="unknown",
                time_rule_code="",
                quality_flags=flags,
                notes=(
                    f"pleiades_place_types={','.join(types) if types else ''}"
                    f";has_representative_point={'true' if has_rep else 'false'}"
                    f";has_bounding_box={'true' if has_bbox else 'false'}"
                    f";location_precision={precision}"
                ),
            )
        )

    records: List[ExtraRecord] = (
        place_records
        + name_records
        + point_records
        + rep_records
        + line_records
        + polygon_records
        + connection_records
    )
    extraction.records = records

    location_total = (
        len(point_records) + len(rep_records) + len(line_records) + len(polygon_records)
    )
    extraction.stats.update(
        {
            "source_id": PLEIADES_SOURCE_ID,
            "dataset_id": PLEIADES_FULL_DATASET_ID,
            "full_package": True,
            "record_kinds": {
                "places": len(place_records),
                "names": len(name_records),
                "locations": location_total,
                "location_points": len(point_records),
                "location_representative_points": len(rep_records),
                "location_linestrings": len(line_records),
                "location_polygons": len(polygon_records),
                "connections": len(connection_records),
            },
            "record_kind_total": len(records),
            "places_all": len(place_rows),
            "places_new": len(new_set),
            "places_superseded": len(sup_set),
            "superseded_place_ids": sorted(sup_set),
            "superseded_place_index": {
                pid: place_index.get(pid, 0) for pid in sorted(sup_set)
            },
            "places_new_without_representative_point": missing_rep,
            "superseded_place_precision": dict(
                sorted(Counter(
                    (row.get("location_precision") or "").strip() or "unknown"
                    for row in place_rows
                    if (row.get("id") or "").strip() in sup_set
                ).items())
            ),
            "place_precision_new": dict(sorted(place_precision.items())),
            "place_type_detail_counts": dict(
                sorted(
                    Counter(
                        "settlement" if "settlement" in place_types.get(pid, []) else "unknown"
                        for pid in new_set
                    ).items()
                )
            ),
            "location_geometry_counts": dict(sorted(geometry_counts.items())),
            "location_geometry_invalid_repaired": invalid_repaired,
            "location_geometry_unusable": skipped_unusable,
            "location_precision_new": dict(
                sorted(Counter(
                    (r.location_precision or "unknown")
                    for r in point_records + rep_records + line_records + polygon_records
                ).items())
            ),
            "representative_points": {
                "count": len(rep_records),
                "precision": dict(sorted(rep_precision.items())),
                "accuracy_unknown_sentinel": rep_sentinel,
            },
            "connections": {
                "rows": len(connection_records),
                "dangling": len(dangling),
                "dangling_rows": dangling,
                "self_loops": self_loops,
            },
            "short_record_count": short_total,
            "place_precision_vs_places_accuracy_disagreements": precision_disagreements,
            "places_table_has_time_columns": False,
            "year_zero_convention": (
                "gis_README.md: 'a signed integer indicating a year in the proleptic "
                "Julian calendar. There is no year zero.' —— 与 CHGIS 同一约定，"
                "astro_year() 原样适用"
            ),
            "qualities_present": ["place", "name", "location", "connection"],
        }
    )
    return extraction
