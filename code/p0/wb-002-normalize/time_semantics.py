"""Time-bound semantics shared by every WB-002 source.

Why this module exists
----------------------
The first pipeline revision carried a single ``time_basis`` column with the
vocabulary ``source_attested`` / ``estimated`` / ``unknown``.  That vocabulary
cannot express two things the data actually needs:

1. **Terminus post quem / ante quem (TPQ/TAQ).**  Pleiades publishes
   ``year_after_which`` and ``year_before_which``; those are *bounds*, not an
   attested span.  Rendering them as ``source_attested`` would claim the place
   existed continuously across the whole interval.
2. **Snapshot vs span.**  ``BEG_RULE``/``END_RULE`` code ``9`` is documented in
   the CHGIS ``xtra_date_rules`` workbook as *Time slice*: the year records
   **that the row was captured in a time slice**, not that the entity began or
   ended then.  Twenty-one CHGIS records carry ``END_RULE=9``; twenty of them
   have ``BEG_YR != END_YR``, so under the old vocabulary they rendered as
   confident multi-decade spans.

``time_bound_type`` replaces ``time_basis``.  It is a statement about *what kind
of claim* the two year columns make, not about how tight the interval is.

Vocabulary
----------
``exact``             Both ends come from an explicitly written year/month/date
                      (CHGIS rules 4/5/6).  The pair is a claimed validity span.
``bounded``           Both ends come from a period or reign label (CHGIS rules
                      1/2/3).  The pair is a span whose endpoints are the
                      *outer* bounds of the label, not attested event dates.
``exact_or_bounded``  One end from each of the two families above.
``tpq_taq``           The two years are a terminus post quem / terminus ante
                      quem pair (Pleiades).  The entity flourished somewhere
                      between them; continuity is not claimed.
``derived_tpq_taq``   The TPQ/TAQ pair was aggregated from child rows by
                      :func:`aggregate_tpq_taq`.
``snapshot``          The year is an observation date ("recorded in this
                      slice"), not a validity boundary.  ``valid_from`` and
                      ``valid_to`` are both set to the slice year.
``unknown``           No usable temporal statement.

``time_rule_code`` keeps the raw CHGIS ``BEG_RULE|END_RULE`` pair so a reviewer
can re-derive ``time_bound_type`` without re-reading the DBF.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "TIME_BOUND_TYPES",
    "TIME_DERIVATIONS",
    "EXACT_RULE_CODES",
    "BOUNDED_RULE_CODES",
    "SNAPSHOT_RULE_CODE",
    "TIME_BOUND_TYPE_DESCRIPTIONS",
    "chgis_time_bound_type",
    "chgis_snapshot_year",
    "chgis_time_rule_code",
    "aggregate_min_max",
    "aggregate_tpq_taq",
    "iter_time_bound_types",
]

#: Frozen vocabulary written into ``*.time_bound_type``.
TIME_BOUND_TYPES: Tuple[str, ...] = (
    "exact",
    "bounded",
    "exact_or_bounded",
    "tpq_taq",
    "derived_tpq_taq",
    "snapshot",
    "unknown",
)

#: Frozen vocabulary written into ``historical_places.time_derivation``.
TIME_DERIVATIONS: Tuple[str, ...] = (
    "min_max_of_children",
    "tpq_taq_of_children",
    "none",
)

#: CHGIS ``xtra_date_rules`` codes that pin the year to a written year, month
#: or day.  See ``chgis_extract`` / the parsed ``xtra_date_rules`` workbook.
EXACT_RULE_CODES = frozenset({"4", "5", "6"})

#: Codes whose year is the outer bound of a period label (pan-dynastic,
#: dynastic, reign).  The label can span decades, so these are not event dates.
BOUNDED_RULE_CODES = frozenset({"1", "2", "3"})

#: Code 9 is documented as *Time slice*: the year is an observation date.
SNAPSHOT_RULE_CODE = "9"

#: One-line explanations reused by the README and by the generated reports.
TIME_BOUND_TYPE_DESCRIPTIONS: dict = {
    "exact": (
        "both ends carry an explicitly written year, month or day "
        "(CHGIS BEG_RULE and END_RULE both in 4/5/6); the pair is a claimed "
        "validity span"
    ),
    "bounded": (
        "both ends are the outer bounds of a period or reign label (CHGIS rules "
        "1/2/3); the pair is a span but its endpoints are label boundaries, not "
        "attested event dates"
    ),
    "exact_or_bounded": (
        "one end is an explicitly written year and the other is a period/reign "
        "label; the interval mixes the two determinacy levels"
    ),
    "tpq_taq": (
        "the two years are a terminus post quem / terminus ante quem pair from "
        "the source; the entity flourished somewhere between them and "
        "continuity across the interval is NOT claimed"
    ),
    "derived_tpq_taq": (
        "the TPQ/TAQ pair was aggregated from the place's child rows "
        "(earliest TPQ, latest TAQ); same meaning as tpq_taq with an extra "
        "level of derivation"
    ),
    "snapshot": (
        "the year is an observation date -- 'recorded in this time slice' -- "
        "not a validity boundary; valid_from and valid_to are both set to the "
        "slice year and must not be read as an interval of existence"
    ),
    "unknown": (
        "no usable temporal statement: the rule code is blank or undocumented, "
        "the source carries no time columns, or the year pair is inverted"
    ),
}


def _clean(code: Optional[str]) -> str:
    """Normalise a raw rule code to a stripped string."""
    return (code or "").strip()


def chgis_time_bound_type(beg_rule: Optional[str], end_rule: Optional[str]) -> str:
    """Map a CHGIS ``(BEG_RULE, END_RULE)`` pair onto :data:`TIME_BOUND_TYPES`.

    Precedence, applied in order:

      1. either code is ``9``                      -> ``snapshot``;
      2. both codes in ``{4,5,6}``                 -> ``exact``;
      3. both codes in ``{1,2,3}``                 -> ``bounded``;
      4. one code in ``{4,5,6}`` and one in ``{1,2,3}`` -> ``exact_or_bounded``;
      5. anything else (blank, ``0``, ``7``, ``8``, or a mixed blank) ->
         ``unknown``.

    Rule 1 is deliberately evaluated first.  A record such as
    ``BEG_RULE=6, END_RULE=9`` mixes an explicit year with a time slice; the
    slice is the stronger statement about how the *row* was produced, so the
    whole record is downgraded to ``snapshot`` rather than being reported as
    ``exact_or_bounded``.

    Args:
      beg_rule: Raw ``BEG_RULE`` code, possibly blank.
      end_rule: Raw ``END_RULE`` code, possibly blank.

    Returns:
      One value from :data:`TIME_BOUND_TYPES`.
    """
    beg = _clean(beg_rule)
    end = _clean(end_rule)
    if beg == SNAPSHOT_RULE_CODE or end == SNAPSHOT_RULE_CODE:
        return "snapshot"
    if beg in EXACT_RULE_CODES and end in EXACT_RULE_CODES:
        return "exact"
    if beg in BOUNDED_RULE_CODES and end in BOUNDED_RULE_CODES:
        return "bounded"
    if (beg in EXACT_RULE_CODES and end in BOUNDED_RULE_CODES) or (
        beg in BOUNDED_RULE_CODES and end in EXACT_RULE_CODES
    ):
        return "exact_or_bounded"
    return "unknown"


def chgis_snapshot_year(
    beg_year: Optional[int],
    end_year: Optional[int],
    beg_rule: Optional[str],
    end_rule: Optional[str],
) -> Tuple[Optional[int], str]:
    """Return the observation year to use for a ``snapshot`` record.

    A CHGIS time-series row is *captured* in a slice; the year that carries the
    slice code is the year the row was observed.  In the shipped data the slice
    code is on the end for all 21 affected records (one of which also carries it
    on the begin), so the rule below collapses to ``END_YR`` in practice while
    still being stated generally.

    Args:
      beg_year: Raw ``BEG_YR`` (historical, no year zero).
      end_year: Raw ``END_YR``.
      beg_rule: Raw ``BEG_RULE``.
      end_rule: Raw ``END_RULE``.

    Returns:
      ``(year, basis)``.  ``year`` is ``None`` when neither side carries a year.
      ``basis`` is a short machine-readable string recording which side won,
      e.g. ``end_rule_9`` or ``begin_rule_9_conflict_with_9``.
    """
    beg = _clean(beg_rule)
    end = _clean(end_rule)
    if end == SNAPSHOT_RULE_CODE and end_year is not None:
        basis = "end_rule_9"
        if beg == SNAPSHOT_RULE_CODE and beg_year is not None and beg_year != end_year:
            basis = "end_rule_9_conflict_with_begin_rule_9"
        return end_year, basis
    if beg == SNAPSHOT_RULE_CODE and beg_year is not None:
        return beg_year, "begin_rule_9"
    # No slice code on a side that carries a year: fall back to whichever year
    # exists, and let the basis string make the fallback visible.
    if end_year is not None:
        return end_year, "fallback_end_year"
    if beg_year is not None:
        return beg_year, "fallback_beg_year"
    return None, "no_year"


def chgis_time_rule_code(beg_rule: Optional[str], end_rule: Optional[str]) -> str:
    """Render the raw CHGIS rule pair as ``BEG_RULE|END_RULE``.

    Blank codes are preserved as empty fields, so ``('6', '9')`` becomes
    ``'6|9'``, ``('', '9')`` becomes ``'|9'`` and two blanks become ``'|'``.
    The single separator is unambiguous because each side is at most one
    character wide.
    """
    return f"{_clean(beg_rule)}|{_clean(end_rule)}"


def aggregate_min_max(
    spans: Iterable[Tuple[Optional[int], Optional[int]]]
) -> Tuple[Optional[int], Optional[int]]:
    """Aggregate child year spans into one enclosing span.

    Args:
      spans: ``(from_year, to_year)`` pairs, in astronomical years.  ``None``
        entries are skipped.

    Returns:
      ``(min from, max to)``, either of which is ``None`` when no child
      supplied that side.
    """
    froms: List[int] = []
    tos: List[int] = []
    for from_year, to_year in spans:
        if from_year is not None:
            froms.append(from_year)
        if to_year is not None:
            tos.append(to_year)
    return (min(froms) if froms else None, max(tos) if tos else None)


def aggregate_tpq_taq(
    bounds: Iterable[Tuple[Optional[int], Optional[int]]]
) -> Tuple[Optional[int], Optional[int]]:
    """Aggregate child TPQ/TAQ pairs into one place-level bound.

    The envelope of several TPQ/TAQ pairs is the *earliest* TPQ and the
    *latest* TAQ: the entity is attested no later than the earliest lower bound
    and no earlier than the latest upper bound.  This is deliberately the
    widest reading; a narrower reading would need evidence the source does not
    carry.

    Args:
      bounds: ``(tpq_year, taq_year)`` pairs, in astronomical years.

    Returns:
      ``(min tpq, max taq)``.
    """
    return aggregate_min_max(bounds)


_INT_RE = re.compile(r"^[+-]?\d+$")


def parse_signed_year(text: str) -> Optional[int]:
    """Parse a signed integer year, tolerating surrounding whitespace.

    Returns ``None`` for blank text or for anything that is not a plain signed
    integer.  No range clamping is applied here; implausible magnitudes are
    reported by the caller instead of being silently dropped.
    """
    stripped = (text or "").strip()
    if not stripped or not _INT_RE.match(stripped):
        return None
    try:
        return int(stripped)
    except ValueError:  # pragma: no cover - defensive
        return None


def iter_time_bound_types() -> Sequence[str]:
    """Return the vocabulary in declaration order (convenience for reports)."""
    return TIME_BOUND_TYPES
