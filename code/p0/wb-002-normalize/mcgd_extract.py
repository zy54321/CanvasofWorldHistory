"""MCGD (Modern China Geospatial Database) sample extraction.

The sample is a 960-row head slice of ``MCGD_Data2026_08_25.csv`` published on
Zenodo (record 22094815) under CC BY 4.0.  Columns:

``Name, Prov_Zh, Prov_Py, Code, LAT, LONG, LocID, NameID, PROVID``

Verified properties of this slice (computed at run time, not assumed):

* ``NameID`` is unique per row -- it is the row/name-instance key.
* ``LocID`` is *not* unique -- it is the place key; several rows (names) can
  share one ``LocID`` while always sharing exactly one coordinate.
* ``LAT``/``LONG`` column names state the axis order, which is why
  ``axis_order_verified`` is ``'true'`` even though the CRS itself is
  undeclared.  ``original_crs`` therefore stays ``'unknown'``.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

__all__ = [
    "SOURCE_ID_MCGD",
    "MCGD_SOURCE_DATASET",
    "MCGD_ATTRIBUTION",
    "McgdRecord",
    "McgdExtraction",
    "extract_mcgd",
]

#: ``source_id`` used for every MCGD row.
SOURCE_ID_MCGD = "mcgd"

#: ``source_dataset`` value required by the WB-002 specification.
MCGD_SOURCE_DATASET = "mcgd_zenodo_22094815_head960"

#: Attribution string recorded on every MCGD row in ``source_records.csv``.
MCGD_ATTRIBUTION = "Christian Henriot / ENP-China, MCGD (Zenodo 22094815), CC BY 4.0"

#: Expected column order of the sample slice.
MCGD_COLUMNS: Sequence[str] = (
    "Name", "Prov_Zh", "Prov_Py", "Code", "LAT", "LONG", "LocID", "NameID", "PROVID",
)


@dataclass(frozen=True)
class McgdRecord:
    """One MCGD CSV row.

    Attributes:
      record_index: 1-based data row index (header excluded).
      raw: Original ``str`` values keyed by column name.
    """

    record_index: int
    raw: Dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Romanised / pinyin place name, e.g. ``"A-ch'eng Hsien"``."""
        return self.raw.get("Name", "")

    @property
    def prov_zh(self) -> str:
        """Province name in Chinese characters."""
        return self.raw.get("Prov_Zh", "")

    @property
    def prov_py(self) -> str:
        """Province name in pinyin."""
        return self.raw.get("Prov_Py", "")

    @property
    def code(self) -> str:
        """Undocumented short code (observed values: P, PP, W, WW, NA, A, J)."""
        return self.raw.get("Code", "")

    @property
    def lat(self) -> Optional[float]:
        """Latitude as a float, or ``None`` when blank / unparseable."""
        return _to_float(self.raw.get("LAT"))

    @property
    def lon(self) -> Optional[float]:
        """Longitude as a float, or ``None`` when blank / unparseable."""
        return _to_float(self.raw.get("LONG"))

    @property
    def loc_id(self) -> str:
        """Place identifier, e.g. ``'D3392205'``."""
        return self.raw.get("LocID", "")

    @property
    def name_id(self) -> str:
        """Name-instance identifier, e.g. ``'H0380830'``."""
        return self.raw.get("NameID", "")

    @property
    def prov_id(self) -> str:
        """Upstream province identifier."""
        return self.raw.get("PROVID", "")

    def identity_key(self) -> str:
        """Stable identifier for this row."""
        return f"{MCGD_SOURCE_DATASET}:{self.record_index}"


@dataclass
class McgdExtraction:
    """Result bundle returned by :func:`extract_mcgd`."""

    records: List[McgdRecord]
    csv_path_relative: str
    csv_sha256: str
    zenodo_title: str
    zenodo_doi: str
    header: List[str]
    header_matches_expected: bool


def _to_float(text: Optional[str]) -> Optional[float]:
    """Parse a CSV numeric cell, tolerating blanks and surrounding whitespace."""
    if text is None:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _sha256(path: Path) -> str:
    """Return the lowercase hex SHA256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zenodo_metadata(path: Path) -> Dict[str, str]:
    """Pull license id, title and DOI out of the cached Zenodo record JSON."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    metadata = payload.get("metadata", payload)
    license_info = metadata.get("license", {})
    if isinstance(license_info, dict):
        license_id = license_info.get("id", "")
    else:
        license_id = str(license_info)
    doi = metadata.get("doi") or payload.get("doi") or ""
    return {
        "license_id": license_id,
        "title": str(metadata.get("title", "")),
        "doi": str(doi),
    }


def extract_mcgd(sample_dir: Path, project_root: Path) -> McgdExtraction:
    """Read the 960-row MCGD head slice.

    Args:
      sample_dir: Absolute path to ``设计资料/P0验证/WB-002/sample_data``.
      project_root: Absolute path used to render a project-relative raw path.

    Returns:
      A :class:`McgdExtraction` with all rows and the license metadata.

    Raises:
      FileNotFoundError: If the sample CSV or the cached Zenodo record is absent.
    """
    csv_path = sample_dir / "mcgd" / "MCGD_Data2026_08_25.csv.head-960rows.sample.csv"
    zenodo_path = sample_dir / "mcgd" / "zenodo_record_22094815.json"
    for path in (csv_path, zenodo_path):
        if not path.is_file():
            raise FileNotFoundError(f"missing MCGD input: {path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    if not rows:
        raise ValueError(f"MCGD sample is empty: {csv_path}")

    header = [cell.strip() for cell in rows[0]]
    records: List[McgdRecord] = []
    for offset, row in enumerate(rows[1:], start=1):
        # Pad short rows so every declared column is addressable.
        padded = list(row) + [""] * (len(header) - len(row))
        raw = {name: padded[index].strip() for index, name in enumerate(header)}
        records.append(McgdRecord(record_index=offset, raw=raw))

    meta = _zenodo_metadata(zenodo_path)
    rel_csv = str(csv_path.relative_to(project_root)).replace("\\", "/")

    return McgdExtraction(
        records=records,
        csv_path_relative=rel_csv,
        csv_sha256=_sha256(csv_path),
        zenodo_title=meta["title"],
        zenodo_doi=meta["doi"],
        header=header,
        header_matches_expected=header == list(MCGD_COLUMNS),
    )
