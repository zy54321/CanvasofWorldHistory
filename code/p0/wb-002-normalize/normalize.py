"""Build the six WB-002 staging tables from the extracted source records.

Identity model
--------------
The WB-002 specification defines a historical place as *one distinct CHGIS
``SYS_ID`` within one dataset*.  That rule is implemented exactly as specified,
but the CHGIS data dictionary itself states that ``SYS_ID`` is a "unique ID for
the spatial object [can only occur once in the gisinfo_table]" -- i.e. it
identifies a *spatial object*, not a persistent administrative entity.  The
shipped data agrees: 15,746 of 15,748 ``SYS_ID`` values occur exactly once.  The
consequence, recorded in ``stats.json`` and the run report rather than papered
over, is that location migration cannot be recovered from repeated ``SYS_ID`` in
the point layers; successive seats of one entity are separate spatial objects.

Nothing here merges two source rows into one place, and nothing rewrites a year.

Time semantics
--------------
``time_basis`` was removed in revision 1.2.0 and replaced by ``time_bound_type``
plus ``time_rule_code``; see :mod:`time_semantics` for why the old vocabulary
could not express TPQ/TAQ or a snapshot.  The four sources map as follows:

===================  ======================================================
source               ``time_bound_type``
===================  ======================================================
CHGIS                derived from ``(BEG_RULE, END_RULE)`` via
                     :func:`time_semantics.chgis_time_bound_type`
MCGD                 ``unknown`` -- the CSV has no temporal columns at all
Pleiades             ``tpq_taq`` on name/location rows (documented
                     terminus post quem / ante quem); the place row itself is
                     ``unknown`` because ``places.csv`` has no time columns and
                     the place-level bound is aggregated from children
WHG                  ``unknown`` -- only partial ``when.timespans`` hints exist
                     and they are not a documented validity span
===================  ======================================================
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from chgis_extract import ChgisRecord
from chgis_migration import EMITTED_RELATIONS as MIGRATION_EMITTED_RELATIONS
from datasets import (
    CHGIS_CITATION_README,
    DATA_DATASETS_COLUMNS,
    MCGD_ATTRIBUTION as MCGD_DATASET_ATTRIBUTION,
    PLEIADES_ATTRIBUTION,
    get_dataset,
    iter_datasets,
)
from extra_record import ExtraExtraction, ExtraRecord
from mcgd_extract import (
    MCGD_ATTRIBUTION,
    MCGD_SOURCE_DATASET,
    SOURCE_ID_MCGD,
    McgdRecord,
)
from chgis_extract import SOURCE_ID_CHGIS
from quality_checks import (
    CHINA_LAT_RANGE,
    CHINA_LON_RANGE,
    DateRuleDictionary,
    astro_year,
    haversine_m,
    year_out_of_range_reason,
)
from time_semantics import (
    TIME_BOUND_TYPES,
    TIME_DERIVATIONS,
    aggregate_min_max,
    aggregate_tpq_taq,
    chgis_snapshot_year,
    chgis_time_bound_type,
    chgis_time_rule_code,
)

__all__ = [
    "PIPELINE_VERSION",
    "TABLE_COLUMNS",
    "NormalizedBundle",
    "build_bundle",
    "format_number",
]

#: Version stamp written into ``source_records.pipeline_version``.
PIPELINE_VERSION = "wb-002-normalize/1.3.0"

#: CHGIS layer -> registry dataset id, used for ``source_records.dataset_id``.
CHGIS_DATASET_IDS: Dict[str, str] = {
    "chgis_pref": "chgis_v6_prefecture_points",
    "chgis_cnty": "chgis_v6_county_points",
}

#: ``source_id`` for Pleiades rows; mirrors :mod:`pleiades_extract` without
#: importing it, to keep the dependency direction one-way.
SOURCE_ID_PLEIADES = "pleiades"
SOURCE_ID_WHG = "whg"

#: M4-4a：Pleiades GIS 4.1 全量数据集。与 ``pleiades_gis_4_1_slice`` 是同一来源的
#: 两个快照，前者是 1 MB 头切片，后者是完整 19 文件包。
PLEIADES_FULL_SOURCE_DATASET = "pleiades_gis_4_1"

#: Every non-CHGIS ``source_dataset`` whose place rows this module groups.
EXTRA_SOURCE_DATASETS: Tuple[str, ...] = (
    "pleiades_gis_4_1_slice",
    "whg_api_sample",
    PLEIADES_FULL_SOURCE_DATASET,
)

#: Sources in the fixed order used for stable ``place_id`` allocation.
#: The full v4.1 dataset is **appended last** on purpose: every place id that
#: already exists in ``code/data/staging`` then keeps its exact value, so the
#: union staging can be diffed row by row against the previous one.
DATASET_ORDER: Tuple[str, ...] = (
    "chgis_pref",
    "chgis_cnty",
    MCGD_SOURCE_DATASET,
    "pleiades_gis_4_1_slice",
    "whg_api_sample",
    PLEIADES_FULL_SOURCE_DATASET,
)

#: ``LEV_RANK`` -> controlled place-type vocabulary.
#: The CHGIS data dictionary does not describe ``LEV_RANK``, so the mapping is
#: derived from the empirical composition of the shipped layers (``'3'`` is used
#: by every prefecture-level feature type; ``'6'`` by every county-level one) and
#: anything else falls back to ``admin_center_other`` / ``unknown``.
LEV_RANK_TO_PLACE_TYPE: Dict[str, str] = {
    "3": "admin_center_prefecture",
    "6": "admin_center_county",
    "0": "admin_center_other",
    "1": "admin_center_other",
    "2": "admin_center_other",
    "4": "admin_center_other",
    "5": "admin_center_other",
}

#: Hard ceiling for ``raw_payload_json`` total size before falling back to
#: "non-empty fields only" storage, per the specification.
RAW_PAYLOAD_SIZE_LIMIT_BYTES = 25 * 1024 * 1024

#: Cap on emitted ``homonym_diff_place`` candidates, keeping the nearest pairs.
HOMONYM_PAIR_LIMIT = 25000

#: Distance ceiling for a homonym pair to be worth reviewing as a possible
#: mis-split of one place rather than a genuine far-apart namesake.
HOMONYM_PAIR_MAX_METRES = 200_000.0

#: Column order of every output table.  Kept as data so ``run_all`` can write
#: headers even for an empty table.
TABLE_COLUMNS: Dict[str, Tuple[str, ...]] = {
    "historical_places": (
        "place_id", "canonical_name", "canonical_name_lang", "place_type",
        "source_id", "source_dataset", "primary_external_id", "record_status",
        "locked", "created_at", "valid_from_year_astro", "valid_to_year_astro",
        "time_bound_type", "time_derivation", "notes",
    ),
    "historical_place_locations": (
        "location_id", "place_id", "geom_type", "lon", "lat", "geom_wkt",
        "representative_lon", "representative_lat", "original_x", "original_y",
        "original_crs", "crs_confidence", "axis_order_verified", "location_precision",
        "uncertainty_m", "valid_from_year_astro", "valid_to_year_astro",
        "time_bound_type", "time_rule_code", "quality_flag", "source_record_id", "notes",
    ),
    "historical_place_names": (
        "name_id", "place_id", "name", "name_lang", "name_script", "name_type",
        "transliteration_scheme", "valid_from_year_astro", "valid_to_year_astro",
        "time_bound_type", "time_rule_code", "source_record_id", "notes",
    ),
    "source_records": (
        "source_record_id", "source_id", "source_dataset", "dataset_id",
        "external_id", "external_id_type", "raw_file", "raw_record_index",
        "raw_payload_json", "attribution_text",
        "ingested_at", "pipeline_version",
    ),
    "data_quality_issues": (
        "issue_id", "source_id", "source_dataset", "source_record_id", "issue_type",
        "severity", "field_name", "observed_value", "expected_rule", "action_taken",
        "notes",
    ),
    "candidate_matches": (
        "candidate_id", "relation_type", "place_id_a", "source_record_id_a",
        "name_a", "lon_a", "lat_a", "place_id_b", "source_record_id_b", "name_b",
        "lon_b", "lat_b", "distance_m", "same_name", "evidence", "confidence",
        "status", "reviewer", "reviewed_at",
    ),
    "data_datasets": DATA_DATASETS_COLUMNS,
}

#: CRS provenance string shared by every CHGIS location row.
CHGIS_CRS_NOTE = (
    "original_crs=EPSG:4326 confirmed from the .prj sidecar in the source zip "
    "(GEOGCS[\"GCS_WGS_1984\"], DATUM[\"D_WGS_1984\"]); axis order verified because "
    "X_COOR holds values such as 108.937190 which cannot be a latitude (>90), so "
    "X_COOR=longitude and Y_COOR=latitude"
)

#: CRS provenance string shared by every MCGD location row.
MCGD_CRS_NOTE = (
    "original_crs unknown: the MCGD CSV declares no CRS. Column names LAT/LONG fix "
    "the axis order (verified: LAT stays within [-90,90] across the sample while "
    "LONG reaches 881.41 in one row, which is impossible as a latitude), so the "
    "data is almost certainly geographic degrees, but the datum/CRS is not "
    "documented and is therefore inferred only"
)


def format_number(value: Optional[float], precision: int = 9) -> str:
    """Render a float for CSV output without scientific notation or noise.

    Args:
      value: Value to render; ``None`` becomes an empty string.
      precision: Maximum decimal places to keep.

    Returns:
      A plain decimal string with trailing zeros removed.
    """
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    text = f"{value:.{precision}f}".rstrip("0").rstrip(".")
    return text or "0"


def _sort_key_for_external_id(source_dataset: str, external_id: str) -> Tuple[int, str]:
    """Order external identifiers numerically when they are numeric.

    CHGIS ``SYS_ID`` values are integers; MCGD ``LocID`` values are strings such
    as ``D3392205``.  Numeric ids are zero-padded to a fixed width so that a
    lexical sort still yields numeric order and the resulting ``place_id``
    sequence is stable.
    """
    if source_dataset == MCGD_SOURCE_DATASET:
        return (1, external_id)
    try:
        return (0, f"{int(external_id):012d}")
    except (TypeError, ValueError):
        return (2, external_id or "")


@dataclass
class PlaceGroup:
    """All source rows that the identity model attributes to one place.

    Attributes:
      source_dataset: Layer the place belongs to.
      external_id: The place key inside that layer (CHGIS ``SYS_ID``, MCGD
        ``LocID``, Pleiades ``id``, WHG place id).
      chgis_records: CHGIS rows collapsed into this place.
      mcgd_records: MCGD rows collapsed into this place.
      extra_records: Pleiades / WHG rows collapsed into this place.  Only rows
        with ``record_kind == 'place'`` appear here; child rows are looked up by
        ``parent_external_id``.
      dataset_id: Registry id used for ``source_records.dataset_id``.
      place_id: Allocated ``hp_`` identifier.
    """

    source_dataset: str
    external_id: str
    chgis_records: List[ChgisRecord] = field(default_factory=list)
    mcgd_records: List[McgdRecord] = field(default_factory=list)
    extra_records: List[ExtraRecord] = field(default_factory=list)
    dataset_id: str = ""
    place_id: str = ""

    @property
    def primary_extra(self) -> Optional[ExtraRecord]:
        """The first extra-source row of this place, or ``None``."""
        return self.extra_records[0] if self.extra_records else None


@dataclass
class NormalizedBundle:
    """The six output tables plus the statistics needed to describe them.

    Attributes:
      tables: Table name -> list of row dicts.
      stats: Every count produced while building the tables.
      place_lookup: ``"<source_dataset>:<record_index>"`` -> ``place_id``, used
        by the issue writers to attach places to cluster members.
    """

    tables: Dict[str, List[Dict[str, str]]]
    stats: Dict[str, Any]
    place_lookup: Dict[str, str] = field(default_factory=dict)


class _IdAllocator:
    """Deterministic sequential identifier generator with a fixed prefix."""

    def __init__(self, prefix: str, width: int) -> None:
        self._prefix = prefix
        self._width = width
        self._next = 1

    def next(self) -> str:
        """Return the next identifier, e.g. ``loc_0000001``."""
        value = f"{self._prefix}{self._next:0{self._width}d}"
        self._next += 1
        return value


def _json_payload(raw: Dict[str, str], non_empty_only: bool) -> str:
    """Serialise a source row's raw fields to compact deterministic JSON."""
    if non_empty_only:
        payload = {k: v for k, v in raw.items() if v != ""}
    else:
        payload = dict(raw)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pick_canonical_chgis_record(records: Sequence[ChgisRecord]) -> ChgisRecord:
    """Choose the name-bearing record for a CHGIS place.

    Priority per the specification: greatest ``BEG_YR`` first, then greatest
    ``END_YR``, then smallest physical ``record_index``.  Missing years sort last
    so that a datable record always wins over an undated one.
    """

    def key(record: ChgisRecord) -> Tuple[int, int, int, int]:
        beg = record.beg_year
        end = record.end_year
        return (
            0 if beg is not None else 1,
            -(beg if beg is not None else 0),
            0 if end is not None else 1,
            -(end if end is not None else 0),
        )

    best = min(records, key=lambda r: (key(r), r.record_index))
    return best


def _pick_canonical_mcgd_record(records: Sequence[McgdRecord]) -> McgdRecord:
    """Choose the canonical MCGD name for a ``LocID``.

    MCGD carries no dates, so no temporal rule exists.  The row with the
    lexicographically smallest ``NameID`` is taken: an arbitrary but fully stable
    choice.  ``LocID`` values with several names are flagged in the place notes so
    a reviewer can override.
    """
    return min(records, key=lambda r: (r.name_id, r.record_index))


def _place_type_for_chgis(records: Sequence[ChgisRecord]) -> Tuple[str, str]:
    """Map a CHGIS place onto the controlled place-type vocabulary.

    Returns:
      ``(place_type, basis)`` where basis documents which field decided it.
    """
    ranks = Counter((r.lev_rank or "").strip() for r in records)
    for rank, _count in ranks.most_common():
        if rank in LEV_RANK_TO_PLACE_TYPE:
            return LEV_RANK_TO_PLACE_TYPE[rank], f"lev_rank={rank}"
    types = Counter(r.type_py for r in records if r.type_py)
    if types:
        return "unknown", f"lev_rank_unmapped; type_py={types.most_common(1)[0][0]}"
    return "unknown", "no lev_rank and no type_py"


def _chgis_record_years(record: ChgisRecord) -> Dict[str, Any]:
    """Derive one CHGIS record's validity columns.

    This is the **only** place a CHGIS year is turned into a validity column, so
    the record-level rows and the place-level aggregate can never disagree.

    Rules, in order:

    1. ``BEG_YR > END_YR`` -> ``time_bound_type='unknown'``, both years empty.
       The pair contradicts itself, so no interval is claimed.  The raw years
       stay verbatim in ``source_records`` / ``chgis_all_records.csv``.
    2. Either rule code ``9`` -> ``snapshot``: both columns are set to the slice
       year and the record claims no interval.
    3. Otherwise the pair is rendered from the rule codes, and a missing year on
       one side leaves that column empty.

    Returns:
      ``{"valid_from": str, "valid_to": str, "time_bound_type": str,
      "time_rule_code": str, "snapshot_basis": str, "inverted": bool}``.
    """
    beg = record.beg_year
    end = record.end_year
    rule_code = chgis_time_rule_code(record.beg_rule, record.end_rule)
    inverted = beg is not None and end is not None and beg > end
    if inverted:
        return {
            "valid_from": "",
            "valid_to": "",
            "time_bound_type": "unknown",
            "time_rule_code": rule_code,
            "snapshot_basis": "",
            "inverted": True,
        }
    bound_type = chgis_time_bound_type(record.beg_rule, record.end_rule)
    if bound_type == "snapshot":
        slice_year, basis = chgis_snapshot_year(
            beg, end, record.beg_rule, record.end_rule
        )
        if slice_year is None:
            from_text = to_text = ""
        else:
            try:
                rendered = str(astro_year(slice_year))
            except ValueError:
                rendered = ""
            from_text = to_text = rendered
        return {
            "valid_from": from_text,
            "valid_to": to_text,
            "time_bound_type": "snapshot",
            "time_rule_code": rule_code,
            "snapshot_basis": basis,
            "inverted": False,
        }
    try:
        from_text = "" if beg is None else str(astro_year(beg))
    except ValueError:
        from_text = ""
    try:
        to_text = "" if end is None else str(astro_year(end))
    except ValueError:
        to_text = ""
    return {
        "valid_from": from_text,
        "valid_to": to_text,
        "time_bound_type": bound_type,
        "time_rule_code": rule_code,
        "snapshot_basis": "",
        "inverted": False,
    }


def _extra_years(record: ExtraRecord) -> Tuple[str, str]:
    """Render one non-CHGIS record's TPQ/TAQ pair as astronomical years."""
    from_text = ""
    to_text = ""
    if record.valid_from_year is not None:
        try:
            from_text = str(astro_year(record.valid_from_year))
        except ValueError:
            from_text = ""
    if record.valid_to_year is not None:
        try:
            to_text = str(astro_year(record.valid_to_year))
        except ValueError:
            to_text = ""
    return from_text, to_text


def _place_time_bounds(
    group: PlaceGroup,
    children: Sequence[ExtraRecord],
) -> Tuple[str, str, str, str]:
    """Aggregate a place's own rows into place-level validity columns.

    The four sources are handled differently because they make different claims:

    * CHGIS: the envelope of its records, ``min_max_of_children``.
    * Pleiades: the TPQ/TAQ envelope of its **name and location** rows,
      ``tpq_taq_of_children``.  The place row itself has no time columns.
      Connection rows are excluded: a connection's TPQ/TAQ describes when the
      *relation between two places* is attested, not when the place existed
      (CORE_DATA_MODEL_V2.1 §5.5.4, IMPORT_RULES_V2.1 §7.6).  Including them
      inflated 820 place/field values across 629 places -- see M4-5.
    * MCGD and WHG: ``none`` -- nothing to aggregate.

    Returns:
      ``(valid_from, valid_to, time_bound_type, time_derivation)``.
    """
    if group.source_dataset in ("chgis_pref", "chgis_cnty"):
        spans: List[Tuple[Optional[int], Optional[int]]] = []
        types: List[str] = []
        for record in group.chgis_records:
            years = _chgis_record_years(record)
            types.append(years["time_bound_type"])
            spans.append(
                (
                    _to_int(years["valid_from"]),
                    _to_int(years["valid_to"]),
                )
            )
        low, high = aggregate_min_max(spans)
        if low is None and high is None:
            return "", "", "unknown", "none"
        # A place is only as precise as its weakest record, so the place-level
        # type is only promoted to a determinate value when every child agrees.
        determinate = {t for t in types if t != "unknown"}
        if len(determinate) == 1 and "snapshot" not in determinate:
            bound_type = determinate.pop()
        elif determinate == {"snapshot"}:
            bound_type = "snapshot"
        else:
            bound_type = "unknown"
        return (
            "" if low is None else str(low),
            "" if high is None else str(high),
            bound_type,
            "min_max_of_children",
        )

    if group.source_dataset in EXTRA_SOURCE_DATASETS:
        bounds: List[Tuple[Optional[int], Optional[int]]] = []
        for record in children:
            # M4-5：connection 子记录**不进入**地点级时间包络。
            #
            # 依据（不是本轮新造的语义）：
            #   CORE_DATA_MODEL_V2.1 §5.5.4 —— "地点的时间跨度是『它的名称与位置
            #   的时间跨度之并』，是一句可以随时重算的派生结论"，派生视图只 UNION
            #   historical_place_location 与 historical_place_name，没有 connection。
            #   IMPORT_RULES_V2.1 §7.6 的重算规则同样只聚合 name+location。
            #
            # 语义上也站得住：connection 的 year_after_which / year_before_which 说的是
            # "这两个地点之间的关系何时被证实"（part_of_admin、insula-batavorum …），
            # 不是"这个地点何时存在"。把它算进地点包络，等于让邻接地点的年代改写
            # 本地点——实测 820 行 / 629 个地点的虚增全部来自这里（见 M4-5 审计）。
            if record.record_kind == "connection":
                continue
            if record.time_bound_type not in ("tpq_taq", "bounded"):
                continue
            from_astro, to_astro = _extra_years(record)
            bounds.append((_to_int(from_astro), _to_int(to_astro)))
        low, high = aggregate_tpq_taq(bounds)
        if low is None and high is None:
            return "", "", "unknown", "none"
        return (
            "" if low is None else str(low),
            "" if high is None else str(high),
            "derived_tpq_taq",
            "tpq_taq_of_children",
        )

    return "", "", "unknown", "none"


def _to_int(text: str) -> Optional[int]:
    """Parse an already-rendered year string back to ``int`` for aggregation."""
    stripped = (text or "").strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


#: CRS confidence vocabulary, and the rule that produces it.
#:
#: ``original_crs``      what the *source* declares (``unknown`` when silent).
#: ``crs_confidence``    how sure we are that the coordinates really are
#:                       EPSG:4326.  Derived from the declaration, never from
#:                       plausibility:
#:                         ``confirmed`` -- the source states WGS84 (CHGIS
#:                           ``.prj``; Pleiades ``gis_README.md``);
#:                         ``inferred``  -- no explicit statement, but the
#:                           format the data is expressed in mandates WGS84
#:                           **and the file actually conforms to that format**
#:                           (RFC 7946 GeoJSON -> WHG's JSON-LD records).
#:                           Merely *looking* GeoJSON-shaped is not enough: WHG's
#:                           older flat schema carries ``geoms[].coordinates``
#:                           but no ``@context`` and no ``crs`` member, so its
#:                           rows are ``unknown``, exactly like MCGD.
#:                         ``unknown``   -- neither, i.e. MCGD, whose 9-column
#:                           header names no datum and whose numbers being
#:                           plausible is a sanity check, not CRS evidence.
#: ``axis_order_verified`` whether lon/lat order has been established.  It is a
#:                       *separate* question: MCGD's axis order can be verified
#:                       from its ``LAT``/``LONG`` column names while its CRS
#:                       stays ``unknown``, and those two facts do not conflict.
CRS_CONFIDENCE_VALUES: Tuple[str, ...] = ("confirmed", "inferred", "unknown")

CRS_CONFIDENCE_BY_SOURCE: Dict[str, str] = {
    "chgis": "confirmed",
    "pleiades": "confirmed",
    "whg": "inferred",
    "mcgd": "unknown",
}


def _crs_confidence_for(source_id: str) -> str:
    """Return the CRS confidence for a source, per the rule documented above."""
    return CRS_CONFIDENCE_BY_SOURCE.get(source_id, "unknown")


def _source_id_for_dataset(source_dataset: str) -> str:
    """Map a ``source_dataset`` value onto its owning ``source_id``."""
    if source_dataset == MCGD_SOURCE_DATASET:
        return SOURCE_ID_MCGD
    if source_dataset in ("pleiades_gis_4_1_slice", PLEIADES_FULL_SOURCE_DATASET):
        return SOURCE_ID_PLEIADES
    if source_dataset == "whg_api_sample":
        return SOURCE_ID_WHG
    return SOURCE_ID_CHGIS


#: ``geometry_wkt`` prefix -> the controlled ``historical_place_location.geom_type``
#: value.  The prefix is read instead of adding a field to :class:`ExtraRecord`,
#: because the WKT already is the authoritative statement of the row's geometry.
_GEOM_TYPE_BY_WKT_PREFIX: Tuple[Tuple[str, str], ...] = (
    ("MULTIPOLYGON", "MultiPolygon"),
    ("POLYGON", "Polygon"),
    ("MULTILINESTRING", "MultiLineString"),
    ("LINESTRING", "LineString"),
    ("POINT", "Point"),
)


def _geom_type_of_wkt(wkt: str) -> str:
    """Return the ``geom_type`` implied by a WKT string's first token.

    Point rows and rows whose WKT failed to parse fall back to ``Point``: every
    non-point row in this pipeline is produced from a WKT that parsed, so the
    fallback can only ever describe a genuine point.
    """
    text = (wkt or "").strip().upper()
    for prefix, value in _GEOM_TYPE_BY_WKT_PREFIX:
        if text.startswith(prefix):
            return value
    return "Point"


def _extra_name_lang(record: ExtraRecord) -> str:
    """Return a usable language tag for a non-CHGIS name row."""
    tag = (record.name_lang or "").strip()
    return tag or "und"


def build_bundle(
    chgis_records: Sequence[ChgisRecord],
    mcgd_records: Sequence[McgdRecord],
    date_rules: DateRuleDictionary,
    chgis_attribution: str,
    ingested_at: str,
    mcgd_csv_relative: str,
    mcgd_doi: str,
    field_quirks: Sequence[Any] = (),
    migration_edges: Sequence[Any] = (),
    extra_extractions: Sequence[ExtraExtraction] = (),
) -> NormalizedBundle:
    """Assemble the seven staging tables.

    Args:
      chgis_records: All 15,748 CHGIS point records, in dataset order.
      mcgd_records: All 960 MCGD sample rows.
      date_rules: Parsed CHGIS ``xtra_date_rules`` lookup, used to derive
        ``time_bound_type`` and to describe each rule code in the notes.
      chgis_attribution: Verbatim CHGIS citation line from the README.
      ingested_at: ISO-8601 UTC timestamp stamped onto every output row.
      mcgd_csv_relative: Project-relative path of the MCGD sample CSV.
      mcgd_doi: DOI read from the cached Zenodo record.
      field_quirks: Field-name deviations detected across the CHGIS layers.
      migration_edges: Rule-based adjacent-pair verdicts produced by
        :mod:`chgis_migration`.  Their emittable rows are appended to
        ``candidate_matches`` after the coordinate/name-based relations.
      extra_extractions: Normalised Pleiades and WHG rows.  Each extraction
        contributes place / name / location / connection records; nothing here
        merges them with a CHGIS place.

    Returns:
      A :class:`NormalizedBundle` with ``tables`` keyed by table name and
      ``stats`` holding every count produced while building them.
    """
    stats: Dict[str, Any] = {}
    rule_basis_available = date_rules.loaded

    # ------------------------------------------------------------------
    # 1. Place groups
    # ------------------------------------------------------------------
    chgis_groups: Dict[Tuple[str, str], PlaceGroup] = {}
    for record in chgis_records:
        key = (record.source_dataset, record.sys_id_text)
        group = chgis_groups.get(key)
        if group is None:
            group = PlaceGroup(
                source_dataset=record.source_dataset,
                external_id=record.sys_id_text,
                dataset_id=CHGIS_DATASET_IDS.get(record.source_dataset, ""),
            )
            chgis_groups[key] = group
        group.chgis_records.append(record)

    mcgd_groups: Dict[str, PlaceGroup] = {}
    for record in mcgd_records:
        group = mcgd_groups.get(record.loc_id)
        if group is None:
            group = PlaceGroup(
                source_dataset=MCGD_SOURCE_DATASET,
                external_id=record.loc_id,
                dataset_id="mcgd_zenodo_22094815_head960",
            )
            mcgd_groups[record.loc_id] = group
        group.mcgd_records.append(record)

    # Non-CHGIS places: one group per ``(source_dataset, external_id)``.  Child
    # rows (names, locations, connections) are kept on the extraction and looked
    # up by ``parent_external_id``; only ``place`` rows create groups.
    #
    # M4-4a: the v4.1 package carries 2,552 places that the older slice snapshot
    # already imported.  Those place rows still become ``source_records`` (so all
    # 41,480 rows stay traceable) but they never become a ``PlaceGroup``: the
    # increment plan keeps the existing place untouched instead of creating a
    # duplicate, and their children are not part of the increment either.
    superseded_keys: set = set()
    for extraction in extra_extractions:
        for external_id in extraction.stats.get("superseded_place_ids", []) or []:
            superseded_keys.add((extraction.source_dataset, external_id))

    extra_groups: Dict[Tuple[str, str], PlaceGroup] = {}
    extra_children: Dict[str, List[ExtraRecord]] = defaultdict(list)
    for extraction in extra_extractions:
        for record in extraction.records:
            if record.record_kind == "place":
                key = (record.source_dataset, record.external_id)
                if key in superseded_keys:
                    continue
                group = extra_groups.get(key)
                if group is None:
                    group = PlaceGroup(
                        source_dataset=record.source_dataset,
                        external_id=record.external_id,
                        dataset_id=record.dataset_id,
                    )
                    extra_groups[key] = group
                group.extra_records.append(record)
            elif record.record_kind in ("name", "location", "connection"):
                extra_children[f"{record.source_dataset}:{record.parent_external_id}"].append(
                    record
                )
    stats["superseded_place_groups_skipped"] = len(superseded_keys)

    ordered_groups: List[PlaceGroup] = []
    for dataset in DATASET_ORDER:
        if dataset == MCGD_SOURCE_DATASET:
            ordered_groups.extend(
                mcgd_groups[key] for key in sorted(mcgd_groups, key=lambda k: _sort_key_for_external_id(dataset, k))
            )
        elif dataset in EXTRA_SOURCE_DATASETS:
            subset = [g for g in extra_groups.values() if g.source_dataset == dataset]
            subset.sort(key=lambda g: _sort_key_for_external_id(dataset, g.external_id))
            ordered_groups.extend(subset)
        else:
            subset = [g for g in chgis_groups.values() if g.source_dataset == dataset]
            subset.sort(key=lambda g: _sort_key_for_external_id(dataset, g.external_id))
            ordered_groups.extend(subset)

    place_ids = _IdAllocator("hp_", 6)
    for group in ordered_groups:
        group.place_id = place_ids.next()

    # M4-4a：重叠地点的别名映射。某个 v4.1 地点若已由切片快照建点，指向它的连接
    # （以及指向它的候选关系另一端）必须解析到**既有**的 place_id，否则会造出一条
    # 指向不存在地点的候选记录。映射只在内存里构造，不改任何表结构。
    alias_place_ids: Dict[Tuple[str, str], str] = {}
    for source_dataset, external_id in sorted(superseded_keys):
        slice_group = extra_groups.get(("pleiades_gis_4_1_slice", external_id))
        if slice_group is not None:
            alias_place_ids[(source_dataset, external_id)] = slice_group.place_id
    stats["superseded_place_alias_resolved"] = len(alias_place_ids)
    stats["superseded_place_alias_unresolved"] = sorted(
        f"{dataset}:{external_id}"
        for dataset, external_id in superseded_keys
        if (dataset, external_id) not in alias_place_ids
    )

    # Fast lookups used when emitting names/locations/candidates.
    place_of_chgis_record: Dict[Tuple[str, int], str] = {}
    for group in ordered_groups:
        for record in group.chgis_records:
            place_of_chgis_record[(record.source_dataset, record.record_index)] = group.place_id
    place_of_mcgd_record: Dict[int, str] = {}
    for group in ordered_groups:
        for record in group.mcgd_records:
            place_of_mcgd_record[record.record_index] = group.place_id

    stats["place_counts"] = {
        "total": len(ordered_groups),
        "chgis_pref": sum(1 for g in ordered_groups if g.source_dataset == "chgis_pref"),
        "chgis_cnty": sum(1 for g in ordered_groups if g.source_dataset == "chgis_cnty"),
        "mcgd": sum(1 for g in ordered_groups if g.source_dataset == MCGD_SOURCE_DATASET),
        "pleiades": sum(1 for g in ordered_groups if g.source_dataset == "pleiades_gis_4_1_slice"),
        "pleiades_gis_4_1": sum(
            1 for g in ordered_groups if g.source_dataset == PLEIADES_FULL_SOURCE_DATASET
        ),
        "whg": sum(1 for g in ordered_groups if g.source_dataset == "whg_api_sample"),
    }
    stats["place_counts_per_source_dataset"] = dict(
        sorted(Counter(g.source_dataset for g in ordered_groups).items())
    )
    stats["chgis_place_record_multiplicity"] = {
        f"places_with_{row_count}_source_record(s)": place_count
        for row_count, place_count in sorted(
            Counter(
                len(g.chgis_records)
                for g in ordered_groups
                if g.source_dataset not in (MCGD_SOURCE_DATASET,) + EXTRA_SOURCE_DATASETS
            ).items()
        )
    }
    stats["mcgd_place_record_multiplicity"] = {
        f"places_with_{row_count}_source_row(s)": place_count
        for row_count, place_count in sorted(
            Counter(
                len(g.mcgd_records) for g in ordered_groups if g.source_dataset == MCGD_SOURCE_DATASET
            ).items()
        )
    }

    # Child-row counts for the non-CHGIS sources: how many names / locations /
    # connections each place carries.  Reported so the 1:N geometry of Pleiades
    # (one place, many location points) is visible in stats and not just prose.
    stats["extra_place_child_counts"] = {}
    for dataset in EXTRA_SOURCE_DATASETS:
        children = [
            record
            for extraction in extra_extractions
            if extraction.source_dataset == dataset
            for record in extraction.records
            if record.record_kind in ("name", "location", "connection")
        ]
        stats["extra_place_child_counts"][dataset] = dict(
            sorted(Counter(record.record_kind for record in children).items())
        )

    # ------------------------------------------------------------------
    # 2. source_records
    # ------------------------------------------------------------------
    source_record_ids: Dict[Tuple[str, int], str] = {}
    raw_payloads: List[str] = []
    pending_source_rows: List[Dict[str, str]] = []
    sr_ids = _IdAllocator("sr_", 7)

    chgis_payloads = [_json_payload(r.raw, non_empty_only=False) for r in chgis_records]
    mcgd_payloads = [_json_payload(r.raw, non_empty_only=False) for r in mcgd_records]
    total_payload_bytes = sum(len(p.encode("utf-8")) for p in chgis_payloads + mcgd_payloads)
    non_empty_only = total_payload_bytes > RAW_PAYLOAD_SIZE_LIMIT_BYTES
    if non_empty_only:
        chgis_payloads = [_json_payload(r.raw, non_empty_only=True) for r in chgis_records]
        mcgd_payloads = [_json_payload(r.raw, non_empty_only=True) for r in mcgd_records]
        total_payload_bytes = sum(len(p.encode("utf-8")) for p in chgis_payloads + mcgd_payloads)
    stats["raw_payload"] = {
        "non_empty_only": non_empty_only,
        "size_limit_bytes": RAW_PAYLOAD_SIZE_LIMIT_BYTES,
        "total_bytes": total_payload_bytes,
    }

    for record, payload in zip(chgis_records, chgis_payloads):
        source_record_id = sr_ids.next()
        source_record_ids[(record.source_dataset, record.record_index)] = source_record_id
        pending_source_rows.append(
            {
                "source_record_id": source_record_id,
                "source_id": SOURCE_ID_CHGIS,
                "source_dataset": record.source_dataset,
                "dataset_id": CHGIS_DATASET_IDS.get(record.source_dataset, ""),
                "external_id": record.sys_id_text,
                "external_id_type": "chgis_sys_id",
                "raw_file": record.raw_zip,
                "raw_record_index": str(record.record_index),
                "raw_payload_json": payload,
                "attribution_text": chgis_attribution,
                "ingested_at": ingested_at,
                "pipeline_version": PIPELINE_VERSION,
            }
        )

    mcgd_source_record_ids: Dict[int, str] = {}
    for record, payload in zip(mcgd_records, mcgd_payloads):
        source_record_id = sr_ids.next()
        mcgd_source_record_ids[record.record_index] = source_record_id
        pending_source_rows.append(
            {
                "source_record_id": source_record_id,
                "source_id": SOURCE_ID_MCGD,
                "source_dataset": MCGD_SOURCE_DATASET,
                "dataset_id": "mcgd_zenodo_22094815_head960",
                "external_id": record.name_id,
                "external_id_type": "mcgd_nameid",
                "raw_file": mcgd_csv_relative,
                "raw_record_index": str(record.record_index),
                "raw_payload_json": payload,
                "attribution_text": MCGD_ATTRIBUTION,
                "ingested_at": ingested_at,
                "pipeline_version": PIPELINE_VERSION,
            }
        )

    # ---- non-CHGIS sources ------------------------------------------------
    # Payloads for the CSV/JSON sources always drop empty fields: a Pleiades
    # places.csv row carries 11 columns of which the sample almost never fills
    # more than five, and keeping the blanks would spend most of the payload
    # budget on ", " separators.  This is a per-source decision, reported in
    # stats, so the CHGIS/MCGD payload policy above is unaffected.
    extra_source_record_ids: Dict[Tuple[str, str], str] = {}
    extra_child_source_record_ids: Dict[Tuple[str, str, int], str] = {}
    extra_payload_bytes = 0
    extra_rows_per_dataset: Counter = Counter()
    for extraction in extra_extractions:
        for record in extraction.records:
            if record.record_kind == "reference":
                continue
            dataset = get_dataset(record.dataset_id)
            payload = _json_payload(record.raw, non_empty_only=True)
            extra_payload_bytes += len(payload.encode("utf-8"))
            source_record_id = sr_ids.next()
            if record.record_kind == "place":
                extra_source_record_ids[(record.source_dataset, record.external_id)] = source_record_id
            else:
                # Child rows are numbered inside their own file, so the file has to
                # be part of the key: names.csv row 7 and places.csv row 7 are
                # unrelated rows.
                extra_child_source_record_ids[
                    (record.source_dataset, record.raw_file, record.record_index)
                ] = source_record_id
            extra_rows_per_dataset[record.dataset_id] += 1
            pending_source_rows.append(
                {
                    "source_record_id": source_record_id,
                    "source_id": record.source_id,
                    "source_dataset": record.source_dataset,
                    "dataset_id": record.dataset_id,
                    "external_id": record.external_id,
                    "external_id_type": record.external_id_type,
                    "raw_file": record.raw_file,
                    "raw_record_index": str(record.record_index),
                    "raw_payload_json": payload,
                    "attribution_text": dataset.attribution_text,
                    "ingested_at": ingested_at,
                    "pipeline_version": PIPELINE_VERSION,
                }
            )
    stats["raw_payload"]["extra_sources_total_bytes"] = extra_payload_bytes
    stats["raw_payload"]["extra_sources_non_empty_only"] = True
    stats["source_records_per_dataset_id"] = dict(sorted(extra_rows_per_dataset.items()))

    # ------------------------------------------------------------------
    # 3. historical_places
    # ------------------------------------------------------------------
    places: List[Dict[str, str]] = []
    place_type_counts: Counter = Counter()
    place_type_basis: Counter = Counter()
    place_time_bound_counts: Counter = Counter()
    place_time_derivation_counts: Counter = Counter()
    lev_rank_vs_layer_disagreements = 0

    for group in ordered_groups:
        if group.source_dataset == MCGD_SOURCE_DATASET:
            canonical_record = _pick_canonical_mcgd_record(group.mcgd_records)
            canonical_name = canonical_record.name
            name_lang = "zh-Latn"
            place_type = "unknown"
            basis = "mcgd_code_semantics_unconfirmed"
            note_parts = [
                f"loc_id={group.external_id}",
                f"rows={len(group.mcgd_records)}",
                f"prov_zh={canonical_record.prov_zh}",
                f"code={canonical_record.code}",
                "code_meaning_unconfirmed",
            ]
            if len(group.mcgd_records) > 1:
                note_parts.append(
                    f"alternate_name_count={len(group.mcgd_records) - 1};"
                    "canonical_name_chosen_by_smallest_name_id_arbitrary_but_stable"
                )
        elif group.source_dataset in EXTRA_SOURCE_DATASETS:
            primary = group.primary_extra
            canonical_record = primary
            canonical_name = (primary.name if primary else "") or group.external_id
            if group.source_dataset == PLEIADES_FULL_SOURCE_DATASET:
                name_lang = "und"
                # place_type 只有 5 值域，Pleiades 的 192 键类型词表无法整体映射；
                # 唯一有数据依据的映射是 settlement。多值关系写进汇总文本，
                # 逐行关系留在归档（承载矩阵 §四）。
                place_type = (primary.place_type if primary else "") or "unknown"
                if place_type not in ("settlement", "unknown"):
                    place_type = "unknown"
                basis = "pleiades_settlement_only"
                note_parts = [
                    f"pleiades_place_id={group.external_id}",
                    "canonical_name_source=places.csv title",
                    "name_language_not_stated_by_source_so_und",
                    f"place_type_basis={basis}",
                ]
                if primary is not None and (primary.notes or "").strip():
                    note_parts.append(primary.notes.strip())
            elif group.source_dataset == "pleiades_gis_4_1_slice":
                name_lang = "und"
                note_parts = [
                    f"pleiades_place_id={group.external_id}",
                    "canonical_name_source=places.csv title",
                    "name_language_not_stated_by_source_so_und",
                ]
                place_type = "unknown"
                basis = "source_has_no_chgis_compatible_type_field"
            else:
                name_lang = "und"
                note_parts = [
                    f"whg_place_id={group.external_id}",
                    f"dataset_id={group.dataset_id}",
                    "canonical_name_source=WHG title",
                    "name_language_not_stated_by_source_so_und",
                ]
                place_type = "unknown"
                basis = "source_has_no_chgis_compatible_type_field"
            if group.source_dataset != PLEIADES_FULL_SOURCE_DATASET:
                if primary is not None and primary.quality_flags:
                    note_parts.append("source_flags=" + "|".join(primary.quality_flags))
                    if "attribution_missing" in primary.quality_flags:
                        note_parts.append("attribution_missing")
        else:
            canonical_record = _pick_canonical_chgis_record(group.chgis_records)
            canonical_name = canonical_record.name_ch or canonical_record.name_py
            name_lang = "zh" if canonical_record.name_ch else "zh-Latn"
            place_type, basis = _place_type_for_chgis(group.chgis_records)
            note_parts = [
                f"sys_id={group.external_id}",
                f"records={len(group.chgis_records)}",
                f"canonical_record_index={canonical_record.record_index}",
                f"type_py={canonical_record.type_py}",
                f"type_ch={canonical_record.type_ch}",
                f"lev_rank={canonical_record.lev_rank}",
                f"place_type_basis={basis}",
            ]
            expected_layer = "prefecture" if group.source_dataset == "chgis_pref" else "county"
            observed = LEV_RANK_TO_PLACE_TYPE.get((canonical_record.lev_rank or "").strip(), "unknown")
            if observed != f"admin_center_{expected_layer}":
                lev_rank_vs_layer_disagreements += 1
                note_parts.append(f"lev_rank_disagrees_with_layer={expected_layer}")
            if not canonical_record.name_ch:
                note_parts.append("canonical_name_fell_back_to_pinyin")

        place_type_counts[place_type] += 1
        place_type_basis[basis.split("=")[0]] += 1
        children = extra_children.get(f"{group.source_dataset}:{group.external_id}", [])
        time_from, time_to, time_bound_type, time_derivation = _place_time_bounds(
            group, children
        )
        place_time_bound_counts[time_bound_type] += 1
        place_time_derivation_counts[time_derivation] += 1
        places.append(
            {
                "place_id": group.place_id,
                "canonical_name": canonical_name,
                "canonical_name_lang": name_lang,
                "place_type": place_type,
                "source_id": _source_id_for_dataset(group.source_dataset),
                "source_dataset": group.source_dataset,
                "primary_external_id": group.external_id,
                "record_status": "staging",
                "locked": "false",
                "created_at": ingested_at,
                "valid_from_year_astro": time_from,
                "valid_to_year_astro": time_to,
                "time_bound_type": time_bound_type,
                "time_derivation": time_derivation,
                "notes": "; ".join(note_parts),
            }
        )

    stats["place_type_counts"] = dict(sorted(place_type_counts.items()))
    stats["place_type_basis"] = dict(sorted(place_type_basis.items()))
    stats["lev_rank_vs_layer_disagreements"] = lev_rank_vs_layer_disagreements
    stats["lev_rank_mapping_rule"] = dict(LEV_RANK_TO_PLACE_TYPE)
    stats["place_time_bound_type_counts"] = dict(sorted(place_time_bound_counts.items()))
    stats["place_time_derivation_counts"] = dict(
        sorted(place_time_derivation_counts.items())
    )

    # ------------------------------------------------------------------
    # 4. locations + names + issues
    # ------------------------------------------------------------------
    loc_ids = _IdAllocator("loc_", 7)
    name_ids = _IdAllocator("nm_", 7)
    issue_ids = _IdAllocator("dq_", 7)

    locations: List[Dict[str, str]] = []
    names: List[Dict[str, str]] = []
    issues: List[Dict[str, str]] = []

    quality_flag_counts: Counter = Counter()
    crs_confidence_counts: Counter = Counter()
    geometry_type_counts: Counter = Counter()
    time_bound_type_counts: Counter = Counter()
    # Denominator bookkeeping for ``time_bound_type_counts``: the counter is fed
    # from three different loops, so the total cannot be reconstructed from any
    # one output table.  Track each contributor explicitly.
    time_bound_type_denominator: Counter = Counter()
    rule_code_counts: Counter = Counter()
    snapshot_basis_counts: Counter = Counter()
    name_type_counts: Counter = Counter()
    inversion_records: List[ChgisRecord] = []

    def add_issue(
        source_dataset: str,
        source_record_id: str,
        issue_type: str,
        severity: str,
        field_name: str,
        observed_value: str,
        expected_rule: str,
        action_taken: str,
        notes: str,
    ) -> None:
        """Append one row to ``data_quality_issues``."""
        issues.append(
            {
                "issue_id": issue_ids.next(),
                "source_id": _source_id_for_dataset(source_dataset),
                "source_dataset": source_dataset,
                "source_record_id": source_record_id,
                "issue_type": issue_type,
                "severity": severity,
                "field_name": field_name,
                "observed_value": observed_value,
                "expected_rule": expected_rule,
                "action_taken": action_taken,
                "notes": notes,
            }
        )

    for group in ordered_groups:
        if group.source_dataset == MCGD_SOURCE_DATASET:
            for record in group.mcgd_records:
                source_record_id = mcgd_source_record_ids[record.record_index]
                time_bound_type_counts["unknown"] += 1
                time_bound_type_denominator["mcgd_rows"] += 1
                names.append(
                    {
                        "name_id": name_ids.next(),
                        "place_id": group.place_id,
                        "name": record.name,
                        "name_lang": "zh-Latn",
                        "name_script": "Latn",
                        "name_type": "primary",
                        "transliteration_scheme": "wade_giles_probable",
                        "valid_from_year_astro": "",
                        "valid_to_year_astro": "",
                        "time_bound_type": "unknown",
                        "time_rule_code": "",
                        "source_record_id": source_record_id,
                        "notes": (
                            "MCGD Name is the dataset's only name field and is its primary label, "
                            "stored in romanised form; apostrophes ('A-ch'eng') and the 'Hsien'/'Shih' "
                            "suffixes indicate a Wade-Giles base with pinyin remnants, so the exact "
                            "scheme is recorded as probable only. valid_from/valid_to left empty "
                            "because MCGD carries no temporal columns."
                        ),
                    }
                )
                name_type_counts["primary"] += 1

            canonical_record = _pick_canonical_mcgd_record(group.mcgd_records)
            location_id = loc_ids.next()
            lon = canonical_record.lon
            lat = canonical_record.lat
            flags: List[str] = ["crs_unknown"]
            coord_ok = lon is not None and lat is not None
            if not coord_ok:
                flags.append("missing_coordinate")
            else:
                if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
                    flags.append("coordinate_out_of_range")
                elif not (CHINA_LON_RANGE[0] <= lon <= CHINA_LON_RANGE[1]) or not (
                    CHINA_LAT_RANGE[0] <= lat <= CHINA_LAT_RANGE[1]
                ):
                    flags.append("coordinate_outside_china_bbox")
            quality_flag_counts.update(flags)

            locations.append(
                {
                    "location_id": location_id,
                    "place_id": group.place_id,
                    "geom_type": "Point",
                    "lon": format_number(lon),
                    "lat": format_number(lat),
                    "geom_wkt": f"POINT({format_number(lon)} {format_number(lat)})" if coord_ok else "",
                    "representative_lon": format_number(lon),
                    "representative_lat": format_number(lat),
                    "original_x": canonical_record.raw.get("LONG", ""),
                    "original_y": canonical_record.raw.get("LAT", ""),
                    "original_crs": "unknown",
                    "crs_confidence": _crs_confidence_for(SOURCE_ID_MCGD),
                    "axis_order_verified": "true",
                    "location_precision": "point",
                    "uncertainty_m": "",
                    "valid_from_year_astro": "",
                    "valid_to_year_astro": "",
                    "time_bound_type": "unknown",
                    "time_rule_code": "",
                    "quality_flag": "|".join(flags),
                    "source_record_id": mcgd_source_record_ids[canonical_record.record_index],
                    "notes": (
                        f"{MCGD_CRS_NOTE}; geography_hint prov_zh={canonical_record.prov_zh} "
                        f"prov_py={canonical_record.prov_py} provid={canonical_record.prov_id} "
                        f"code={canonical_record.code}; loc_id={group.external_id}; "
                        f"rows_sharing_this_location={len(group.mcgd_records)}; "
                        "no temporal columns in MCGD so time_bound_type is unknown"
                    ),
                }
            )
            crs_confidence_counts[f"{SOURCE_ID_MCGD}:unknown"] += 1
            add_issue(
                MCGD_SOURCE_DATASET,
                mcgd_source_record_ids[canonical_record.record_index],
                "unknown_crs",
                "warning",
                "LAT/LONG",
                f"lon={format_number(lon)};lat={format_number(lat)}",
                "location records must carry a documented CRS before entering production "
                "position data",
                "needs_manual_review",
                "MCGD declares no CRS; axis order is verified from the column names and a "
                "physical-impossibility cross-check, but the datum is unknown, not merely "
                "inferred",
            )
            if coord_ok and (
                not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0)
            ):
                add_issue(
                    MCGD_SOURCE_DATASET,
                    mcgd_source_record_ids[canonical_record.record_index],
                    "coordinate_out_of_range",
                    "blocking",
                    "LONG",
                    f"lon={format_number(lon)},lat={format_number(lat)}",
                    "longitude in [-180,180] and latitude in [-90,90]",
                    "preserved_and_flagged",
                    "longitude exceeds 180 degrees; value cannot be a valid WGS84 longitude",
                )
            elif coord_ok and (
                not (CHINA_LON_RANGE[0] <= lon <= CHINA_LON_RANGE[1])
                or not (CHINA_LAT_RANGE[0] <= lat <= CHINA_LAT_RANGE[1])
            ):
                add_issue(
                    MCGD_SOURCE_DATASET,
                    mcgd_source_record_ids[canonical_record.record_index],
                    "coordinate_outside_china_bbox",
                    "warning",
                    "LONG",
                    f"lon={format_number(lon)},lat={format_number(lat)}",
                    "expected inside the China bbox "
                    f"lon[{CHINA_LON_RANGE[0]},{CHINA_LON_RANGE[1]}] "
                    f"lat[{CHINA_LAT_RANGE[0]},{CHINA_LAT_RANGE[1]}]",
                    "needs_manual_review",
                    "coordinate is numerically valid but lies outside China",
                )
            if not coord_ok:
                add_issue(
                    MCGD_SOURCE_DATASET,
                    mcgd_source_record_ids[canonical_record.record_index],
                    "missing_coordinate",
                    "blocking",
                    "LAT/LONG",
                    f"lat={canonical_record.raw.get('LAT', '')};lon={canonical_record.raw.get('LONG', '')}",
                    "both coordinates must parse as numbers",
                    "needs_manual_review",
                    "coordinate could not be parsed",
                )
            continue

        # ---- non-CHGIS group (Pleiades / WHG) ---------------------------
        if group.source_dataset in EXTRA_SOURCE_DATASETS:
            children = extra_children.get(f"{group.source_dataset}:{group.external_id}", [])
            for record in children:
                source_record_id = extra_child_source_record_ids[
                    (record.source_dataset, record.raw_file, record.record_index)
                ]
                time_bound_type_counts[record.time_bound_type] += 1
                time_bound_type_denominator["extra_child_rows"] += 1
                if record.time_bound_type == "tpq_taq":
                    rule_code_counts[f"{record.source_id}:tpq_taq_pair"] += 1
                from_astro, to_astro = _extra_years(record)
                quality_flag_counts.update(record.quality_flags)
                if "parent_place_not_in_sample" in record.quality_flags:
                    add_issue(
                        record.source_dataset,
                        source_record_id,
                        "parent_place_not_in_sample",
                        "info",
                        "place_id",
                        record.parent_external_id,
                        "every child row's parent place should be inside the slice",
                        "preserved_and_flagged",
                        "the parent place falls outside the 1 MB slice window, so the "
                        "child row is kept in source_records but cannot be attached to "
                        "a historical_places row; the row itself is real Pleiades data",
                    )

                if record.record_kind == "name":
                    names.append(
                        {
                            "name_id": name_ids.next(),
                            "place_id": group.place_id,
                            "name": record.name,
                            "name_lang": _extra_name_lang(record),
                            "name_script": record.name_script,
                            "name_type": record.name_type,
                            "transliteration_scheme": "",
                            "valid_from_year_astro": from_astro,
                            "valid_to_year_astro": to_astro,
                            "time_bound_type": record.time_bound_type,
                            "time_rule_code": record.time_rule_code,
                            "source_record_id": source_record_id,
                            "notes": record.notes,
                        }
                    )
                    name_type_counts[record.name_type] += 1
                elif record.record_kind == "location":
                    # CRS is decided per row, not per source: one source can carry
                    # rows of different evidential strength (WHG's conformant
                    # GeoJSON vs its GeoJSON-shaped plain JSON).
                    row_original_crs = record.original_crs or "EPSG:4326"
                    row_crs_confidence = record.crs_confidence or _crs_confidence_for(
                        record.source_id
                    )
                    row_flags = list(record.quality_flags)
                    if row_crs_confidence == "unknown" and "crs_unknown" not in row_flags:
                        row_flags.append("crs_unknown")
                    # M4-4a：几何类型由 WKT 首词决定，不再一律写 Point。
                    # 面/线的 representative_lon/lat 已在抽取阶段用
                    # ST_PointOnSurface / ST_LineInterpolatePoint 等价算法算好，
                    # 否则地图查询（要求 representative_* 非空）看不到这些地点。
                    row_geom_type = _geom_type_of_wkt(record.geom_wkt)
                    row_is_point = row_geom_type == "Point"
                    locations.append(
                        {
                            "location_id": loc_ids.next(),
                            "place_id": group.place_id,
                            "geom_type": row_geom_type,
                            "lon": format_number(record.lon),
                            "lat": format_number(record.lat),
                            "geom_wkt": record.geom_wkt,
                            "representative_lon": format_number(record.lon),
                            "representative_lat": format_number(record.lat),
                            "original_x": record.lon_text if row_is_point else "",
                            "original_y": record.lat_text if row_is_point else "",
                            "original_crs": row_original_crs,
                            "crs_confidence": row_crs_confidence,
                            "axis_order_verified": "true",
                            "location_precision": record.location_precision or "point",
                            "uncertainty_m": record.uncertainty_m,
                            "valid_from_year_astro": from_astro,
                            "valid_to_year_astro": to_astro,
                            "time_bound_type": record.time_bound_type,
                            "time_rule_code": record.time_rule_code,
                            "quality_flag": "|".join(row_flags),
                            "source_record_id": source_record_id,
                            "notes": record.notes,
                        }
                    )
                    geometry_type_counts[row_geom_type] += 1
                    crs_confidence_counts[f"{record.source_id}:{row_crs_confidence}"] += 1
                    # ``record.quality_flags`` was already folded into
                    # ``quality_flag_counts`` by the child loop above; only the flag
                    # added here still needs counting.
                    if "crs_unknown" in row_flags and "crs_unknown" not in record.quality_flags:
                        quality_flag_counts["crs_unknown"] += 1
                    if row_crs_confidence == "unknown":
                        add_issue(
                            record.source_dataset,
                            source_record_id,
                            "unknown_crs",
                            "warning",
                            "geometry",
                            f"lon={format_number(record.lon)};lat={format_number(record.lat)}",
                            "location records must carry a documented CRS before entering "
                            "production position data",
                            "needs_manual_review",
                            "the row declares no CRS and its container format does not "
                            "mandate one (GeoJSON-shaped plain JSON is not a conformant "
                            "GeoJSON document), so crs_confidence is 'unknown'",
                        )
            continue

        # ---- CHGIS group ------------------------------------------------
        for record in group.chgis_records:
            source_record_id = source_record_ids[(record.source_dataset, record.record_index)]
            beg = record.beg_year
            end = record.end_year
            years = _chgis_record_years(record)
            inverted = years["inverted"]
            time_bound_type = years["time_bound_type"]
            valid_from = years["valid_from"]
            valid_to = years["valid_to"]
            rule_code = years["time_rule_code"]
            rule_code_counts[f"BEG_RULE={record.beg_rule or '<blank>'}"] += 1
            rule_code_counts[f"END_RULE={record.end_rule or '<blank>'}"] += 1
            if time_bound_type == "snapshot":
                snapshot_basis_counts[years["snapshot_basis"]] += 1
            time_bound_type_counts[time_bound_type] += 1
            time_bound_type_denominator["chgis_records"] += 1

            flags = []
            if inverted:
                flags.append("beg_gt_end")
                inversion_records.append(record)
            if not record.has_coordinate:
                flags.append("missing_coordinate")
            elif not (-180.0 <= (record.lon or 0.0) <= 180.0) or not (
                -90.0 <= (record.lat or 0.0) <= 90.0
            ):
                flags.append("coordinate_out_of_range")
            elif not (CHINA_LON_RANGE[0] <= (record.lon or 0.0) <= CHINA_LON_RANGE[1]) or not (
                CHINA_LAT_RANGE[0] <= (record.lat or 0.0) <= CHINA_LAT_RANGE[1]
            ):
                flags.append("coordinate_outside_china_bbox")
            quality_flag_counts.update(flags)
            quality_flag_counts["clean" if not flags else "flagged"] += 1

            coord_ok = record.has_coordinate
            locations.append(
                {
                    "location_id": loc_ids.next(),
                    "place_id": group.place_id,
                    "geom_type": "Point",
                    "lon": format_number(record.lon),
                    "lat": format_number(record.lat),
                    "geom_wkt": (
                        f"POINT({format_number(record.lon)} {format_number(record.lat)})"
                        if coord_ok
                        else ""
                    ),
                    "representative_lon": format_number(record.lon),
                    "representative_lat": format_number(record.lat),
                    "original_x": record.lon_text,
                    "original_y": record.lat_text,
                    "original_crs": "EPSG:4326",
                    "crs_confidence": "confirmed",
                    "axis_order_verified": "true",
                    "location_precision": "point",
                    "uncertainty_m": "",
                    "valid_from_year_astro": valid_from,
                    "valid_to_year_astro": valid_to,
                    "time_bound_type": time_bound_type,
                    "time_rule_code": rule_code,
                    "quality_flag": "|".join(flags),
                    "source_record_id": source_record_id,
                    "notes": (
                        f"{CHGIS_CRS_NOTE}; record_index={record.record_index}; "
                        f"raw_beg_yr={record.raw.get('BEG_YR', '')}; raw_end_yr={record.raw.get('END_YR', '')}; "
                        f"beg_rule={record.beg_rule or '<blank>'} ({date_rules.describe(record.beg_rule)}); "
                        f"end_rule={record.end_rule or '<blank>'} ({date_rules.describe(record.end_rule)})"
                        + ("; valid_from/valid_to suppressed because raw BEG_YR > END_YR" if inverted else "")
                        + (
                            "; SNAPSHOT: rule 9 is a time slice, so valid_from and "
                            "valid_to both hold the slice year "
                            f"({valid_from}) and the row claims no interval; raw "
                            f"BEG_YR={record.raw.get('BEG_YR', '')} / END_YR="
                            f"{record.raw.get('END_YR', '')} are preserved verbatim"
                            if time_bound_type == "snapshot"
                            else ""
                        )
                        + ("; coordinate lost to DBF field-overflow marker" if not coord_ok else "")
                    ),
                }
            )
            crs_confidence_counts[f"{SOURCE_ID_CHGIS}:confirmed"] += 1

            # ---- names -------------------------------------------------
            # A name inherits exactly the record's own time statement, including
            # the snapshot collapse, so a name can never claim a longer life
            # than the row it came from.
            name_time_bound_type = time_bound_type
            name_from = valid_from
            name_to = valid_to

            if record.name_ch:
                name_notes = (
                    f"NAME_CH from record {record.record_index}; this is the name attested for the "
                    "entity during this record's own time window, not the entity's total lifespan"
                )
                names.append(
                    {
                        "name_id": name_ids.next(),
                        "place_id": group.place_id,
                        "name": record.name_ch,
                        "name_lang": "zh",
                        "name_script": "Hani",
                        "name_type": "primary",
                        "transliteration_scheme": "",
                        "valid_from_year_astro": name_from,
                        "valid_to_year_astro": name_to,
                        "time_bound_type": name_time_bound_type,
                        "time_rule_code": rule_code,
                        "source_record_id": source_record_id,
                        "notes": name_notes,
                    }
                )
                name_type_counts["primary"] += 1
            else:
                add_issue(
                    record.source_dataset,
                    source_record_id,
                    "empty_name",
                    "warning",
                    "NAME_CH",
                    "",
                    "NAME_CH should be non-empty",
                    "preserved_and_flagged",
                    "no vernacular name on this record",
                )

            if record.name_py:
                names.append(
                    {
                        "name_id": name_ids.next(),
                        "place_id": group.place_id,
                        "name": record.name_py,
                        "name_lang": "zh-Latn",
                        "name_script": "Latn",
                        "name_type": "transliteration",
                        "transliteration_scheme": "pinyin",
                        "valid_from_year_astro": name_from,
                        "valid_to_year_astro": name_to,
                        "time_bound_type": name_time_bound_type,
                        "time_rule_code": rule_code,
                        "source_record_id": source_record_id,
                        "notes": "NAME_PY from the same record as the primary NAME_CH name",
                    }
                )
                name_type_counts["transliteration"] += 1

            if record.name_ft and record.name_ft != record.name_ch:
                names.append(
                    {
                        "name_id": name_ids.next(),
                        "place_id": group.place_id,
                        "name": record.name_ft,
                        "name_lang": "zh",
                        "name_script": "Hant",
                        "name_type": "alternate",
                        "transliteration_scheme": "",
                        "valid_from_year_astro": name_from,
                        "valid_to_year_astro": name_to,
                        "time_bound_type": name_time_bound_type,
                        "time_rule_code": rule_code,
                        "source_record_id": source_record_id,
                        "notes": "NAME_FT differs from NAME_CH (traditional-character form)",
                    }
                )
                name_type_counts["alternate"] += 1

            # ---- per-record issues -------------------------------------
            if inverted:
                add_issue(
                    record.source_dataset,
                    source_record_id,
                    "beg_gt_end",
                    "blocking",
                    "BEG_YR/END_YR",
                    f"BEG_YR={record.raw.get('BEG_YR', '')};END_YR={record.raw.get('END_YR', '')}",
                    "BEG_YR <= END_YR",
                    "preserved_and_flagged",
                    f"years kept verbatim (delta={beg - end} years); valid_from/valid_to left "
                    "empty because the interval cannot be trusted; values were NOT swapped",
                )
            if beg is None:
                add_issue(
                    record.source_dataset, source_record_id, "null_beg_year", "warning", "BEG_YR",
                    record.raw.get("BEG_YR", ""), "BEG_YR must hold a year", "preserved_and_flagged",
                    "begin year blank or the DBF overflow marker",
                )
            if end is None:
                add_issue(
                    record.source_dataset, source_record_id, "null_end_year", "warning", "END_YR",
                    record.raw.get("END_YR", ""), "END_YR must hold a year", "preserved_and_flagged",
                    "end year blank or the DBF overflow marker",
                )
            if beg is not None and end is not None and beg == end:
                add_issue(
                    record.source_dataset, source_record_id, "beg_eq_end", "info", "BEG_YR/END_YR",
                    f"BEG_YR={beg};END_YR={end}",
                    "BEG_YR < END_YR for a span; equal years are valid only for a time slice "
                    "(date rule 9)",
                    "preserved_and_flagged",
                    f"single-year span; beg_rule={record.beg_rule or '<blank>'}, "
                    f"end_rule={record.end_rule or '<blank>'}",
                )
            for label, value in (("BEG_YR", beg), ("END_YR", end)):
                reason = year_out_of_range_reason(value)
                if reason:
                    add_issue(
                        record.source_dataset, source_record_id, "year_out_of_range", "warning",
                        label, str(value), reason, "preserved_and_flagged",
                        "year magnitude is implausible for the layer's scope",
                    )
            if not record.has_coordinate:
                add_issue(
                    record.source_dataset, source_record_id, "missing_coordinate", "blocking",
                    "X_COOR/Y_COOR",
                    f"X_COOR={record.lon_text};Y_COOR={record.lat_text}",
                    "both coordinates must be numeric",
                    "preserved_and_flagged",
                    "coordinate replaced by the DBF all-asterisk overflow marker; the true value "
                    "was lost upstream, not by this pipeline",
                )
            elif not (-180.0 <= (record.lon or 0.0) <= 180.0) or not (
                -90.0 <= (record.lat or 0.0) <= 90.0
            ):
                add_issue(
                    record.source_dataset, source_record_id, "coordinate_out_of_range", "blocking",
                    "X_COOR/Y_COOR",
                    f"X_COOR={record.lon_text};Y_COOR={record.lat_text}",
                    "lon in [-180,180], lat in [-90,90]",
                    "preserved_and_flagged",
                    "value cannot be a valid WGS84 longitude/latitude",
                )
            elif not (CHINA_LON_RANGE[0] <= (record.lon or 0.0) <= CHINA_LON_RANGE[1]) or not (
                CHINA_LAT_RANGE[0] <= (record.lat or 0.0) <= CHINA_LAT_RANGE[1]
            ):
                add_issue(
                    record.source_dataset, source_record_id, "coordinate_outside_china_bbox",
                    "warning", "X_COOR/Y_COOR",
                    f"X_COOR={record.lon_text};Y_COOR={record.lat_text}",
                    "expected inside the China bbox",
                    "needs_manual_review",
                    "numerically valid but outside China",
                )
            if rule_basis_available:
                # One row per record (not per field) so the issue table stays
                # filterable without being dominated by 12k duplicate rows: the
                # county layer alone leaves BEG_RULE blank on 58% of its records.
                undocumented_fields = [
                    (label, code)
                    for label, code in (
                        ("BEG_RULE", record.beg_rule),
                        ("END_RULE", record.end_rule),
                    )
                    if (code or "").strip() not in date_rules.rules
                ]
                if undocumented_fields and time_bound_type == "unknown":
                    add_issue(
                        record.source_dataset, source_record_id, "unknown_time_bound_type", "info",
                        "|".join(label for label, _code in undocumented_fields),
                        ";".join(
                            f"{label}={code or '<blank>'}" for label, code in undocumented_fields
                        ),
                        "every BEG_RULE/END_RULE code should appear in xtra_date_rules so the "
                        "determinacy of the year can be established",
                        "preserved_and_flagged",
                        "one row per record listing each field whose rule code is blank or absent "
                        "from the CHGIS date-rule workbook; time_bound_type is 'unknown' for this "
                        "record and time_rule_code keeps the raw pair",
                    )

    # Duplicate SYS_ID bookkeeping happens outside the group loop because the
    # identity model collapses them into one place.
    by_sysid: Dict[Tuple[str, str], List[ChgisRecord]] = defaultdict(list)
    for record in chgis_records:
        by_sysid[(record.source_dataset, record.sys_id_text)].append(record)
    for key, members in sorted(by_sysid.items()):
        if len(members) <= 1:
            continue
        for extra in members[1:]:
            add_issue(
                extra.source_dataset,
                source_record_ids[(extra.source_dataset, extra.record_index)],
                "duplicate_sysid",
                "warning",
                "SYS_ID",
                extra.sys_id_text,
                "SYS_ID should occur once per spatial object per the CHGIS data dictionary",
                "needs_manual_review",
                f"record_index {extra.record_index} repeats SYS_ID held by record_index "
                f"{members[0].record_index}; name={extra.name_ch}, years={extra.raw.get('BEG_YR','')}"
                f"-{extra.raw.get('END_YR','')}, coord={extra.lon_text},{extra.lat_text}",
            )

    for quirk in field_quirks:
        add_issue(
            quirk.source_dataset,
            "",
            "nonstandard_field_name",
            "info",
            quirk.field_name,
            quirk.field_name,
            quirk.expected_name,
            "preserved_and_flagged",
            f"field name differs from the sibling layer ({quirk.note}); no aliasing was applied "
            "so the raw name stays visible in chgis_all_records.csv",
        )

    stats["quality_flag_counts"] = dict(sorted(quality_flag_counts.items()))
    stats["location_geometry_type_counts"] = dict(sorted(geometry_type_counts.items()))
    stats["crs_confidence_counts"] = dict(sorted(crs_confidence_counts.items()))
    stats["crs_confidence_rule"] = {
        "vocabulary": list(CRS_CONFIDENCE_VALUES),
        "by_source": dict(CRS_CONFIDENCE_BY_SOURCE),
        "original_crs": "what the source declares; 'unknown' when it declares nothing",
        "crs_confidence": (
            "how sure we are the coordinates really are EPSG:4326: confirmed = the "
            "source states WGS84 (CHGIS .prj, Pleiades gis_README.md); inferred = no "
            "explicit statement, but the format specification mandates WGS84 AND the "
            "file conforms to that specification (RFC 7946 GeoJSON -> WHG's JSON-LD "
            "records); being merely GeoJSON-SHAPED is not enough, so WHG's older flat "
            "schema (geoms[].coordinates present, but no @context and no crs member) is "
            "'unknown'; unknown = neither, i.e. MCGD (no datum declared) and those WHG "
            "flat rows; plausible numbers are a sanity check, not CRS evidence"
        ),
        "per_row": (
            "crs_confidence is decided per location row, not per source: WHG carries "
            "inferred for its 5 conformant GeoJSON rows and unknown for its 3 "
            "GeoJSON-shaped plain-JSON rows, and every 'unknown' row also carries "
            "quality_flag 'crs_unknown' plus an 'unknown_crs' warning issue"
        ),
        "axis_order_verified": (
            "a SEPARATE question from CRS confidence: MCGD's axis order is verified "
            "from its LAT/LONG column names plus a physical-impossibility check while "
            "its CRS stays 'unknown'; those two facts do not conflict"
        ),
    }
    stats["time_bound_type_counts"] = dict(sorted(time_bound_type_counts.items()))
    stats["time_bound_type_denominator"] = {
        **dict(sorted(time_bound_type_denominator.items())),
        "total": sum(time_bound_type_counts.values()),
        "note": (
            "what the record-level time_bound_type distribution counts: every CHGIS "
            "record, every MCGD source row, and every Pleiades/WHG child row that is "
            "attached to a place inside the slice. Pleiades/WHG place rows are excluded "
            "(they carry no years of their own) and so are orphan child rows, whose "
            "parents fall outside the 1 MB slice."
        ),
    }
    stats["time_bound_type_vocabulary"] = list(TIME_BOUND_TYPES)
    stats["time_derivation_vocabulary"] = list(TIME_DERIVATIONS)
    stats["snapshot_basis_counts"] = dict(sorted(snapshot_basis_counts.items()))
    stats["rule_code_counts"] = dict(sorted(rule_code_counts.items()))
    stats["name_type_counts"] = dict(sorted(name_type_counts.items()))
    stats["time_inversion_records"] = len(inversion_records)
    stats["date_rule_dictionary"] = {
        "loaded": date_rules.loaded,
        "source_member": date_rules.source_member,
        "error": date_rules.error,
        "documented_codes": date_rules.documented_codes(),
        "entries": date_rules.rules,
    }

    # ------------------------------------------------------------------
    # 5. extra-source issues (truncated tails, licence, axis notes)
    # ------------------------------------------------------------------
    for extraction in extra_extractions:
        for discarded in extraction.stats.get("discarded_tail_rows", []):
            add_issue(
                extraction.source_dataset,
                "",
                "truncated_slice_tail",
                "info",
                "record_tail",
                (
                    f"file={discarded['file']}; parsed_fields={discarded['parsed_fields']}"
                    f"/{discarded['expected_fields']}; head={discarded['leading_cells']}"
                ),
                "a complete CSV record has as many fields as the header",
                "discarded",
                "the HTTP Range slice ends mid-record, so this tail is truncated "
                "transport data rather than a defective row; it is dropped and "
                "counted so the row total in this table reconciles",
            )

    for group in ordered_groups:
        if group.source_dataset not in EXTRA_SOURCE_DATASETS:
            continue
        if group.source_dataset == PLEIADES_FULL_SOURCE_DATASET:
            # v4.1 全量分支的台账在下面单独追加（见 "v4.1 全量台账"），
            # 因为它多了 geometry_invalid_repaired / connection_endpoint_missing /
            # accuracy_unknown_sentinel 三类，而且必须排在所有既有 dq_ 行之后，
            # 这样既有暂存的台账 id 一个都不会移位。
            continue
        primary = group.primary_extra
        if primary is None:
            continue
        source_record_id = extra_source_record_ids.get(
            (group.source_dataset, group.external_id), ""
        )
        if "attribution_missing" in primary.quality_flags:
            # M4-2：许可门禁已取消，本行不再是阻断项，只作为来源元数据缺失的观察保留。
            add_issue(
                group.source_dataset,
                source_record_id,
                "attribution_missing",
                "info",
                "attribution",
                "no attribution block in the source payload",
                "attribution text is optional provenance, not an import gate",
                "preserved_and_flagged",
                "the flat HGIS records carry no per-record attribution; the row is "
                "imported as-is (M4-2: licensing is the Owner's responsibility and "
                "gates nothing)",
            )
        for flag in primary.quality_flags:
            if flag in ("attribution_missing",):
                continue
            add_issue(
                group.source_dataset,
                source_record_id,
                flag,
                "warning" if flag != "missing_coordinate" else "blocking",
                "representative_lat/lon" if flag == "missing_coordinate" else "geometry",
                primary.coord_key or "",
                "a place row should carry a parseable coordinate",
                "preserved_and_flagged",
                "flagged by the source extractor; the value was not repaired",
            )

    # Orphan children: rows whose parent place fell outside the slice window.
    # They never enter a PlaceGroup, so without this pass their
    # ``parent_place_not_in_sample`` flag would exist on the extractor object and
    # nowhere in the output.  One issue row per row keeps the count reconcilable
    # (4,810) and lets a reviewer join back to source_records.source_record_id.
    orphan_count = 0
    for extraction in extra_extractions:
        for record in extraction.records:
            if record.record_kind not in ("name", "location", "connection"):
                continue
            if "parent_place_not_in_sample" not in record.quality_flags:
                continue
            orphan_count += 1
            add_issue(
                record.source_dataset,
                extra_child_source_record_ids.get(
                    (record.source_dataset, record.raw_file, record.record_index), ""
                ),
                "parent_place_not_in_sample",
                "info",
                "place_id",
                record.parent_external_id,
                "every child row's parent place should be inside the slice",
                "preserved_and_flagged",
                f"the parent place falls outside the 1 MB slice window of "
                f"{record.raw_file}, so this row is kept in source_records but has no "
                "historical_places row to attach to; the row itself is real source data",
            )
    stats["extra_orphan_child_rows"] = orphan_count

    # ------------------------------------------------------------------
    # 5b. Pleiades v4.1 全量台账（追加在最后，既有 dq_ 编号不动）
    # ------------------------------------------------------------------
    # 四类，全部由抽取阶段写在记录上的 quality_flag 决定，不在这里重新判断：
    #   missing_coordinate          7,200  地点行没有代表点（place 级 flag）
    #   geometry_invalid_repaired       4  面 WKT 无效、已修复
    #   connection_endpoint_missing    28  连接至少一端解析不到 place_id
    #   accuracy_unknown_sentinel     728  合成代表点的 min_accuracy_meters = -1
    # 另有两类**明确不开票**，写在这里是为了让"为什么没有"也可审计：
    #   z_ordinate_discarded       Z 序降维是表示层处理，不构成数据缺陷
    #   parent_place_not_in_sample 全量包无孤儿（切片时代才有 4,810 条）
    full_issues: List[Dict[str, str]] = []

    def add_full_issue(
        source_dataset: str,
        source_record_id: str,
        issue_type: str,
        severity: str,
        field_name: str,
        observed_value: str,
        expected_rule: str,
        action_taken: str,
        notes: str,
    ) -> None:
        """Append one v4.1 ledger row to the deferred list."""
        full_issues.append(
            {
                "issue_id": issue_ids.next(),
                "source_id": _source_id_for_dataset(source_dataset),
                "source_dataset": source_dataset,
                "source_record_id": source_record_id,
                "issue_type": issue_type,
                "severity": severity,
                "field_name": field_name,
                "observed_value": observed_value,
                "expected_rule": expected_rule,
                "action_taken": action_taken,
                "notes": notes,
            }
        )

    full_issue_counts: Counter = Counter()
    for group in ordered_groups:
        if group.source_dataset != PLEIADES_FULL_SOURCE_DATASET:
            continue
        primary = group.primary_extra
        if primary is None:
            continue
        source_record_id = extra_source_record_ids.get(
            (group.source_dataset, group.external_id), ""
        )
        for flag in primary.quality_flags:
            if flag == "missing_coordinate":
                add_full_issue(
                    group.source_dataset,
                    source_record_id,
                    "missing_coordinate",
                    "blocking",
                    "representative_lat/lon",
                    primary.coord_key or "",
                    "a place row should carry a parseable coordinate",
                    "preserved_and_flagged",
                    "places.csv 该行没有 representative_latitude/longitude，"
                    "也没有任何 location 行；地点仍建，地图不显示（验收指标 "
                    "place_without_geometry = 7,200，按 Owner 决策不另开第二类台账）",
                )
                full_issue_counts["missing_coordinate"] += 1
            elif flag == "coordinate_out_of_range":
                add_full_issue(
                    group.source_dataset,
                    source_record_id,
                    "coordinate_out_of_range",
                    "blocking",
                    "representative_lat/lon",
                    primary.coord_key or "",
                    "lon in [-180,180], lat in [-90,90]",
                    "preserved_and_flagged",
                    "坐标越界；值原样保留，未做任何夹取",
                )
                full_issue_counts["coordinate_out_of_range"] += 1

    # 子行三类：位置（修复 / 哨兵）与连接（悬空）
    for extraction in extra_extractions:
        if extraction.source_dataset != PLEIADES_FULL_SOURCE_DATASET:
            continue
        for record in extraction.records:
            if record.record_kind == "location":
                source_record_id = extra_child_source_record_ids.get(
                    (record.source_dataset, record.raw_file, record.record_index), ""
                )
                if "geometry_invalid_repaired" in record.quality_flags:
                    add_full_issue(
                        record.source_dataset,
                        source_record_id,
                        "geometry_invalid_repaired",
                        "warning",
                        "geometry_wkt",
                        record.geom_wkt[:200],
                        "入库几何必须 ST_IsValid=true",
                        "repaired",
                        f"{record.raw_file} 第 {record.record_index} 行：源 WKT 无效，"
                        "经 GEOS MakeValid + 只取面片修复后入库；原始 WKT 保留在 raw_payload",
                    )
                    full_issue_counts["geometry_invalid_repaired"] += 1
                if "accuracy_unknown_sentinel" in record.quality_flags:
                    add_full_issue(
                        record.source_dataset,
                        source_record_id,
                        "accuracy_unknown_sentinel",
                        "info",
                        "uncertainty_m",
                        "-1",
                        "horizontal accuracy in metres, or NULL when unknown",
                        "null_written",
                        "places_accuracy.min_accuracy_meters = -1 是「未知」哨兵，"
                        "不能当 -1 米写库：uncertainty_m 写 NULL 并记本行",
                    )
                    full_issue_counts["accuracy_unknown_sentinel"] += 1
            elif record.record_kind == "connection":
                if "connection_endpoint_missing" not in record.quality_flags:
                    continue
                source_record_id = extra_child_source_record_ids.get(
                    (record.source_dataset, record.raw_file, record.record_index), ""
                )
                add_full_issue(
                    record.source_dataset,
                    source_record_id,
                    "connection_endpoint_missing",
                    "warning",
                    "connects_to/place_id",
                    f"{record.parent_external_id or '<blank>'} -> "
                    f"{record.connects_to_external_id or '<blank>'}",
                    "both endpoints must resolve to a place in places.csv",
                    "preserved_and_flagged",
                    f"connections.csv 第 {record.record_index} 行：至少一端不是 v4.1 的地点；"
                    "源记录照常入库，不生成候选关系（不虚构端点）",
                )
                full_issue_counts["connection_endpoint_missing"] += 1

    issues.extend(full_issues)
    stats["pleiades_full_issue_counts"] = dict(sorted(full_issue_counts.items()))
    stats["pleiades_full_issue_rows"] = len(full_issues)

    # ------------------------------------------------------------------
    # 5. candidate_matches
    # ------------------------------------------------------------------
    candidates = _build_candidates(
        chgis_records=chgis_records,
        place_of_record=place_of_chgis_record,
        source_record_ids=source_record_ids,
        migration_edges=migration_edges,
    )
    stats["candidate_match_counts"] = dict(
        sorted(
            Counter(
                c["relation_type"] for c in candidates if c["relation_type"] != "truncation_notice"
            ).items()
        )
    )
    stats["candidate_match_status"] = dict(
        sorted(
            Counter(
                c["status"] for c in candidates if c["relation_type"] != "truncation_notice"
            ).items()
        )
    )
    stats["candidate_truncation_notices"] = [
        c["evidence"] for c in candidates if c["relation_type"] == "truncation_notice"
    ]
    # Pleiades connections become candidate rows when both endpoints are inside
    # the slice: the source asserts a relation, we only record it.
    connection_candidates, connection_stats = _build_pleiades_connection_candidates(
        extra_extractions,
        extra_source_record_ids,
        extra_child_source_record_ids,
        {
            key: group.place_id
            for key, group in extra_groups.items()
        },
        alias_place_ids,
    )
    candidates.extend(connection_candidates)
    stats["pleiades_connection_candidates"] = connection_stats
    stats["candidate_match_counts"] = dict(
        sorted(
            Counter(
                c["relation_type"] for c in candidates if c["relation_type"] != "truncation_notice"
            ).items()
        )
    )
    stats["candidate_match_status"] = dict(
        sorted(
            Counter(
                c["status"] for c in candidates if c["relation_type"] != "truncation_notice"
            ).items()
        )
    )

    # ------------------------------------------------------------------
    # 6. data_datasets
    # ------------------------------------------------------------------
    dataset_rows = [dataset.as_row() for dataset in iter_datasets()]
    stats["data_datasets_rows"] = len(dataset_rows)
    stats["data_datasets_ids"] = [row["dataset_id"] for row in dataset_rows]

    return NormalizedBundle(
        tables={
            "historical_places": places,
            "historical_place_locations": locations,
            "historical_place_names": names,
            "source_records": pending_source_rows,
            "data_quality_issues": issues,
            "candidate_matches": candidates,
            "data_datasets": dataset_rows,
        },
        stats=stats,
        place_lookup={
            f"{dataset}:{record_index}": place_id
            for (dataset, record_index), place_id in place_of_chgis_record.items()
        },
    )


def _build_pleiades_connection_candidates(
    extra_extractions: Sequence[ExtraExtraction],
    place_source_record_ids: Dict[Tuple[str, str], str],
    child_source_record_ids: Dict[Tuple[str, str, int], str],
    place_ids: Dict[Tuple[str, str], str],
    alias_place_ids: Optional[Dict[Tuple[str, str], str]] = None,
) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    """Turn in-sample Pleiades connections into ``candidate_matches`` rows.

    A ``candidate_matches`` row must name two real ``place_id`` values, so a
    connection is emitted only when *both* endpoints resolve:

      * the endpoint is a place grouped in this run -> its own ``place_id``;
      * the endpoint is a v4.1 place already carried by the slice snapshot ->
        the slice's ``place_id`` through ``alias_place_ids`` (M4-4a).  Without
        this alias 1,358 connections would look dangling even though both ends
        are perfectly well known places.

    Endpoints that are not places at all (``/errata/`` ids, an all-blank row,
    ids absent from ``places.csv``) stay in ``source_records`` with
    ``connection_endpoint_missing`` and never become candidates.

    Args:
      extra_extractions: The Pleiades and WHG extractions.
      place_source_record_ids: ``(source_dataset, external_id)`` -> ``sr_`` id of
        the place row.
      child_source_record_ids: ``(source_dataset, raw_file, record_index)`` ->
        ``sr_`` id of the child row.
      place_ids: ``(source_dataset, external_id)`` -> ``hp_`` id.
      alias_place_ids: ``(source_dataset, external_id)`` -> ``hp_`` id of an
        already-existing place that carries the same real-world entity.

    Returns:
      ``(rows, stats)``.
    """
    alias_place_ids = alias_place_ids or {}
    rows: List[Dict[str, str]] = []
    place_names: Dict[Tuple[str, str], str] = {}
    for extraction in extra_extractions:
        for record in extraction.records:
            if record.record_kind == "place":
                place_names[(record.source_dataset, record.external_id)] = record.name

    def resolve_place(key: Tuple[str, str]) -> str:
        """Place id for one connection endpoint, or ``""`` when unresolvable."""
        found = place_ids.get(key)
        if found:
            return found
        return alias_place_ids.get(key, "")

    def resolve_source_record(key: Tuple[str, str]) -> str:
        """``sr_`` id of the record that owns the endpoint's place row."""
        found = place_source_record_ids.get(key)
        if found:
            return found
        return place_source_record_ids.get(("pleiades_gis_4_1_slice", key[1]), "")

    total = 0
    emitted = 0
    dangling = 0
    aliased = 0
    self_after_alias = 0
    for extraction in extra_extractions:
        for record in extraction.records:
            if record.record_kind != "connection":
                continue
            total += 1
            key_a = (record.source_dataset, record.parent_external_id)
            key_b = (record.source_dataset, record.connects_to_external_id)
            place_a = resolve_place(key_a)
            place_b = resolve_place(key_b)
            if not place_a or not place_b:
                dangling += 1
                continue
            if place_a == place_b:
                # A self-loop survives alias resolution as the same place; the
                # table forbids a == b, and the fact is already carried by the
                # source record's note.
                self_after_alias += 1
                continue
            if key_a not in place_ids or key_b not in place_ids:
                aliased += 1
            emitted += 1
            rows.append(
                {
                    "candidate_id": f"cm_pcn_{emitted:07d}",
                    "relation_type": "pleiades_connection",
                    "place_id_a": place_a,
                    "source_record_id_a": child_source_record_ids.get(
                        (record.source_dataset, record.raw_file, record.record_index), ""
                    ),
                    "name_a": place_names.get(key_a, ""),
                    "lon_a": "",
                    "lat_a": "",
                    "place_id_b": place_b,
                    "source_record_id_b": resolve_source_record(key_b),
                    "name_b": place_names.get(key_b, ""),
                    "lon_b": "",
                    "lat_b": "",
                    "distance_m": "",
                    "same_name": "false",
                    "evidence": (
                        f"source=pleiades connections.csv; connection_type={record.connection_type}; "
                        f"pleiades_place_id_a={key_a[1]}; pleiades_place_id_b={key_b[1]}; "
                        f"pleiades_connection_id={record.external_id}"
                    ),
                    "confidence": "source_asserted",
                    "status": "candidate",
                    "reviewer": "",
                    "reviewed_at": "",
                }
            )
    stats = {
        "connection_rows_total": total,
        "connection_rows_with_both_ends_in_sample": emitted,
        "connection_rows_dropped_target_outside_sample": total - emitted - self_after_alias,
        "connection_rows_self_loop_after_alias": self_after_alias,
        "connection_rows_resolved_through_alias": aliased,
        "connection_rows_unresolvable": dangling,
    }
    return rows, stats


def _record_lonlat(record: ChgisRecord) -> Tuple[str, str]:
    """Render a record's coordinates for the candidate table."""
    return format_number(record.lon), format_number(record.lat)


def _build_candidates(
    chgis_records: Sequence[ChgisRecord],
    place_of_record: Dict[Tuple[str, int], str],
    source_record_ids: Dict[Tuple[str, int], str],
    migration_edges: Sequence[Any] = (),
) -> List[Dict[str, str]]:
    """Generate relationship candidates without ever merging two places.

    Emitted relation types:
      * ``location_migration`` -- one ``SYS_ID`` with two distinct coordinates;
      * ``same_entity_multi_period`` -- one ``SYS_ID`` at one coordinate over
        several periods;
      * ``true_duplicate_suspected`` -- identical ``SYS_ID``, coordinate and year
        pair, differing only in physical record index;
      * ``same_coord_diff_entity`` -- different places sharing one exact
        coordinate (comital seats, nested administrations, same-city offices);
      * ``homonym_diff_place`` -- one ``NAME_CH`` at several coordinates, limited
        to pairs closer than 200 km because those are the ones a name-based
        matcher would wrongly fuse;
      * plus, when ``migration_edges`` is supplied, the rule-based adjacent-pair
        verdicts from :mod:`chgis_migration`: ``same_entity_same_seat``,
        ``location_migration_candidate`` and (for legs beyond 300 km)
        ``homonym_diff_place``.

    The first five come from spatial/SYS_ID evidence and are the only relations
    that can be derived without a temporal model.  The last group is the only
    place migration can appear at all, because ``SYS_ID`` identifies a spatial
    object rather than a continuing entity.

    Returns:
      Candidate rows sorted by ``relation_type`` then coordinates so that a re-run
      reproduces byte-identical output.
    """
    candidate_ids = _IdAllocator("cm_", 7)
    rows: List[Dict[str, str]] = []

    def emit(
        relation_type: str,
        a: ChgisRecord,
        b: ChgisRecord,
        evidence: str,
        confidence: str,
        status: str,
        distance: Optional[float] = None,
    ) -> None:
        """Append one candidate row built from two CHGIS records."""
        lon_a, lat_a = _record_lonlat(a)
        lon_b, lat_b = _record_lonlat(b)
        rows.append(
            {
                "candidate_id": "",  # assigned after the deterministic sort
                "relation_type": relation_type,
                "place_id_a": place_of_record[(a.source_dataset, a.record_index)],
                "source_record_id_a": source_record_ids[(a.source_dataset, a.record_index)],
                "name_a": a.name_ch or a.name_py,
                "lon_a": lon_a,
                "lat_a": lat_a,
                "place_id_b": place_of_record[(b.source_dataset, b.record_index)],
                "source_record_id_b": source_record_ids[(b.source_dataset, b.record_index)],
                "name_b": b.name_ch or b.name_py,
                "lon_b": lon_b,
                "lat_b": lat_b,
                "distance_m": "" if distance is None else f"{distance:.1f}",
                "same_name": "true" if (a.name_ch and a.name_ch == b.name_ch) else "false",
                "evidence": evidence,
                "confidence": confidence,
                "status": status,
                "reviewer": "",
                "reviewed_at": "",
            }
        )

    # ---- (1) per-SYS_ID relations -------------------------------------
    by_sysid: Dict[Tuple[str, str], List[ChgisRecord]] = defaultdict(list)
    for record in chgis_records:
        by_sysid[(record.source_dataset, record.sys_id_text)].append(record)

    for key in sorted(by_sysid):
        members = sorted(by_sysid[key], key=lambda r: r.record_index)
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                same_coord = a.coord_key is not None and a.coord_key == b.coord_key
                same_years = a.year_span_key == b.year_span_key
                if same_coord and same_years:
                    emit(
                        "true_duplicate_suspected", a, b,
                        evidence=(
                            f"same SYS_ID={a.sys_id_text}; same coord={a.coord_key}; "
                            f"same year pair={a.year_span_key}; record_index "
                            f"{a.record_index} vs {b.record_index}; identical NOTE_ID, "
                            "change types and administrative type"
                        ),
                        confidence="high",
                        status="needs_manual_review",
                        distance=0.0,
                    )
                elif same_coord:
                    emit(
                        "same_entity_multi_period", a, b,
                        evidence=(
                            f"same SYS_ID={a.sys_id_text} at one coordinate over two periods: "
                            f"{a.year_span_key} vs {b.year_span_key}"
                        ),
                        confidence="high",
                        status="candidate",
                        distance=0.0,
                    )
                elif a.lon is not None and a.lat is not None and b.lon is not None and b.lat is not None:
                    distance = haversine_m(a.lon, a.lat, b.lon, b.lat)
                    emit(
                        "location_migration", a, b,
                        evidence=(
                            f"same SYS_ID={a.sys_id_text} at two different coordinates; "
                            f"periods {a.year_span_key} vs {b.year_span_key}; "
                            f"name {a.name_ch!r} vs {b.name_ch!r}"
                        ),
                        confidence="high",
                        status="candidate",
                        distance=distance,
                    )

    # ---- (2) coordinate clusters --------------------------------------
    buckets: Dict[str, List[ChgisRecord]] = defaultdict(list)
    for record in chgis_records:
        if record.coord_key is None:
            continue
        buckets[record.coord_key].append(record)

    for coord_key in sorted(buckets):
        members = sorted(buckets[coord_key], key=lambda r: (r.source_dataset, r.record_index))
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                place_a = place_of_record[(a.source_dataset, a.record_index)]
                place_b = place_of_record[(b.source_dataset, b.record_index)]
                if place_a == place_b:
                    continue  # already covered by the per-SYS_ID pass
                same_name = bool(a.name_ch) and a.name_ch == b.name_ch
                emit(
                    "same_coord_diff_entity", a, b,
                    evidence=(
                        f"exact shared coordinate {coord_key}; "
                        f"sys_id {a.sys_id_text} ({a.name_ch},{a.year_span_key},"
                        f"{a.type_py},{a.lev_rank}) vs {b.sys_id_text} ({b.name_ch},"
                        f"{b.year_span_key},{b.type_py},{b.lev_rank}); "
                        f"same_name={str(same_name).lower()}"
                    ),
                    confidence="medium",
                    status="candidate",
                    distance=0.0,
                )

    # ---- (3) homonyms near enough to be a possible mis-split ----------
    by_name: Dict[str, List[ChgisRecord]] = defaultdict(list)
    for record in chgis_records:
        if not record.name_ch or record.coord_key is None:
            continue
        by_name[record.name_ch].append(record)

    homonym_pairs: List[Tuple[float, str, ChgisRecord, ChgisRecord]] = []
    seen_pairs: set = set()
    for name in sorted(by_name):
        members = by_name[name]
        place_keys = {place_of_record[(r.source_dataset, r.record_index)] for r in members}
        if len(place_keys) < 2:
            continue
        # One representative record per (place, coordinate) keeps the pair count
        # proportional to distinct places rather than to raw rows.
        representatives: Dict[Tuple[str, str], ChgisRecord] = {}
        for record in sorted(members, key=lambda r: (r.source_dataset, r.record_index)):
            key = (place_of_record[(record.source_dataset, record.record_index)], record.coord_key or "")
            representatives.setdefault(key, record)
        items = list(representatives.items())
        for i in range(len(items)):
            key_a, a = items[i]
            for j in range(i + 1, len(items)):
                key_b, b = items[j]
                if key_a[0] == key_b[0]:
                    continue
                if a.lon is None or a.lat is None or b.lon is None or b.lat is None:
                    continue
                pair_key = tuple(sorted((key_a[0], key_b[0])))
                if pair_key in seen_pairs:
                    continue
                distance = haversine_m(a.lon, a.lat, b.lon, b.lat)
                if distance > HOMONYM_PAIR_MAX_METRES:
                    continue
                seen_pairs.add(pair_key)
                homonym_pairs.append((distance, pair_key[0] + "|" + pair_key[1], a, b))

    homonym_pairs.sort(key=lambda item: (item[0], item[1]))
    truncated = max(0, len(homonym_pairs) - HOMONYM_PAIR_LIMIT)
    for distance, _key, a, b in homonym_pairs[:HOMONYM_PAIR_LIMIT]:
        emit(
            "homonym_diff_place", a, b,
            evidence=(
                f"same NAME_CH={a.name_ch!r} at two places {distance:.0f} m apart; "
                f"sys_id {a.sys_id_text} ({a.year_span_key},{a.pres_loc}) vs "
                f"{b.sys_id_text} ({b.year_span_key},{b.pres_loc}); "
                "either a genuine namesake or one entity split across records"
            ),
            confidence="low",
            status="candidate",
            distance=distance,
        )

    # ---- (4) rule-based migration edges -------------------------------
    # Appended after the spatial rules so that a pair already reported by a
    # coordinate/SYS_ID rule keeps its own row; the migration row additionally
    # records which relation it overlaps with, instead of silently replacing it.
    if migration_edges:
        pair_index: Dict[frozenset, List[str]] = defaultdict(list)
        for row in rows:
            pair_index[frozenset((row["place_id_a"], row["place_id_b"]))].append(row["relation_type"])

        for edge in migration_edges:
            if edge.relation_type not in MIGRATION_EMITTED_RELATIONS:
                continue
            a_record, b_record = edge.record_a, edge.record_b
            place_a = place_of_record[(a_record.source_dataset, a_record.record_index)]
            place_b = place_of_record[(b_record.source_dataset, b_record.record_index)]
            overlapping = sorted(
                {
                    relation
                    for relation in pair_index.get(frozenset((place_a, place_b)), [])
                    if relation != edge.relation_type
                }
            )
            evidence = (
                f"name={edge.name_ch!r}; grouping=(NAME_CH,source_dataset); "
                f"gap={edge.gap_years}; dist={edge.distance_m:.1f}m; rule={edge.rule}; "
                f"years {a_record.year_span_key} -> {b_record.year_span_key}"
            )
            if overlapping:
                evidence += "; supersedes_relation=" + "|".join(overlapping)
            status = (
                "needs_manual_review"
                if edge.relation_type == "location_migration_candidate"
                else "candidate"
            )
            emit(
                edge.relation_type,
                a_record,
                b_record,
                evidence=evidence,
                confidence=edge.confidence,
                status=status,
                distance=edge.distance_m,
            )

    rows.sort(
        key=lambda row: (
            row["relation_type"],
            row["lon_a"],
            row["lat_a"],
            row["place_id_a"],
            row["place_id_b"],
        )
    )
    for row in rows:
        row["candidate_id"] = candidate_ids.next()

    if truncated:
        rows.append(
            {
                "candidate_id": "",
                "relation_type": "truncation_notice",
                "place_id_a": "",
                "source_record_id_a": "",
                "name_a": "",
                "lon_a": "",
                "lat_a": "",
                "place_id_b": "",
                "source_record_id_b": "",
                "name_b": "",
                "lon_b": "",
                "lat_b": "",
                "distance_m": "",
                "same_name": "",
                "evidence": (
                    f"{truncated} homonym_diff_place candidates were dropped by the "
                    f"{HOMONYM_PAIR_LIMIT}-row cap; the nearest {HOMONYM_PAIR_LIMIT} by distance "
                    "were kept"
                ),
                "confidence": "",
                "status": "truncation_notice",
                "reviewer": "",
                "reviewed_at": "",
            }
        )
    return rows
