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
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from datasets import PLEIADES_ATTRIBUTION, PLEIADES_LICENSE_ID
from extra_record import ExtraExtraction, ExtraRecord, parse_wkt_point, wkt_has_z
from time_semantics import parse_signed_year

__all__ = [
    "PLEIADES_SOURCE_ID",
    "PLEIADES_SOURCE_DATASET",
    "PLEIADES_DATASET_ID",
    "PLEIADES_ATTRIBUTION",
    "PLEIADES_LICENSE_ID",
    "PLEIADES_SLICE_DIR",
    "SLICE_FILES",
    "extract_pleiades",
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
