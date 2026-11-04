"""Common record shape for the non-CHGIS sources (Pleiades, WHG).

CHGIS has its own extractor because it needs a hand-written DBF reader.  The two
remaining sources are CSV and JSON, and they differ wildly from each other in
shape, so they are normalised here into one flat record type that
:mod:`normalize` can consume without knowing anything about Pleiades columns or
WHG schemas.

The record keeps **raw years** (historical convention, no year zero); the
astronomical conversion happens in :mod:`normalize` so that every source goes
through exactly one converter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "RECORD_KINDS",
    "ExtraRecord",
    "ExtraExtraction",
    "parse_wkt_point",
    "wkt_has_z",
]

#: Row roles.  Only ``place`` creates a ``historical_places`` row; ``name`` and
#: ``location`` attach to the place named by ``parent_external_id``;
#: ``connection`` becomes a ``candidate_matches`` row; ``reference`` rows are
#: counted but produce no table rows.
RECORD_KINDS = ("place", "name", "location", "connection", "reference")


@dataclass
class ExtraRecord:
    """One normalised source row from a non-CHGIS source.

    Attributes:
      dataset_id: Registry id, resolves in :mod:`datasets`.
      source_id: ``pleiades`` or ``whg``.
      source_dataset: Value written into ``source_records.source_dataset``.
      record_kind: One of :data:`RECORD_KINDS`.
      record_index: 1-based index of the row inside its own file.
      raw_file: Project-relative path of the file the row came from.
      raw: The source row as text, keyed by column (CSV) or by dotted path
        (JSON).  Serialised into ``source_records.raw_payload_json``.
      external_id: Primary key of the row in its own file.
      external_id_type: Qualified key name, e.g. ``pleiades_place_id``.
      parent_external_id: Place id this row belongs to; empty for
        ``record_kind == 'place'``.
      name: Display name, empty when the row carries none.
      name_lang: BCP-47-ish tag, ``und`` when the source does not say.
      name_script: ISO 15924 code, empty when unknown.
      name_type: ``primary`` / ``alternate`` / ``transliteration``.
      place_type: Controlled value; ``unknown`` for every non-CHGIS source
        because their type vocabularies (AAT ids, GeoNames feature codes) do not
        map onto the CHGIS ``admin_center_*`` vocabulary without a decision the
        source does not support.
      lon: Longitude in degrees, ``None`` when absent or unparseable.
      lat: Latitude in degrees.
      lon_text: Verbatim coordinate text for longitude.
      lat_text: Verbatim coordinate text for latitude.
      geom_wkt: WKT for the row's geometry, empty when the row has none.
      location_precision: The source's own precision word.
      uncertainty_m: Horizontal accuracy in metres, empty when not stated.
      original_crs: What the row's own container declares for the coordinate
        reference system; empty means "fall back to the source-level default".
        A conformant GeoJSON payload declares WGS84 through its format, so the
        JSON-LD rows carry ``EPSG:4326``; a plain JSON payload with a
        ``coordinates`` array that merely *looks* GeoJSON-shaped declares
        nothing, so those rows carry ``unknown``.
      crs_confidence: How sure we are the coordinates really are EPSG:4326,
        empty to fall back to the source-level mapping.  Set per row where the
        same source carries rows of different evidential strength.
      time_bound_type: One of :data:`time_semantics.TIME_BOUND_TYPES`.
      valid_from_year: Historical (no year zero) lower bound, ``None`` if absent.
      valid_to_year: Historical upper bound.
      time_rule_code: Raw rule code; empty for sources without one.
      quality_flags: Per-row flags mirroring ``quality_flag`` values.
      notes: Human-readable provenance and caveats.
      connection_type: Pleiades ``connection_type``; empty otherwise.
      connects_to_external_id: Other endpoint of a connection.
    """

    dataset_id: str
    source_id: str
    source_dataset: str
    record_kind: str
    record_index: int
    raw_file: str
    raw: Dict[str, str]
    external_id: str
    external_id_type: str
    parent_external_id: str = ""
    name: str = ""
    name_lang: str = "und"
    name_script: str = ""
    name_type: str = "primary"
    place_type: str = "unknown"
    lon: Optional[float] = None
    lat: Optional[float] = None
    lon_text: str = ""
    lat_text: str = ""
    geom_wkt: str = ""
    location_precision: str = ""
    uncertainty_m: str = ""
    original_crs: str = ""
    crs_confidence: str = ""
    time_bound_type: str = "unknown"
    valid_from_year: Optional[int] = None
    valid_to_year: Optional[int] = None
    time_rule_code: str = ""
    quality_flags: List[str] = field(default_factory=list)
    notes: str = ""
    connection_type: str = ""
    connects_to_external_id: str = ""

    @property
    def has_coordinate(self) -> bool:
        """True when both coordinates parsed as numbers."""
        return self.lon is not None and self.lat is not None

    @property
    def coord_key(self) -> Optional[str]:
        """``"lon|lat"`` text key, ``None`` when the row has no coordinate."""
        if self.lon is None or self.lat is None:
            return None
        return f"{self.lon:.6f}|{self.lat:.6f}"


@dataclass
class ExtraExtraction:
    """Everything one non-CHGIS extractor produced.

    Attributes:
      source_id: Owning source.
      source_dataset: Value used in ``source_records.source_dataset``.
      dataset_id: Registry id for the rows of this extractor.  A WHG sample
        spans three datasets, so its extractor overrides ``dataset_id`` per
        record and this field holds the dataset of the *place* rows.
      records: Every normalised row, in file order then row order.
      stats: Counts produced while reading, ready to be merged into
        ``stats.json``.
      slice_files: One ``{file, bytes, header_columns, parsed_rows,
        discarded_rows, sha256}`` dict per physical file read.
      attribution_note: Optional human note about licensing that the report
        needs verbatim, e.g. the WHG per-record licence switch.
    """

    source_id: str
    source_dataset: str
    dataset_id: str
    records: List[ExtraRecord] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    slice_files: List[Dict[str, Any]] = field(default_factory=list)
    attribution_note: str = ""


def parse_wkt_point(wkt: str) -> Optional[tuple]:
    """Extract ``(x, y)`` from a WKT POINT, tolerating ``Z``/``M``/``ZM``.

    Pleiades ``location_points.geometry_wkt`` holds forms such as
    ``POINT (14.4895 40.75)`` and, for exactly one row in the sample,
    ``POINT Z (x y z)``.  The Z value is discarded because the staging table is
    two-dimensional; discarding it is recorded on the row rather than silently
    dropped.

    Args:
      wkt: Raw WKT string.

    Returns:
      ``(x, y)`` as floats in the WKT's own axis order (X Y = lon lat for
      EPSG:4326), or ``None`` when the string is not a parseable POINT.
    """
    text = (wkt or "").strip()
    if not text:
        return None
    upper = text.upper()
    if not upper.startswith("POINT"):
        return None
    open_paren = text.find("(")
    close_paren = text.rfind(")")
    if open_paren < 0 or close_paren < open_paren:
        return None
    body = text[open_paren + 1 : close_paren].strip()
    parts = body.replace(",", " ").split()
    if len(parts) < 2:
        return None
    try:
        return (float(parts[0]), float(parts[1]))
    except ValueError:
        return None


def wkt_has_z(wkt: str) -> bool:
    """True when a WKT POINT declares or carries a third ordinate."""
    text = (wkt or "").strip().upper()
    if not text.startswith("POINT"):
        return False
    head = text[: text.find("(")] if "(" in text else text
    if "Z" in head.split():
        return True
    open_paren = text.find("(")
    close_paren = text.rfind(")")
    if open_paren < 0 or close_paren < open_paren:
        return False
    return len(text[open_paren + 1 : close_paren].replace(",", " ").split()) >= 3
