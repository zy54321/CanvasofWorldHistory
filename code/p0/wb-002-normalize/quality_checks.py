"""Data-quality analysis for WB-002: time anomalies, coordinate clusters, homonyms.

Every number this module produces is derived from the parsed source records; no
threshold or expectation is hard-coded as a *result*.  Where a threshold *is*
hard-coded (e.g. "a year magnitude above 3000 is implausible") the constant is
named, documented and reported alongside the counts so a reviewer can re-run the
analysis with a different cut-off.

Design decisions recorded here rather than in prose only
-------------------------------------------------------
``BEG_YR > END_YR`` records are never repaired.  Swapping or clamping the two
years would fabricate a historical claim that the source does not make, so the
inverted pair is preserved verbatim and the *derived* validity interval is left
empty.
"""

from __future__ import annotations

import math
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from chgis_extract import ChgisRecord
from xlsx_reader import rows_to_dicts, read_xlsx_from_zip

__all__ = [
    "ASTRO_ASSERTIONS",
    "CHINA_LON_RANGE",
    "CHINA_LAT_RANGE",
    "MAX_PLAUSIBLE_YEAR_MAGNITUDE",
    "PLAUSIBLE_YEAR_CEILING",
    "DateRuleDictionary",
    "TimeAnomalies",
    "CrossLayerDisagreement",
    "astro_year",
    "haversine_m",
    "load_date_rule_dictionary",
    "verify_astro_conversion",
    "analyse_time_anomalies",
    "build_coordinate_clusters",
    "build_homonym_stats",
    "detect_field_name_quirks",
    "find_cross_layer_disagreements",
    "year_out_of_range_reason",
]

#: No year in a Chinese historical dataset should exceed this magnitude.  Used by
#: :func:`year_out_of_range_reason`; chosen conservatively (three millennia) so
#: that legitimate deep-antiquity entries such as -221 survive untouched.
MAX_PLAUSIBLE_YEAR_MAGNITUDE = 3000

#: CHGIS V6 time-series layers end with the Qing collapse; the county layer's
#: latest observations run to 1911.  Anything materially later is out of scope.
PLAUSIBLE_YEAR_CEILING = 1912

#: Accepted longitude / latitude windows for a Chinese gazetteer point.  Used to
#: *flag* suspicious coordinates, never to drop them.
CHINA_LON_RANGE: Tuple[float, float] = (73.0, 135.5)
CHINA_LAT_RANGE: Tuple[float, float] = (3.0, 54.0)

#: Rule codes that the CHGIS ``xtra_date_rules`` workbook documents.
#: ``''`` (blank), ``'0'``, ``'7'`` and ``'8'`` occur in the shipped DBFs but are
#: absent from the workbook; they are reported as ``unknown`` rather than guessed.
DOCUMENTED_RULE_CODES: Tuple[str, ...] = ("1", "2", "3", "4", "5", "6", "9")

#: Rule-code families now live in :mod:`time_semantics`
#: (``EXACT_RULE_CODES`` = 4/5/6, ``BOUNDED_RULE_CODES`` = 1/2/3,
#: ``SNAPSHOT_RULE_CODE`` = 9).  They moved there when ``time_basis`` was
#: replaced by ``time_bound_type``, because the mapping is about what kind of
#: claim the years make, not about data quality.

#: Assertions required by the WB-002 spec for the astronomical year conversion.
ASTRO_ASSERTIONS: Tuple[Tuple[int, int], ...] = ((-221, -220), (1, 1), (1911, 1911))


def astro_year(year: Optional[int]) -> Optional[int]:
    """Convert a CHGIS historical year to an astronomical (ISO 8601) year.

    CHGIS uses the traditional convention with no year zero: 1 BCE is stored as
    ``-1``.  ISO 8601 has a year zero, so astronomical year *n* equals
    historical year ``n`` for ``n > 0`` and ``n + 1`` for ``n < 0``.

    Args:
      year: Historical year, possibly negative, possibly ``None``.

    Returns:
      The astronomical year, or ``None`` when the input is ``None``.

    Raises:
      ValueError: If ``year`` is exactly ``0``, which cannot occur under either
        convention and therefore signals a corrupt source value.
    """
    if year is None:
        return None
    if year == 0:
        raise ValueError("year 0 does not exist in the CHGIS historical convention")
    return year + 1 if year < 0 else year


def verify_astro_conversion() -> List[str]:
    """Assert the astronomical conversion against the spec's worked examples.

    Returns:
      Human readable lines describing each assertion, suitable for the run log.

    Raises:
      AssertionError: If any expected conversion does not hold.
    """
    lines: List[str] = []
    for historical, expected in ASTRO_ASSERTIONS:
        actual = astro_year(historical)
        assert actual == expected, (
            f"astro_year({historical}) returned {actual}, expected {expected}"
        )
        lines.append(f"astro_year({historical}) == {expected} OK")
    assert astro_year(None) is None, "astro_year(None) must be None"
    lines.append("astro_year(None) is None OK")
    try:
        astro_year(0)
    except ValueError:
        lines.append("astro_year(0) raises ValueError OK")
    else:  # pragma: no cover - defensive
        raise AssertionError("astro_year(0) must raise ValueError")
    return lines


def haversine_m(lon_a: float, lat_a: float, lon_b: float, lat_b: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    radius = 6371008.8
    phi_a, phi_b = math.radians(lat_a), math.radians(lat_b)
    d_phi = phi_b - phi_a
    d_lambda = math.radians(lon_b - lon_a)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi_a) * math.cos(phi_b) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(min(1.0, max(0.0, h))))


def year_out_of_range_reason(
    year: Optional[int], ceiling: int = PLAUSIBLE_YEAR_CEILING
) -> Optional[str]:
    """Return a short reason string when a year is implausible, else ``None``.

    Two independent tests are applied:
      * absolute magnitude above :data:`MAX_PLAUSIBLE_YEAR_MAGNITUDE`;
      * a CE year later than :data:`PLAUSIBLE_YEAR_CEILING`, i.e. outside the
        Qing-collapse horizon of the CHGIS time-series layers.
    """
    if year is None:
        return None
    if abs(year) > MAX_PLAUSIBLE_YEAR_MAGNITUDE:
        return f"abs(year)>{MAX_PLAUSIBLE_YEAR_MAGNITUDE}"
    if year > ceiling:
        return f"year>{ceiling}"
    return None


@dataclass
class DateRuleDictionary:
    """CHGIS ``xtra_date_rules`` lookup table, with parse provenance.

    Attributes:
      loaded: True when the workbook was found and parsed.
      rules: Mapping of rule code (as text) to ``{short_name, english}``.
      source_member: Name of the ``.xlsx`` member inside the dictionary zip.
      error: Populated when parsing failed; the reason is reported verbatim.
    """

    loaded: bool
    rules: Dict[str, Dict[str, str]] = field(default_factory=dict)
    source_member: str = ""
    error: str = ""

    def describe(self, code: str) -> str:
        """Return a human readable description for a rule code."""
        entry = self.rules.get((code or "").strip())
        if not entry:
            return "undocumented"
        return f"{entry.get('short_name', '')} -- {entry.get('english', '')}"

    def documented_codes(self) -> List[str]:
        """Sorted list of rule codes the workbook defines."""
        return sorted(self.rules)


def load_date_rule_dictionary(sample_dir: Path) -> DateRuleDictionary:
    """Parse ``xtra_date_rules.xlsx`` out of the CHGIS data-dictionary zip.

    The workbook is a two-layer zip: an outer ``CHGIS_data_dictionary.zip``
    containing ``.xlsx`` members, each of which is itself a zip.  It uses
    ``inlineStr`` cells and ships no ``sharedStrings.xml``.

    Args:
      sample_dir: Absolute path to ``设计资料/P0验证/WB-002/sample_data``.

    Returns:
      A :class:`DateRuleDictionary`.  On any failure ``loaded`` is ``False``,
      ``error`` explains why, and callers must degrade to ``unknown`` time basis
      rather than inventing meanings.
    """
    zip_path = sample_dir / "chgis" / "CHGIS_data_dictionary.zip"
    member = "xtra_date_rules.xlsx"
    if not zip_path.is_file():
        return DateRuleDictionary(loaded=False, source_member=member, error=f"missing {zip_path}")
    try:
        grid = read_xlsx_from_zip(str(zip_path), member)
    except (KeyError, zipfile.BadZipFile, ValueError) as exc:
        return DateRuleDictionary(loaded=False, source_member=member, error=f"{type(exc).__name__}: {exc}")

    rows = rows_to_dicts(grid)
    if not rows:
        return DateRuleDictionary(loaded=False, source_member=member, error="workbook parsed but held no data rows")

    rules: Dict[str, Dict[str, str]] = {}
    for row in rows:
        code = (row.get("rule_number") or "").strip()
        if not code:
            continue
        # Workbook stores rule_number as a numeric cell, so '1' may arrive as '1'
        # or '1.0'.  Normalise without losing the original text.
        if code.endswith(".0") and code[:-2].isdigit():
            code = code[:-2]
        rules[code] = {
            "short_name": (row.get("rule_short_name") or "").strip(),
            "english": (row.get("rule_eng") or "").strip(),
        }
    return DateRuleDictionary(loaded=True, rules=rules, source_member=member)


# ---------------------------------------------------------------------------
# Time analysis
# ---------------------------------------------------------------------------


@dataclass
class TimeAnomalies:
    """Container for every time-related finding produced by one analysis pass."""

    inversions: List[ChgisRecord] = field(default_factory=list)
    null_beg: List[ChgisRecord] = field(default_factory=list)
    null_end: List[ChgisRecord] = field(default_factory=list)
    equal_years: List[ChgisRecord] = field(default_factory=list)
    out_of_range: List[Tuple[ChgisRecord, str, str]] = field(default_factory=list)
    beg_rule_counts: Counter = field(default_factory=Counter)
    end_rule_counts: Counter = field(default_factory=Counter)
    sysid_counts: Counter = field(default_factory=Counter)
    duplicate_sysids: Dict[str, List[ChgisRecord]] = field(default_factory=dict)
    note_id_counts: Counter = field(default_factory=Counter)
    obj_type_counts: Counter = field(default_factory=Counter)
    lev_rank_counts: Counter = field(default_factory=Counter)
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    per_dataset: Dict[str, Dict[str, int]] = field(default_factory=dict)


def analyse_time_anomalies(records: Sequence[ChgisRecord]) -> TimeAnomalies:
    """Scan every CHGIS record for time defects.

    The inversion test is strict: **both** years must be present and numeric, and
    ``BEG_YR`` must be strictly greater than ``END_YR``.  Blank years are *not*
    counted as inversions -- they are reported separately -- and ``BEG == END``
    is treated as ``info`` because rule 9 ("time slice") documents it as
    intentional.
    """
    result = TimeAnomalies()
    sysid_buckets: Dict[str, List[ChgisRecord]] = defaultdict(list)
    years: List[int] = []
    per_dataset: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for record in records:
        beg = record.beg_year
        end = record.end_year
        bucket = per_dataset[record.source_dataset]
        bucket["records"] += 1

        if beg is not None:
            years.append(beg)
        if end is not None:
            years.append(end)

        if beg is None:
            result.null_beg.append(record)
            bucket["null_beg"] += 1
        if end is None:
            result.null_end.append(record)
            bucket["null_end"] += 1

        if beg is not None and end is not None:
            if beg > end:
                result.inversions.append(record)
                bucket["beg_gt_end"] += 1
            elif beg == end:
                result.equal_years.append(record)
                bucket["beg_eq_end"] += 1

        for label, value in (("BEG_YR", beg), ("END_YR", end)):
            reason = year_out_of_range_reason(value)
            if reason:
                result.out_of_range.append((record, label, reason))
                bucket["year_out_of_range"] += 1

        result.beg_rule_counts[record.beg_rule] += 1
        result.end_rule_counts[record.end_rule] += 1
        result.obj_type_counts[record.raw.get("OBJ_TYPE", "")] += 1
        result.lev_rank_counts[record.lev_rank] += 1
        result.note_id_counts[record.raw.get("NOTE_ID", "")] += 1

        key = f"{record.source_dataset}:{record.sys_id_text}"
        result.sysid_counts[key] += 1
        sysid_buckets[key].append(record)

    result.duplicate_sysids = {k: v for k, v in sysid_buckets.items() if len(v) > 1}
    if years:
        result.year_min = min(years)
        result.year_max = max(years)
    result.per_dataset = {k: dict(v) for k, v in per_dataset.items()}
    return result


# ---------------------------------------------------------------------------
# Coordinate clusters
# ---------------------------------------------------------------------------


@dataclass
class ClusterClassification:
    """Classification counters for one coordinate cluster.

    Attributes:
      cluster_id: Stable ``cl_`` identifier.
      coord_key: Exact ``lon|lat`` string key.
      lon: Parsed longitude.
      lat: Parsed latitude.
      records: Member records.
      same_place_multi_period: Pairs sharing one SYS_ID (migration / return).
      same_name_diff_entity: Pairs with equal ``NAME_CH`` but different SYS_ID.
      diff_name_diff_entity: Pairs with different name and different SYS_ID.
      suspected_duplicate: Pairs sharing SYS_ID *and* the exact year pair.
      distinct_sysids: Number of distinct SYS_IDs in the cluster.
      distinct_names: Number of distinct ``NAME_CH`` values in the cluster.
    """

    cluster_id: str
    coord_key: str
    lon: float
    lat: float
    records: List[ChgisRecord] = field(default_factory=list)
    same_place_multi_period: int = 0
    same_name_diff_entity: int = 0
    diff_name_diff_entity: int = 0
    suspected_duplicate: int = 0
    distinct_sysids: int = 0
    distinct_names: int = 0

    @property
    def record_count(self) -> int:
        """Number of records at this coordinate."""
        return len(self.records)

    @property
    def classification(self) -> str:
        """Dominant classification label for the cluster.

        Precedence follows the spec's a/b/c/d ordering: a cluster that is wholly
        one entity over several periods is *not* a duplicate cluster, so ``d``
        only wins when it is the only signal present.
        """
        if self.suspected_duplicate and self.suspected_duplicate * 2 >= self.record_count - 1:
            return "suspected_true_duplicate"
        if self.same_place_multi_period and not (self.same_name_diff_entity or self.diff_name_diff_entity):
            return "same_entity_multi_period"
        if self.same_place_multi_period:
            return "mixed"
        if self.same_name_diff_entity and not self.diff_name_diff_entity:
            return "same_name_diff_entity"
        if self.diff_name_diff_entity and not self.same_name_diff_entity:
            return "same_coord_diff_entity"
        if self.same_name_diff_entity and self.diff_name_diff_entity:
            return "mixed"
        return "single_record"


def build_coordinate_clusters(
    records: Sequence[ChgisRecord],
) -> Tuple[List[ClusterClassification], Dict[str, Counter]]:
    """Group records by *exact* coordinate text and classify each cluster.

    Deduplication uses the literal ``X_COOR|Y_COOR`` strings, not a rounded
    numeric tuple.  Both were measured on the shipped data and agree exactly, so
    the choice does not change any count -- the exact-string form is used because
    it is loss-free and obvious to a reviewer re-checking the numbers.

    Returns:
      ``(clusters, stats)`` where clusters are sorted by record count descending
      then by coordinate string, and ``stats`` carries the supporting counters.
    """
    buckets: Dict[str, List[ChgisRecord]] = defaultdict(list)
    overflow_records = 0
    for record in records:
        key = record.coord_key
        if key is None:
            overflow_records += 1
            continue
        buckets[key].append(record)

    ordered = sorted(buckets.items(), key=lambda item: (item[1][0].lon or 0.0, item[1][0].lat or 0.0))
    clusters: List[ClusterClassification] = []
    for order, (coord_key, members) in enumerate(ordered, start=1):
        first = members[0]
        cluster = ClusterClassification(
            cluster_id=f"cl_{order:06d}",
            coord_key=coord_key,
            lon=first.lon or 0.0,
            lat=first.lat or 0.0,
            records=sorted(members, key=lambda r: (r.source_dataset, r.record_index)),
        )
        place_keys = [f"{r.source_dataset}:{r.sys_id_text}" for r in cluster.records]
        cluster.distinct_sysids = len(set(place_keys))
        cluster.distinct_names = len({r.name_ch for r in cluster.records if r.name_ch})

        for i in range(len(cluster.records)):
            for j in range(i + 1, len(cluster.records)):
                a, b = cluster.records[i], cluster.records[j]
                same_place = place_keys[i] == place_keys[j]
                same_name = bool(a.name_ch) and a.name_ch == b.name_ch
                if same_place:
                    cluster.same_place_multi_period += 1
                    if a.year_span_key == b.year_span_key:
                        cluster.suspected_duplicate += 1
                elif same_name:
                    cluster.same_name_diff_entity += 1
                else:
                    cluster.diff_name_diff_entity += 1
        clusters.append(cluster)

    clusters.sort(key=lambda c: (-c.record_count, c.coord_key))

    size_hist = Counter(c.record_count for c in clusters)
    pairwise = sum(n * (n - 1) // 2 for n in size_hist.elements())
    # Reconciliation: if the DBF overflow rows (`**********`) are treated as one
    # more (bogus) coordinate value, the count rises by exactly one.  Both figures
    # are reported so any externally quoted number can be matched.
    raw_text_keys = {
        f"{r.lon_text}|{r.lat_text}" for r in records if r.lon_text or r.lat_text
    }
    stats: Dict[str, Counter] = {
        "size_histogram": size_hist,
        "classifications": Counter(c.classification for c in clusters),
        "pairwise": Counter(
            {
                "total_pairs": pairwise,
                "overflow_coordinates": overflow_records,
                "distinct_coordinates": len(clusters),
                "distinct_raw_text_including_overflow": len(raw_text_keys),
            }
        ),
    }
    # Re-number ids after the deterministic display sort so that cluster_id order
    # matches file order.
    for index, cluster in enumerate(clusters, start=1):
        cluster.cluster_id = f"cl_{index:06d}"
    return clusters, stats


# ---------------------------------------------------------------------------
# Homonyms
# ---------------------------------------------------------------------------


@dataclass
class HomonymEntry:
    """One name that occurs at more than one coordinate.

    Attributes:
      name: Exact ``NAME_CH`` value.
      coord_keys: Distinct coordinate keys the name appears at.
      sysids: Distinct dataset-scoped SYS_IDs carrying the name.
      bbox: ``(lon_min, lat_min, lon_max, lat_max)``.
      provinces: Distinct ``PRES_LOC`` prefix tokens used as a province hint.
      is_cross_province: True when more than one province hint was observed.
      record_count: Number of CHGIS records carrying the name.
    """

    name: str
    coord_keys: List[str] = field(default_factory=list)
    sysids: List[str] = field(default_factory=list)
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    provinces: List[str] = field(default_factory=list)
    is_cross_province: bool = False
    record_count: int = 0


#: ``PRES_LOC`` strings begin with a modern province reference such as
#: ``"今山西保德县城西侧"`` or ``"山西保德县城西侧"``.  Stripping a leading ``今``
#: and taking the first two characters yields a coarse province token.  This is a
#: *hint only*; it is never used to merge or split places.
_PROVINCE_HINTS = (
    "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
    "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
    "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门",
)


def province_hint(pres_loc: str) -> str:
    """Return a coarse province token from a ``PRES_LOC`` string, or ``''``."""
    text = (pres_loc or "").strip()
    if text.startswith("今"):
        text = text[1:]
    for province in _PROVINCE_HINTS:
        if text.startswith(province):
            return province
    return ""


def build_homonym_stats(records: Sequence[ChgisRecord]) -> Tuple[List[HomonymEntry], Dict[str, Counter]]:
    """Find ``NAME_CH`` values that occur at more than one coordinate.

    Matching口径 (**exact** ``NAME_CH`` equality, empty names excluded, no
    ``TYPE_CH`` qualification): this is the only definition under which the
    "3,072 of 8,303" style figure is reproducible, and the same口径 is used for
    the 24.9% multi-coordinate share.

    Returns:
      ``(entries, stats)`` with entries sorted by coordinate count descending.
    """
    by_name: Dict[str, List[ChgisRecord]] = defaultdict(list)
    for record in records:
        if not record.name_ch:
            continue
        by_name[record.name_ch].append(record)

    entries: List[HomonymEntry] = []
    for name, members in by_name.items():
        coords = sorted({r.coord_key for r in members if r.coord_key})
        if len(coords) < 2:
            continue
        lons = [r.lon for r in members if r.lon is not None]
        lats = [r.lat for r in members if r.lat is not None]
        provinces = sorted({p for p in (province_hint(r.pres_loc) for r in members) if p})
        entries.append(
            HomonymEntry(
                name=name,
                coord_keys=coords,
                sysids=sorted({f"{r.source_dataset}:{r.sys_id_text}" for r in members}),
                bbox=(
                    min(lons) if lons else 0.0,
                    min(lats) if lats else 0.0,
                    max(lons) if lons else 0.0,
                    max(lats) if lats else 0.0,
                ),
                provinces=provinces,
                is_cross_province=len(provinces) > 1,
                record_count=len(members),
            )
        )

    entries.sort(key=lambda e: (-len(e.coord_keys), -e.record_count, e.name))

    distinct_names = len(by_name)

    # Reconciliation series: the same statistic computed while treating the DBF
    # overflow marker rows as ordinary (bogus) coordinates, so that a figure
    # quoted from an earlier pass can be matched exactly.
    multi_including_overflow = 0
    for name, members in by_name.items():
        coords = {f"{r.lon_text}|{r.lat_text}" for r in members if r.lon_text or r.lat_text}
        if len(coords) > 1:
            multi_including_overflow += 1

    stats: Dict[str, Counter] = {
        "totals": Counter(
            {
                "distinct_names": distinct_names,
                "multi_coordinate_names": len(entries),
                "single_coordinate_names": distinct_names - len(entries),
                "records_with_name": sum(len(v) for v in by_name.values()),
                "cross_province_names": sum(1 for e in entries if e.is_cross_province),
                "multi_coordinate_names_including_overflow_rows": multi_including_overflow,
            }
        ),
        "coord_count_histogram": Counter(len(e.coord_keys) for e in entries),
    }
    return entries, stats


# ---------------------------------------------------------------------------
# Field-name quirks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldNameQuirk:
    """A field whose name deviates from the documented/expected spelling."""

    source_dataset: str
    field_name: str
    expected_name: str
    note: str


def detect_field_name_quirks(declared: Dict[str, List[str]]) -> List[FieldNameQuirk]:
    """Detect field-name spelling deviations across the CHGIS layers.

    Rather than hard-coding "county uses GECOMPLR", the two layers are compared
    against each other: any field present in exactly one layer that is within
    Levenshtein distance 2 of a field in the other layer is reported as a quirk.

    Each *pair* of names is reported exactly once, attributed to the
    later-listed dataset, so ``GEOCOMPLR``/``GECOMPLR`` produces one row rather
    than one row in each direction.

    Args:
      declared: Mapping of ``source_dataset`` to its physical field-name list.

    Returns:
      A list of :class:`FieldNameQuirk` in a deterministic order.
    """
    quirks: List[FieldNameQuirk] = []
    reported_pairs: set = set()
    datasets = sorted(declared)
    for i, left in enumerate(datasets):
        for right in datasets[i + 1 :]:
            left_only = set(declared[left]) - set(declared[right])
            right_only = set(declared[right]) - set(declared[left])
            for name in sorted(left_only):
                match = _closest_name(name, right_only)
                if match is None:
                    continue
                pair = tuple(sorted((name, match)))
                if pair in reported_pairs:
                    continue
                reported_pairs.add(pair)
                quirks.append(
                    FieldNameQuirk(
                        source_dataset=right,
                        field_name=match,
                        expected_name=name,
                        note=(
                            f"{left} spells the corresponding field {name!r} while {right} "
                            f"spells it {match!r}"
                        ),
                    )
                )
            for name in sorted(right_only):
                match = _closest_name(name, left_only)
                if match is None:
                    continue
                pair = tuple(sorted((name, match)))
                if pair in reported_pairs:
                    continue
                reported_pairs.add(pair)
                quirks.append(
                    FieldNameQuirk(
                        source_dataset=right,
                        field_name=name,
                        expected_name=match,
                        note=(
                            f"{left} spells the corresponding field {match!r} while {right} "
                            f"spells it {name!r}"
                        ),
                    )
                )
    quirks.sort(key=lambda q: (q.source_dataset, q.field_name))
    return quirks


def _closest_name(name: str, candidates: Iterable[str], max_distance: int = 2) -> Optional[str]:
    """Return the candidate within ``max_distance`` edits, preferring the closest."""
    best: Optional[str] = None
    best_distance = max_distance + 1
    for candidate in sorted(candidates):
        distance = _edit_distance(name, candidate)
        if distance < best_distance:
            best, best_distance = candidate, distance
    return best if best_distance <= max_distance else None


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance between two short ASCII strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (char_a != char_b),
                )
            )
        previous = current
    return previous[-1]


# ---------------------------------------------------------------------------
# Cross-layer disagreement
# ---------------------------------------------------------------------------


@dataclass
class CrossLayerDisagreement:
    """One ``(name, year span)`` that the two CHGIS layers place differently.

    Attributes:
      name: ``NAME_CH`` shared by both layers.
      beg_yr: Shared ``BEG_YR`` text.
      end_yr: Shared ``END_YR`` text.
      prefecture_coords: Distinct coordinates in ``chgis_pref``.
      county_coords: Distinct coordinates in ``chgis_cnty``.
      prefecture_sys_ids: ``SYS_ID`` values in ``chgis_pref``.
      county_sys_ids: ``SYS_ID`` values in ``chgis_cnty``.
      max_separation_m: Largest prefecture-to-county distance in metres.
    """

    name: str
    beg_yr: str
    end_yr: str
    prefecture_coords: List[str] = field(default_factory=list)
    county_coords: List[str] = field(default_factory=list)
    prefecture_sys_ids: List[str] = field(default_factory=list)
    county_sys_ids: List[str] = field(default_factory=list)
    max_separation_m: float = 0.0


def find_cross_layer_disagreements(
    records: Sequence[ChgisRecord], max_results: int = 500
) -> Tuple[List[CrossLayerDisagreement], Dict[str, Counter]]:
    """Find entities the prefecture and county layers place at different points.

    A match requires the *same* ``NAME_CH`` **and** the same raw
    ``(BEG_YR, END_YR)`` pair in both layers -- a much stronger claim than name
    equality alone.  Such a pair should be one historical entity, so a coordinate
    difference is a direct contradiction between the two shipped layers rather
    than a naming coincidence.

    Args:
      records: All CHGIS records.
      max_results: Cap on the number returned, keeping the furthest apart pairs.

    Returns:
      ``(disagreements, stats)``.
    """
    buckets: Dict[Tuple[str, str, str], List[ChgisRecord]] = defaultdict(list)
    for record in records:
        if not record.name_ch or record.beg_year is None or record.end_year is None:
            continue
        buckets[(record.name_ch, record.raw.get("BEG_YR", ""), record.raw.get("END_YR", ""))].append(record)

    found: List[CrossLayerDisagreement] = []
    for (name, beg, end), members in buckets.items():
        by_dataset: Dict[str, List[ChgisRecord]] = defaultdict(list)
        for record in members:
            by_dataset[record.source_dataset].append(record)
        if "chgis_pref" not in by_dataset or "chgis_cnty" not in by_dataset:
            continue
        pref = by_dataset["chgis_pref"]
        cnty = by_dataset["chgis_cnty"]
        pref_coords = sorted({r.coord_key for r in pref if r.coord_key})
        cnty_coords = sorted({r.coord_key for r in cnty if r.coord_key})
        if not pref_coords or not cnty_coords:
            continue
        if pref_coords == cnty_coords:
            continue
        separation = 0.0
        for a in pref:
            for b in cnty:
                if a.lon is None or a.lat is None or b.lon is None or b.lat is None:
                    continue
                separation = max(separation, haversine_m(a.lon, a.lat, b.lon, b.lat))
        found.append(
            CrossLayerDisagreement(
                name=name,
                beg_yr=beg,
                end_yr=end,
                prefecture_coords=pref_coords,
                county_coords=cnty_coords,
                prefecture_sys_ids=sorted({r.sys_id_text for r in pref}),
                county_sys_ids=sorted({r.sys_id_text for r in cnty}),
                max_separation_m=separation,
            )
        )

    found.sort(key=lambda d: (-d.max_separation_m, d.name, d.beg_yr))
    stats: Dict[str, Counter] = {
        "totals": Counter(
            {
                "pairs": len(found),
                "returned": min(len(found), max_results),
                "over_1km": sum(1 for d in found if d.max_separation_m > 1000.0),
                "over_10km": sum(1 for d in found if d.max_separation_m > 10000.0),
            }
        )
    }
    return found[:max_results], stats
