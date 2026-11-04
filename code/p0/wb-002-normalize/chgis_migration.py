"""Rule-based migration (迁治) chain candidates for the CHGIS V6 point layers.

Why this module exists
----------------------
The WB-002 staging pipeline originally modelled one distinct ``SYS_ID`` as one
historical place.  That model is contradicted by the CHGIS data dictionary, which
describes ``SYS_ID`` as a "unique ID for the spatial object [can only occur once
in the gisinfo_table]" -- a *spatial object* key, not a persistent administrative
entity.  The data agrees: 15,746 of 15,748 ``SYS_ID`` values occur exactly once,
so "the same SYS_ID appears at two coordinates" can never be observed and the
``location_migration`` relation came out empty.

Migration is real, though; it is simply recorded as a *succession of separate
points*.  This module therefore infers entity identity from a weaker but
available signal and emits **candidates only** -- nothing is merged, nothing is
renamed, and no year is rewritten.

Identity model used here
------------------------
Group key: ``(NAME_CH, source_dataset)``.

Rationale: within one administrative layer, consecutive year spans that carry the
same vernacular name are most plausibly the same entity continuing.  Layers are
never mixed, because a change of administrative level is a different kind of
event and mixing the layers produces false matches -- the prefecture and county
layers place ``中山国`` 55 km apart across the *same* year spans, which is a data
disagreement, not a migration.

Records are ordered by ``BEG_YR``; records with a blank ``BEG_YR`` are held out of
the pairing (they cannot be placed on a timeline) and counted separately.

Adjacency decision order
------------------------
For each adjacent pair ``A -> B`` compute::

    gap  = B.BEG_YR - A.END_YR      # negative means the spans overlap
    dist = haversine(A, B)          # metres

and stop at the first rule that matches:

===================================  ==============================  ==========
rule                                 relation_type                   confidence
===================================  ==============================  ==========
``dist > 300 km``                    ``homonym_diff_place``          high
``gap < -2``                         ``period_overlap``              (no row)
``dist == 0`` and ``gap <= 2``       ``same_entity_same_seat``       high
``dist == 0`` and ``gap <= 60``      ``same_entity_same_seat``       medium
``0 < dist <= 300 km`` and ``gap<=2`` ``location_migration_candidate`` high
``0 < dist <= 300 km`` and ``gap<=10`` ``location_migration_candidate`` medium
``0 < dist <= 300 km`` and ``gap<=60`` ``location_migration_candidate`` low
otherwise (``gap > 60``)             ``temporal_gap_too_large``      (no row)
===================================  ==============================  ==========

The ``dist > 300 km`` test is hoisted above the gap tests.  This is
*order-preserving* with respect to the specification: every distance band below
it requires ``dist <= 300 km``, so no pair changes classification.  Hoisting only
decides the tie between "far apart" and "spans overlap", and distance is the
stronger, year-independent signal: the same name 1,700 km away is a namesake no
matter what the years say.

``gap < -2`` is held out of migration detection deliberately.  Overlapping spans
mean one of the two year pairs is unreliable -- the same class of defect as the
28 ``BEG_YR > END_YR`` records -- so inferring a move across them would launder
bad dates into a confident claim.  A tolerance of 2 years absorbs ordinary
boundary conventions (inclusive end years, one-year compilation slop).

All thresholds are module constants so a reviewer can re-run at different cuts.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from chgis_extract import ChgisRecord
from quality_checks import haversine_m

__all__ = [
    "MIGRATION_MAX_LEG_M",
    "GAP_SAME_SEAT_HIGH",
    "GAP_SAME_SEAT_MAX",
    "GAP_MIGRATION_HIGH",
    "GAP_MIGRATION_MEDIUM",
    "GAP_MIGRATION_MAX",
    "GAP_OVERLAP_TOLERANCE",
    "REL_SAME_SEAT",
    "REL_MIGRATION",
    "REL_HOMONYM",
    "REL_OVERLAP",
    "REL_GAP_TOO_LARGE",
    "REL_NO_COORD",
    "EMITTED_RELATIONS",
    "CHAIN_RELATIONS",
    "CONFIDENCE_ORDER",
    "MigrationEdge",
    "MigrationChain",
    "MigrationAnalysis",
    "ReviewQueueEntry",
    "REVIEW_QUEUE_COLUMNS",
    "REVIEW_P1_DISTANCE_M",
    "REVIEW_P2_DISTANCE_M",
    "review_priority",
    "build_review_queue",
    "analyse_migrations",
    "verify_xinxing_jun",
    "verify_zhongshan_guo",
]

#: A leg longer than this is treated as two different places that happen to share
#: a name, not as a move.  300 km is deliberately generous: it comfortably spans
#: real prefecture relocations (the 新兴郡 chain's longest leg is 31.6 km) while
#: still rejecting the 1,746 km 山西-广东 namesake.
MIGRATION_MAX_LEG_M = 300_000.0

#: Year-gap tolerances.  ``HIGH`` means the spans touch or nearly touch.
GAP_SAME_SEAT_HIGH = 2
GAP_SAME_SEAT_MAX = 60
GAP_MIGRATION_HIGH = 2
GAP_MIGRATION_MEDIUM = 10
GAP_MIGRATION_MAX = 60

#: Gaps at or below this (i.e. overlaps of more than two years) are treated as
#: unreliable year evidence rather than as evidence of coexistence.
GAP_OVERLAP_TOLERANCE = -2

REL_SAME_SEAT = "same_entity_same_seat"
REL_MIGRATION = "location_migration_candidate"
REL_HOMONYM = "homonym_diff_place"
REL_OVERLAP = "period_overlap"
REL_GAP_TOO_LARGE = "temporal_gap_too_large"
REL_NO_COORD = "coordinate_missing"

#: Relations that produce a row in ``candidate_matches.csv``.
EMITTED_RELATIONS: Tuple[str, ...] = (REL_SAME_SEAT, REL_MIGRATION, REL_HOMONYM)

#: Relations that may form part of a migration chain.
CHAIN_RELATIONS: Tuple[str, ...] = (REL_SAME_SEAT, REL_MIGRATION)

#: Worst-to-best ordering used to derive ``min_confidence`` for a chain.
CONFIDENCE_ORDER: Tuple[str, ...] = ("low", "medium", "high")


@dataclass(frozen=True)
class MigrationEdge:
    """One adjacent-pair verdict inside a ``(NAME_CH, source_dataset)`` group.

    Attributes:
      name_ch: Shared vernacular name of the group.
      source_dataset: Layer the pair belongs to.
      record_a: Earlier record (smaller ``BEG_YR``).
      record_b: Later record.
      gap_years: ``B.BEG_YR - A.END_YR``; negative when the spans overlap.
      distance_m: Great-circle distance between the two seats, in metres.
      relation_type: One of the ``REL_*`` constants.
      confidence: ``high`` / ``medium`` / ``low``, empty when no row is emitted.
      rule: Name of the threshold clause that fired, e.g. ``migration_gap<=10``.
    """

    name_ch: str
    source_dataset: str
    record_a: ChgisRecord
    record_b: ChgisRecord
    gap_years: int
    distance_m: float
    relation_type: str
    confidence: str
    rule: str


@dataclass
class MigrationChain:
    """A run of consecutive same-seat / migration edges inside one group.

    Attributes:
      chain_id: Stable ``ch_`` identifier assigned after the deterministic sort.
      name_ch: Group name.
      source_dataset: Group layer.
      records: Member records in chronological order (``edges`` + 1 items).
      edges: The edges that built the chain.
      seat_count: Number of distinct analysed coordinates.
      first_beg_yr: ``BEG_YR`` of the first record.
      last_end_yr: ``END_YR`` of the last record.
      max_leg_distance_m: Longest single leg.
      total_path_distance_m: Sum of all legs.
      min_confidence: Worst confidence among the chain's edges.
      is_migration_chain: True when ``seat_count >= 2`` and at least one
        ``location_migration_candidate`` edge is present.
    """

    chain_id: str
    name_ch: str
    source_dataset: str
    records: List[ChgisRecord] = field(default_factory=list)
    edges: List[MigrationEdge] = field(default_factory=list)
    seat_count: int = 0
    first_beg_yr: Optional[int] = None
    last_end_yr: Optional[int] = None
    max_leg_distance_m: float = 0.0
    total_path_distance_m: float = 0.0
    min_confidence: str = ""
    is_migration_chain: bool = False

    @property
    def record_count(self) -> int:
        """Number of records in the chain."""
        return len(self.records)

    @property
    def total_span_years(self) -> Optional[int]:
        """Years from the first ``BEG_YR`` to the last ``END_YR``."""
        if self.first_beg_yr is None or self.last_end_yr is None:
            return None
        return self.last_end_yr - self.first_beg_yr

    @property
    def coord_keys(self) -> List[str]:
        """Distinct coordinate keys in order of first appearance."""
        seen: List[str] = []
        for record in self.records:
            key = record.coord_key
            if key is None or key in seen:
                continue
            seen.append(key)
        return seen

    @property
    def sys_ids(self) -> List[str]:
        """``SYS_ID`` values of the member records, in order."""
        return [record.sys_id_text for record in self.records]


@dataclass
class MigrationAnalysis:
    """Everything :func:`analyse_migrations` produces."""

    edges: List[MigrationEdge]
    chains: List[MigrationChain]
    migration_chains: List[MigrationChain]
    stats: Dict[str, object]


#: A migration leg longer than this is P1 when its temporal confidence is high:
#: the year gap says the two seats were used back to back, but a move of this
#: length is where a false positive would hide.
REVIEW_P1_DISTANCE_M = 100_000.0

#: A leg longer than this is worth a look even at high confidence, and a leg at
#: medium confidence above :data:`REVIEW_P1_DISTANCE_M` is equally worth a look.
REVIEW_P2_DISTANCE_M = 50_000.0

#: Column order of ``issues/migration_review_queue.csv``.
REVIEW_QUEUE_COLUMNS: Tuple[str, ...] = (
    "priority", "name_ch", "source_dataset", "leg_distance_m", "gap_years",
    "confidence", "from_coord", "to_coord", "from_pres_loc", "to_pres_loc",
    "review_hint",
)


@dataclass(frozen=True)
class ReviewQueueEntry:
    """One migration leg that a human must judge.

    ``confidence`` is copied verbatim from :class:`MigrationEdge` and keeps its
    purely temporal meaning.  ``priority`` is a *review ordering*, derived from
    distance and confidence, and is the only field here that encodes a judgement
    about plausibility.
    """

    priority: str
    name_ch: str
    source_dataset: str
    leg_distance_m: float
    gap_years: int
    confidence: str
    from_coord: str
    to_coord: str
    from_pres_loc: str
    to_pres_loc: str
    review_hint: str


def review_priority(distance_m: float, confidence: str) -> str:
    """Derive the review priority for one leg.

    The mapping is a *review ordering only*:

    * ``P1`` -- distance > 100 km at ``high`` confidence.  The year gap says the
      seats were consecutive, so the only remaining doubt is the distance.
    * ``P2`` -- 50-100 km at ``high`` confidence, **or** > 100 km at ``medium``.
    * ``P3`` -- everything else.

    Args:
      distance_m: Leg length in metres.
      confidence: ``high`` / ``medium`` / ``low``.

    Returns:
      ``'P1'``, ``'P2'`` or ``'P3'``.
    """
    if distance_m > REVIEW_P1_DISTANCE_M and confidence == "high":
        return "P1"
    if distance_m > REVIEW_P1_DISTANCE_M and confidence == "medium":
        return "P2"
    if distance_m > REVIEW_P2_DISTANCE_M and confidence == "high":
        return "P2"
    return "P3"


_REVIEW_HINTS: Dict[str, str] = {
    "P1": (
        "long leg at high temporal confidence: the years say the two seats were used "
        "back to back, so distance is the only remaining doubt. Check whether the two "
        "coordinates are really one entity's successive seats or two same-named places."
    ),
    "P2": (
        "long leg with weaker temporal support: either the distance is large or the "
        "year gap is loose. Confirm both before treating this as a move."
    ),
    "P3": (
        "short leg and/or loose years: plausible as a move but unverified. Review only "
        "if the entity matters to the project."
    ),
}


def build_review_queue(analysis: MigrationAnalysis) -> List[ReviewQueueEntry]:
    """Build the human review queue from the emitted migration legs.

    Only ``location_migration_candidate`` edges enter the queue.  Rejected legs
    (``homonym_diff_place``, ``period_overlap``, ``temporal_gap_too_large``,
    ``coordinate_missing``) are already excluded by the rules and stay in
    ``candidate_matches.csv``; the queue exists for the legs the pipeline *did*
    accept, so a reviewer's attention is not diluted.

    Sort order is ``priority`` ascending (``P1`` -> ``P2`` -> ``P3``), then
    ``leg_distance_m`` descending, then ``gap_years`` ascending.  Priority comes
    first **because the queue exists to be worked through by hand**: a
    distance-first order buries the 87 P1 rows behind 299 km legs that are only
    ``low`` confidence, which defeats the file's purpose.  The distance-descending
    view is still obtainable by sorting the ``leg_distance_m`` column.

    Args:
      analysis: Output of :func:`analyse_migrations`.

    Returns:
      Entries in queue order.
    """
    entries: List[ReviewQueueEntry] = []
    for edge in analysis.edges:
        if edge.relation_type != REL_MIGRATION:
            continue
        priority = review_priority(edge.distance_m, edge.confidence)
        entries.append(
            ReviewQueueEntry(
                priority=priority,
                name_ch=edge.name_ch,
                source_dataset=edge.source_dataset,
                leg_distance_m=edge.distance_m,
                gap_years=edge.gap_years,
                confidence=edge.confidence,
                from_coord=edge.record_a.coord_key or "",
                to_coord=edge.record_b.coord_key or "",
                from_pres_loc=edge.record_a.pres_loc,
                to_pres_loc=edge.record_b.pres_loc,
                review_hint=_REVIEW_HINTS[priority],
            )
        )
    # Primary key: ``priority`` ascending, so the first screen of the file is the
    # 87 legs that most need a human.  Secondary key is the *written* distance, not
    # the raw float: ``_fmt_distance`` renders one decimal, so two legs 0.06 m
    # apart would print the same number while the raw sort could still put the
    # larger gap first -- the reader then sees an apparent inversion when
    # re-sorting the CSV by column.  Sorting on ``round(distance, 1)`` keeps the
    # artifact self-consistent with the rule it claims to follow; the remaining
    # ties are broken deterministically.
    entries.sort(
        key=lambda e: (
            _PRIORITY_ORDER[e.priority],
            -_queue_distance(e.leg_distance_m),
            e.gap_years,
            e.name_ch,
            e.source_dataset,
            e.from_coord,
            e.to_coord,
        )
    )
    return entries


#: Sort rank of each priority label.  ``P1`` must come first: the queue is a
#: work list, not a distance ranking.
_PRIORITY_ORDER: Dict[str, int] = {"P1": 0, "P2": 1, "P3": 2}


def _queue_distance(value: float) -> float:
    """Round a leg distance to the precision written to the queue CSV.

    Args:
      value: Raw leg length in metres.

    Returns:
      The value rounded to one decimal, matching ``_fmt_distance``.
    """
    return round(value, 1)


def _fmt_distance(value: float) -> str:
    """Render a distance with one decimal, ASCII only."""
    return f"{value:.1f}"


def build_entity_groups(
    records: Sequence[ChgisRecord],
) -> Tuple[Dict[Tuple[str, str], List[ChgisRecord]], List[ChgisRecord]]:
    """Group records by ``(NAME_CH, source_dataset)`` and sort each group by year.

    Args:
      records: All CHGIS records.

    Returns:
      ``(groups, undatable)``.  ``groups`` maps the key to a chronologically
      sorted list (blank ``BEG_YR`` excluded); ``undatable`` holds the records
      that could not be placed on a timeline.
    """
    buckets: Dict[Tuple[str, str], List[ChgisRecord]] = defaultdict(list)
    undatable: List[ChgisRecord] = []
    for record in records:
        if not record.name_ch:
            undatable.append(record)
            continue
        if record.beg_year is None:
            undatable.append(record)
            continue
        buckets[(record.name_ch, record.source_dataset)].append(record)

    groups: Dict[Tuple[str, str], List[ChgisRecord]] = {}
    for key in sorted(buckets):
        groups[key] = sorted(
            buckets[key],
            key=lambda r: (r.beg_year if r.beg_year is not None else 0, r.record_index),
        )
    undatable.sort(key=lambda r: (r.source_dataset, r.record_index))
    return groups, undatable


def classify_pair(
    name_ch: str, source_dataset: str, a: ChgisRecord, b: ChgisRecord
) -> MigrationEdge:
    """Classify one adjacent pair with the documented rule ladder.

    Args:
      name_ch: Group name (already known equal for both records).
      source_dataset: Group layer.
      a: Earlier record.
      b: Later record.

    Returns:
      A :class:`MigrationEdge`; ``relation_type`` is one of the ``REL_*``
      constants and ``confidence`` is empty when no candidate row is emitted.
    """
    beg_a = a.beg_year or 0
    end_a = a.end_year if a.end_year is not None else beg_a
    beg_b = b.beg_year or 0
    gap = beg_b - end_a

    if not a.has_coordinate or not b.has_coordinate:
        return MigrationEdge(
            name_ch, source_dataset, a, b, gap, 0.0, REL_NO_COORD, "", "coordinate_overflow_marker"
        )

    distance = haversine_m(a.lon or 0.0, a.lat or 0.0, b.lon or 0.0, b.lat or 0.0)

    def edge(relation: str, confidence: str, rule: str) -> MigrationEdge:
        return MigrationEdge(name_ch, source_dataset, a, b, gap, distance, relation, confidence, rule)

    if distance > MIGRATION_MAX_LEG_M:
        return edge(REL_HOMONYM, "high", "dist>300km")
    if gap < GAP_OVERLAP_TOLERANCE:
        return edge(REL_OVERLAP, "", "gap<-2 (spans overlap)")
    if distance == 0.0:
        if gap <= GAP_SAME_SEAT_HIGH:
            return edge(REL_SAME_SEAT, "high", "dist==0 and gap<=2")
        if gap <= GAP_SAME_SEAT_MAX:
            return edge(REL_SAME_SEAT, "medium", "dist==0 and gap<=60")
    else:
        if gap <= GAP_MIGRATION_HIGH:
            return edge(REL_MIGRATION, "high", "0<dist<=300km and gap<=2")
        if gap <= GAP_MIGRATION_MEDIUM:
            return edge(REL_MIGRATION, "medium", "0<dist<=300km and gap<=10")
        if gap <= GAP_MIGRATION_MAX:
            return edge(REL_MIGRATION, "low", "0<dist<=300km and gap<=60")
    return edge(REL_GAP_TOO_LARGE, "", "gap>60")


def _build_chain(edges: Sequence[MigrationEdge]) -> MigrationChain:
    """Assemble a :class:`MigrationChain` from a run of consecutive edges."""
    first, last = edges[0], edges[-1]
    records: List[ChgisRecord] = [first.record_a] + [edge.record_b for edge in edges]
    chain = MigrationChain(
        chain_id="",
        name_ch=first.name_ch,
        source_dataset=first.source_dataset,
        records=records,
        edges=list(edges),
    )
    chain.first_beg_yr = first.record_a.beg_year
    chain.last_end_yr = last.record_b.end_year
    chain.seat_count = len(chain.coord_keys)
    distances = [edge.distance_m for edge in edges]
    chain.max_leg_distance_m = max(distances) if distances else 0.0
    chain.total_path_distance_m = sum(distances)
    confidences = [edge.confidence for edge in edges if edge.confidence]
    chain.min_confidence = (
        min(confidences, key=lambda c: CONFIDENCE_ORDER.index(c)) if confidences else ""
    )
    chain.is_migration_chain = chain.seat_count >= 2 and any(
        edge.relation_type == REL_MIGRATION for edge in edges
    )
    return chain


def assemble_chains(edges: Sequence[MigrationEdge]) -> List[MigrationChain]:
    """Split each group's edge sequence into maximal chainable runs.

    Non-chainable edges (``period_overlap``, ``temporal_gap_too_large``,
    ``coordinate_missing``) terminate the current run without producing a
    multi-record chain, which is what keeps an unreliable year pair from silently
    gluing two unrelated entities together.

    Args:
      edges: All edges, in group then chronological order.

    Returns:
      Chains in the same order as their first edge.
    """
    chains: List[MigrationChain] = []
    run: List[MigrationEdge] = []
    current_key: Optional[Tuple[str, str]] = None
    for edge in edges:
        key = (edge.name_ch, edge.source_dataset)
        if key != current_key:
            if run:
                chains.append(_build_chain(run))
            run = []
            current_key = key
        if edge.relation_type in CHAIN_RELATIONS:
            run.append(edge)
        else:
            if run:
                chains.append(_build_chain(run))
            run = []
    if run:
        chains.append(_build_chain(run))
    return chains


def analyse_migrations(records: Sequence[ChgisRecord]) -> MigrationAnalysis:
    """Run the whole migration analysis.

    Args:
      records: All CHGIS records.

    Returns:
      A :class:`MigrationAnalysis` holding edges, all chains, the subset that
      qualifies as migration chains, and the statistics dictionary.
    """
    groups, undatable = build_entity_groups(records)

    edges: List[MigrationEdge] = []
    for key in sorted(groups):
        members = groups[key]
        for a, b in zip(members, members[1:]):
            edges.append(classify_pair(key[0], key[1], a, b))

    chains = assemble_chains(edges)
    migration_chains = [c for c in chains if c.is_migration_chain]

    # Deterministic identifiers: order by name, layer, then start year so the file
    # is stable across runs regardless of dict iteration order.
    chains.sort(key=lambda c: (c.name_ch, c.source_dataset, c.first_beg_yr or 0))
    migration_chains = [c for c in chains if c.is_migration_chain]
    for index, chain in enumerate(chains, start=1):
        chain.chain_id = f"ch_{index:06d}"

    relation_counts = Counter(edge.relation_type for edge in edges)
    confidence_counts = Counter(
        edge.confidence for edge in edges if edge.relation_type in EMITTED_RELATIONS
    )
    seat_histogram = Counter(chain.seat_count for chain in migration_chains)

    longest = (
        max(migration_chains, key=lambda c: (c.seat_count, c.total_path_distance_m))
        if migration_chains
        else None
    )
    longest_leg = (
        max(migration_chains, key=lambda c: c.max_leg_distance_m) if migration_chains else None
    )

    # Distance profile of the emitted migration legs.  This exists because the
    # confidence label encodes *temporal* contiguity only: a leg with gap <= 2
    # years is "high" however implausible its distance, so long legs are where a
    # false positive would hide.  Reported rather than silently capped.
    migration_legs = [edge for edge in edges if edge.relation_type == REL_MIGRATION]
    distance_buckets: Counter = Counter()
    long_high_confidence = []
    for edge in migration_legs:
        if edge.distance_m <= 10_000:
            distance_buckets["<=10km"] += 1
        elif edge.distance_m <= 50_000:
            distance_buckets["10-50km"] += 1
        elif edge.distance_m <= 100_000:
            distance_buckets["50-100km"] += 1
        elif edge.distance_m <= 200_000:
            distance_buckets["100-200km"] += 1
        else:
            distance_buckets[">200km"] += 1
        if edge.distance_m > 100_000 and edge.confidence == "high":
            long_high_confidence.append(edge)
    long_high_confidence.sort(key=lambda e: -e.distance_m)

    stats: Dict[str, object] = {
        "grouping_model": "(NAME_CH, source_dataset); layers are never mixed",
        "groups": len(groups),
        "records_in_groups": sum(len(v) for v in groups.values()),
        "records_undatable": len(undatable),
        "adjacent_pairs_total": len(edges),
        "relation_counts": dict(sorted(relation_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "chains_total": len(chains),
        "migration_chains": len(migration_chains),
        "seat_count_histogram": {str(k): v for k, v in sorted(seat_histogram.items())},
        "seat_count_2": seat_histogram.get(2, 0),
        "seat_count_3": seat_histogram.get(3, 0),
        "seat_count_4_plus": sum(v for k, v in seat_histogram.items() if k >= 4),
        "excluded_temporal_gap_too_large": relation_counts.get(REL_GAP_TOO_LARGE, 0),
        "excluded_period_overlap": relation_counts.get(REL_OVERLAP, 0),
        "excluded_coordinate_missing": relation_counts.get(REL_NO_COORD, 0),
        "longest_chain": (
            {
                "chain_id": longest.chain_id,
                "name_ch": longest.name_ch,
                "source_dataset": longest.source_dataset,
                "seat_count": longest.seat_count,
                "record_count": longest.record_count,
                "total_path_distance_m": round(longest.total_path_distance_m, 1),
                "coord_keys": longest.coord_keys,
            }
            if longest
            else None
        ),
        "longest_leg": (
            {
                "chain_id": longest_leg.chain_id,
                "name_ch": longest_leg.name_ch,
                "source_dataset": longest_leg.source_dataset,
                "max_leg_distance_m": round(longest_leg.max_leg_distance_m, 1),
            }
            if longest_leg
            else None
        ),
        "thresholds": {
            "MIGRATION_MAX_LEG_M": MIGRATION_MAX_LEG_M,
            "GAP_SAME_SEAT_HIGH": GAP_SAME_SEAT_HIGH,
            "GAP_SAME_SEAT_MAX": GAP_SAME_SEAT_MAX,
            "GAP_MIGRATION_HIGH": GAP_MIGRATION_HIGH,
            "GAP_MIGRATION_MEDIUM": GAP_MIGRATION_MEDIUM,
            "GAP_MIGRATION_MAX": GAP_MIGRATION_MAX,
            "GAP_OVERLAP_TOLERANCE": GAP_OVERLAP_TOLERANCE,
        },
        "migration_leg_distance_buckets": {
            key: distance_buckets.get(key, 0)
            for key in ("<=10km", "10-50km", "50-100km", "100-200km", ">200km")
        },
        "long_legs_over_100km_at_high_confidence": len(long_high_confidence),
        "long_leg_examples": [
            {
                "name_ch": edge.name_ch,
                "source_dataset": edge.source_dataset,
                "coord_a": edge.record_a.coord_key,
                "coord_b": edge.record_b.coord_key,
                "pres_loc_a": edge.record_a.pres_loc,
                "pres_loc_b": edge.record_b.pres_loc,
                "gap_years": edge.gap_years,
                "distance_m": round(edge.distance_m, 1),
                "confidence": edge.confidence,
            }
            for edge in long_high_confidence[:10]
        ],
        "caution": (
            "confidence reflects temporal contiguity only, not distance plausibility: a leg with "
            "gap<=2 is 'high' even at 200+ km. Legs beyond ~100 km are the likeliest false "
            "positives (same name, different province) and should be reviewed first."
        ),
    }

    return MigrationAnalysis(
        edges=edges,
        chains=chains,
        migration_chains=migration_chains,
        stats=stats,
    )


# ---------------------------------------------------------------------------
# Ground-truth regression checks
# ---------------------------------------------------------------------------

#: The three Shanxi seats the 新兴郡 chain must cover.
XINXING_JUN_EXPECTED_SEATS: Tuple[str, ...] = (
    "112.731508|38.398588",  # 忻州 (today's Xinzhou city centre)
    "112.944084|38.492717",  # 定襄 (Dingxiang county seat)
    "112.733095|38.261740",  # 忻州南三十里 (30 li south of Xinzhou)
)

#: The Guangdong seat that must stay OUT of the chain (a genuine namesake).
XINXING_JUN_FOREIGN_SEAT = "112.225082|22.702915"

#: The two 中山国 coordinates whose cross-layer disagreement must not look like a move.
ZHONGSHAN_GUO_PAIR = ("114.563995|38.140121", "114.975040|38.520060")


def verify_xinxing_jun(analysis: MigrationAnalysis) -> Dict[str, object]:
    """Regression-check the 新兴郡 case against the documented ground truth.

    Expected outcome: exactly one migration chain at ``chgis_pref`` covering the
    three Shanxi seats, with the Guangdong seat classified ``homonym_diff_place``
    because it is 1,745,947 m away, i.e. beyond :data:`MIGRATION_MAX_LEG_M`.

    Returns:
      A result dictionary with ``passed`` plus every observed value, so a failure
      can be reported as evidence rather than patched away.
    """
    chains = [
        c
        for c in analysis.chains
        if c.name_ch == "新兴郡" and c.source_dataset == "chgis_pref"
    ]
    migration_chains = [c for c in chains if c.is_migration_chain]
    chain = migration_chains[0] if migration_chains else None
    seats = chain.coord_keys if chain else []
    foreign_pairs = [
        edge
        for edge in analysis.edges
        if edge.name_ch == "新兴郡"
        and edge.source_dataset == "chgis_pref"
        and edge.relation_type == REL_HOMONYM
    ]
    foreign_seat_outside_chain = XINXING_JUN_FOREIGN_SEAT not in seats
    covered = [seat for seat in XINXING_JUN_EXPECTED_SEATS if seat in seats]
    missing = [seat for seat in XINXING_JUN_EXPECTED_SEATS if seat not in seats]

    passed = (
        len(migration_chains) == 1
        and chain is not None
        and chain.seat_count >= 3
        and not missing
        and foreign_seat_outside_chain
        and len(foreign_pairs) >= 1
    )
    return {
        "case": "新兴郡 @ chgis_pref",
        "passed": passed,
        "migration_chain_count": len(migration_chains),
        "seat_count": chain.seat_count if chain else 0,
        "observed_seats": seats,
        "expected_seats_covered": covered,
        "expected_seats_missing": missing,
        "foreign_seat_excluded_from_chain": foreign_seat_outside_chain,
        "foreign_seat": XINXING_JUN_FOREIGN_SEAT,
        "homonym_edges": [
            {
                "from_coord": edge.record_a.coord_key,
                "to_coord": edge.record_b.coord_key,
                "gap_years": edge.gap_years,
                "distance_m": round(edge.distance_m, 1),
                "confidence": edge.confidence,
            }
            for edge in foreign_pairs
        ],
        "chain_id": chain.chain_id if chain else None,
        "chain_sys_ids": chain.sys_ids if chain else [],
    }


def verify_zhongshan_guo(analysis: MigrationAnalysis) -> Dict[str, object]:
    """Regression-check that the 中山国 cross-layer conflict is not read as a move.

    The prefecture layer puts every 中山国 record at ``114.563995|38.140121`` and
    the county layer puts every record at ``114.975040|38.520060`` -- 55,410.7 m
    apart, with *identical* year spans.  Two independent safeguards must hold:
    the layer-scoped grouping means the cross-layer pair is never even formed, and
    within each layer every pair is ``dist == 0`` so at most a same-seat chain with
    one analysed coordinate appears.

    Returns:
      A result dictionary with ``passed`` and the observed values.
    """
    cross_layer_edges = [
        edge
        for edge in analysis.edges
        if (edge.record_a.source_dataset != edge.record_b.source_dataset)
    ]
    offending = [
        edge
        for edge in analysis.edges
        if {edge.record_a.coord_key, edge.record_b.coord_key} == set(ZHONGSHAN_GUO_PAIR)
    ]
    zhongshan_chains = [c for c in analysis.chains if c.name_ch == "中山国"]
    zhongshan_migration = [c for c in zhongshan_chains if c.is_migration_chain]

    passed = (
        not cross_layer_edges
        and not offending
        and not zhongshan_migration
        and all(c.seat_count <= 1 for c in zhongshan_chains)
    )
    return {
        "case": "中山国 cross-layer conflict",
        "passed": passed,
        "cross_layer_edges": len(cross_layer_edges),
        "edge_joining_the_two_disputed_coords": len(offending),
        "chains_for_name": [
            {
                "chain_id": c.chain_id,
                "source_dataset": c.source_dataset,
                "seat_count": c.seat_count,
                "is_migration_chain": c.is_migration_chain,
                "coord_keys": c.coord_keys,
            }
            for c in zhongshan_chains
        ],
        "migration_chain_count": len(zhongshan_migration),
        "exclusion_reason": (
            "grouping is (NAME_CH, source_dataset) so the prefecture and county rows are never "
            "compared; and within each layer all 中山国 records share one coordinate, so every "
            "pair is dist==0 and the chain collapses to seat_count==1"
        ),
    }
