"""CHGIS V6 time-series point layer extraction.

Reads the two read-only CHGIS V6 zips, parses their ``.dbf`` attribute tables
with :mod:`dbf_reader`, and returns fully materialised record objects that keep

* every one of the 23 original DBF fields, unmodified,
* the 1-based physical record index inside that DBF,
* the archive and DBF member the record came from.

Nothing is dropped, renamed, reordered or coerced here.  Field-name quirks in
the source data are *detected*, never assumed:

* ``v6_time_pref_pts`` names its compiler columns ``GEOCOMPLR`` and
  ``END_DATE``;
* ``v6_time_cnty_pts`` names the same columns ``GECOMPLR`` (missing an ``O``)
  and ``ENT_DATE``;
* the county layer additionally limits ``NAME_PY``/``NAME_CH``/``NAME_FT`` to
  40/45/45 bytes while the prefecture layer allows 254 bytes each.

The extractor therefore builds a *union* column order from the descriptors it
actually finds, and emits a ``nonstandard_field_name`` quality signal for the
misspelt county column instead of silently aliasing it.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from dbf_reader import DbfTable, is_overflow_marker, parse_float, parse_int, read_dbf

__all__ = [
    "CHGIS_DATASETS",
    "ChgisDataset",
    "ChgisRecord",
    "ChgisExtraction",
    "SOURCE_ID_CHGIS",
    "PREFECTURE_FIELD_ORDER",
    "COUNTY_FIELD_ORDER",
    "extract_all",
    "union_field_order",
    "read_chgis_readme",
    "citation_from_readme",
    "license_statement_from_readme",
    "mandatory_citation_from_eula",
]

#: ``source_id`` used for every CHGIS row in ``source_records``.
SOURCE_ID_CHGIS = "chgis"

#: UTF-8 byte-order-mark that CHGIS zips carry in front of their README.
_BOM = "\ufeff"


@dataclass(frozen=True)
class ChgisDataset:
    """Description of one CHGIS V6 time-series point layer.

    Attributes:
      source_dataset: Stable dataset key used across all outputs.
      zip_name: File name inside ``sample_data/chgis/``.
      layer_label: Bundled layer name used for reporting.
      level: ``'prefecture'`` or ``'county'``; the layer's own admin level.
      admin_level: Canonical admin level implemented by this layer.
    """

    source_dataset: str
    zip_name: str
    layer_label: str
    level: str
    admin_level: str


#: The two layers this pipeline consumes, in the fixed order used for stable ID
#: allocation.  Order matters: ``place_id`` numbering must be reproducible.
CHGIS_DATASETS: Sequence[ChgisDataset] = (
    ChgisDataset(
        source_dataset="chgis_pref",
        zip_name="v6_time_pref_pts_utf_wgs84.zip",
        layer_label="v6_time_pref_pts",
        level="prefecture",
        admin_level="prefecture",
    ),
    ChgisDataset(
        source_dataset="chgis_cnty",
        zip_name="v6_time_cnty_pts_utf_wgs84.zip",
        layer_label="v6_time_cnty_pts",
        level="county",
        admin_level="county",
    ),
)

#: Field order observed in ``v6_time_pref_pts_utf_wgs84.dbf``.  Recorded here as
#: a *documentation* constant so that a change in the shipped data is visible in
#: the statistics output; the reader does not trust it.
PREFECTURE_FIELD_ORDER: Sequence[str] = (
    "NAME_PY", "NAME_CH", "NAME_FT", "X_COOR", "Y_COOR", "PRES_LOC",
    "TYPE_PY", "TYPE_CH", "LEV_RANK", "BEG_YR", "BEG_RULE", "END_YR",
    "END_RULE", "NOTE_ID", "OBJ_TYPE", "SYS_ID", "GEO_SRC", "COMPILER",
    "GEOCOMPLR", "CHECKER", "END_DATE", "BEG_CHG_TY", "END_CHG_TY",
)

#: Field order observed in ``v6_time_cnty_pts_utf_wgs84.dbf``.
COUNTY_FIELD_ORDER: Sequence[str] = (
    "NAME_PY", "NAME_CH", "NAME_FT", "X_COOR", "Y_COOR", "PRES_LOC",
    "TYPE_PY", "TYPE_CH", "LEV_RANK", "BEG_YR", "BEG_RULE", "END_YR",
    "END_RULE", "NOTE_ID", "OBJ_TYPE", "SYS_ID", "GEO_SRC", "COMPILER",
    "GECOMPLR", "CHECKER", "ENT_DATE", "BEG_CHG_TY", "END_CHG_TY",
)


@dataclass
class ChgisRecord:
    """One CHGIS time-series point record, plus extraction provenance.

    Attributes:
      source_dataset: ``'chgis_pref'`` or ``'chgis_cnty'``.
      record_index: 1-based physical record index inside the source DBF.
      raw_zip: Project-relative path of the archive the record came from.
      raw_dbf: Archive member name of the DBF.
      raw: Every original DBF field, as stripped text, in source order.
    """

    source_dataset: str
    record_index: int
    raw_zip: str
    raw_dbf: str
    raw: Dict[str, str] = field(default_factory=dict)

    # ---- typed accessors -------------------------------------------------

    @property
    def sys_id_text(self) -> str:
        """``SYS_ID`` exactly as stored (never re-formatted)."""
        return self.raw.get("SYS_ID", "")

    @property
    def sys_id(self) -> Optional[int]:
        """``SYS_ID`` as an integer, or ``None`` when it is blank or malformed."""
        return parse_int(self.raw.get("SYS_ID"))

    @property
    def name_ch(self) -> str:
        """Vernacular (simplified Chinese) name."""
        return self.raw.get("NAME_CH", "")

    @property
    def name_py(self) -> str:
        """Pinyin romanisation."""
        return self.raw.get("NAME_PY", "")

    @property
    def name_ft(self) -> str:
        """Traditional-character name."""
        return self.raw.get("NAME_FT", "")

    @property
    def type_ch(self) -> str:
        """Vernacular administrative type, e.g. ``'州'``."""
        return self.raw.get("TYPE_CH", "")

    @property
    def type_py(self) -> str:
        """Pinyin administrative type, e.g. ``'Zhou'``."""
        return self.raw.get("TYPE_PY", "")

    @property
    def lev_rank(self) -> str:
        """CHGIS ``LEV_RANK`` code, kept as text."""
        return self.raw.get("LEV_RANK", "")

    @property
    def pres_loc(self) -> str:
        """Contemporary-location description used as a geography hint."""
        return self.raw.get("PRES_LOC", "")

    @property
    def beg_year(self) -> Optional[int]:
        """Raw ``BEG_YR`` as an integer.  ``None`` when blank or overflowed."""
        return parse_int(self.raw.get("BEG_YR"))

    @property
    def end_year(self) -> Optional[int]:
        """Raw ``END_YR`` as an integer.  ``None`` when blank or overflowed."""
        return parse_int(self.raw.get("END_YR"))

    @property
    def beg_rule(self) -> str:
        """Raw ``BEG_RULE`` determinacy code."""
        return self.raw.get("BEG_RULE", "")

    @property
    def end_rule(self) -> str:
        """Raw ``END_RULE`` determinacy code."""
        return self.raw.get("END_RULE", "")

    @property
    def lon_text(self) -> str:
        """``X_COOR`` as stored."""
        return self.raw.get("X_COOR", "")

    @property
    def lat_text(self) -> str:
        """``Y_COOR`` as stored."""
        return self.raw.get("Y_COOR", "")

    @property
    def lon(self) -> Optional[float]:
        """Longitude.  ``None`` when the field holds the DBF overflow marker."""
        return parse_float(self.raw.get("X_COOR"))

    @property
    def lat(self) -> Optional[float]:
        """Latitude.  ``None`` when the field holds the DBF overflow marker."""
        return parse_float(self.raw.get("Y_COOR"))

    @property
    def coord_overflow(self) -> bool:
        """True when either coordinate column holds the ``**********`` marker."""
        return is_overflow_marker(self.lon_text) or is_overflow_marker(self.lat_text)

    @property
    def has_coordinate(self) -> bool:
        """True when both coordinates parsed to finite numbers."""
        return self.lon is not None and self.lat is not None

    @property
    def coord_key(self) -> Optional[str]:
        """Exact coordinate key used for cluster analysis, e.g. ``'111.076617|39.017872'``."""
        if not self.has_coordinate:
            return None
        return f"{self.lon_text}|{self.lat_text}"

    @property
    def year_span_key(self) -> str:
        """Composite key of the raw year pair, used for duplicate detection."""
        return f"{self.raw.get('BEG_YR', '')}|{self.raw.get('END_YR', '')}"

    def identity_key(self) -> str:
        """Dataset-scoped stable identifier for this record."""
        return f"{self.source_dataset}:{self.record_index}"


@dataclass
class ChgisExtraction:
    """Result bundle returned by :func:`extract_all`."""

    records: List[ChgisRecord]
    field_order: List[str]
    tables: Dict[str, DbfTable]
    archive_sha256: Dict[str, str]
    prj_text: Dict[str, str]
    cpg_text: Dict[str, str]
    declared_field_order: Dict[str, List[str]]


def sha256_of_file(path: Path) -> str:
    """Return the lowercase hex SHA256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_sidecar(archive: zipfile.ZipFile, dbf_member: str, extension: str) -> str:
    """Read a ``.prj`` / ``.cpg`` sidecar sitting next to the DBF, if present."""
    member = dbf_member.rsplit(".", 1)[0] + extension
    try:
        return archive.read(member).decode("utf-8", errors="replace").strip()
    except KeyError:
        return ""


def _find_dbf_member(archive: zipfile.ZipFile, dataset: ChgisDataset) -> str:
    """Locate the single ``.dbf`` member inside a CHGIS layer archive."""
    members = [n for n in archive.namelist() if n.lower().endswith(".dbf")]
    if len(members) != 1:
        raise ValueError(
            f"{dataset.zip_name}: expected exactly one .dbf member, found {members!r}"
        )
    return members[0]


def union_field_order(records: Iterable[ChgisRecord]) -> List[str]:
    """Build the union of DBF field names, preserving first-seen order.

    Using first-seen order (rather than an alphabetical sort) keeps the CSV
    output readable and mirrors the source layout.  The prefecture layer is
    processed first, so ``GEOCOMPLR`` and ``END_DATE`` land before the county
    layer's ``GECOMPLR`` and ``ENT_DATE``.
    """
    order: List[str] = []
    seen = set()
    for record in records:
        for name in record.raw:
            if name not in seen:
                seen.add(name)
                order.append(name)
    return order


def extract_all(sample_dir: Path, project_root: Path) -> ChgisExtraction:
    """Extract every record from both CHGIS V6 time-series point layers.

    Args:
      sample_dir: Absolute path to ``设计资料/P0验证/WB-002/sample_data``.
      project_root: Absolute path used to render project-relative raw paths.

    Returns:
      A :class:`ChgisExtraction` holding all 15,748 records in dataset order.
    """
    records: List[ChgisRecord] = []
    tables: Dict[str, DbfTable] = {}
    archive_sha256: Dict[str, str] = {}
    prj_text: Dict[str, str] = {}
    cpg_text: Dict[str, str] = {}
    declared: Dict[str, List[str]] = {}

    for dataset in CHGIS_DATASETS:
        zip_path = sample_dir / "chgis" / dataset.zip_name
        if not zip_path.is_file():
            raise FileNotFoundError(f"missing CHGIS archive: {zip_path}")

        archive_sha256[dataset.source_dataset] = sha256_of_file(zip_path)
        rel_zip = str(zip_path.relative_to(project_root)).replace("\\", "/")

        with zipfile.ZipFile(zip_path) as archive:
            dbf_member = _find_dbf_member(archive, dataset)
            prj_text[dataset.source_dataset] = _read_sidecar(archive, dbf_member, ".prj")
            cpg_text[dataset.source_dataset] = _read_sidecar(archive, dbf_member, ".cpg")
            encoding = (cpg_text[dataset.source_dataset] or "utf-8").strip().lower() or "utf-8"
            if encoding in {"utf-8", "utf8"}:
                encoding = "utf-8"
            payload = archive.read(dbf_member)

        table = read_dbf(payload, label=f"{dataset.source_dataset}:{dbf_member}", encoding=encoding)
        tables[dataset.source_dataset] = table
        declared[dataset.source_dataset] = table.field_names

        for raw_record in table.records:
            records.append(
                ChgisRecord(
                    source_dataset=dataset.source_dataset,
                    record_index=raw_record.index,
                    raw_zip=rel_zip,
                    raw_dbf=dbf_member,
                    raw=dict(raw_record.raw),
                )
            )

    return ChgisExtraction(
        records=records,
        field_order=union_field_order(records),
        tables=tables,
        archive_sha256=archive_sha256,
        prj_text=prj_text,
        cpg_text=cpg_text,
        declared_field_order=declared,
    )


def read_chgis_readme(sample_dir: Path) -> str:
    """Return the CHGIS README text with any byte-order mark removed."""
    path = sample_dir / "chgis" / "CHGIS_V6_README.txt"
    return path.read_text(encoding="utf-8").lstrip(_BOM)


def citation_from_readme(readme_text: str) -> Optional[str]:
    """Extract the verbatim ``Citation:`` line from the CHGIS README.

    The attribution string used in ``source_records.csv`` must be the upstream
    wording, not a paraphrase, so it is pulled out of the README at run time.
    Returns ``None`` when no citation line is present.
    """
    for line in readme_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("citation:"):
            return stripped[len("citation:") :].strip()
    return None


def license_statement_from_readme(readme_text: str) -> Optional[str]:
    """Extract the verbatim ``License:`` sentence from the CHGIS README."""
    for line in readme_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("license:"):
            return stripped[len("license:") :].strip()
    return None


def mandatory_citation_from_eula(sample_dir: Path) -> Optional[str]:
    """Extract the ``Mandatory Citation:`` line from the Dataverse EULA.

    CHGIS ships **two different** official citation strings and they disagree:

    * ``CHGIS_V6_README.txt`` says ``"CHGIS, Version: 6." (c) ... Center for
      Historical Geographical Studies at Fudan University, 2016.``
    * the Dataverse dataset EULA (``dataset_FDLFJ3_EULA.json``,
      ``termsOfUse`` clause 4) says ``"CHGIS Version 6." (c) ... Institute for
      Chinese Historical Geography at Fudan University, Dec 2016.``

    They differ in punctuation (``Version: 6`` vs ``Version 6``), in the Fudan
    institution name (``Center for Historical Geographical Studies`` vs
    ``Institute for Chinese Historical Geography``) and in the date
    (``2016`` vs ``Dec 2016``).  The EULA version is the one labelled
    **Mandatory Citation** and the one accepted at download time, so it is
    treated as the operative string and the README wording is preserved
    alongside it rather than discarded.

    Args:
      sample_dir: Absolute path to ``设计资料/P0验证/WB-002/sample_data``.

    Returns:
      The citation text with the ``Mandatory Citation:`` prefix removed, or
      ``None`` when the EULA file or the clause is missing.
    """
    path = sample_dir / "chgis" / "api" / "dataset_FDLFJ3_EULA.json"
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    terms = _find_string_by_key(payload, "termsOfUse")
    if not terms:
        return None
    for line in terms.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("mandatory citation:"):
            return stripped[len("mandatory citation:") :].strip()
    return None


def _find_string_by_key(node: object, key: str) -> Optional[str]:
    """Depth-first search for the first ``str`` value stored under ``key``."""
    if isinstance(node, dict):
        for name, value in node.items():
            if name == key and isinstance(value, str):
                return value
            found = _find_string_by_key(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_string_by_key(item, key)
            if found is not None:
                return found
    return None
