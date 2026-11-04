"""Pure-standard-library reader for dBase III / IV (``.dbf``) attribute tables.

This module intentionally avoids third-party dependencies (no ``dbfread``, no
``pyshp``, no ``pandas``) so the WB-002 normalisation pipeline can run on a bare
Python 3.13 interpreter with no network access.

Only the subset of the DBF specification that CHGIS V6 actually uses is
implemented:

* 32 byte file header.
  - offset 4:8   uint32 LE  record count
  - offset 8:10  uint16 LE  header length
  - offset 10:12 uint16 LE  record length
* Field descriptors start at offset 32 and are 32 bytes each, terminated by the
  ``0x0D`` carriage-return marker.
  - name      bytes ``p .. p+11`` (NUL padded)
  - type      byte  ``p+11``       (``C``, ``N``, ``F``, ``D``, ``L``, ...)
  - length    byte  ``p+16``
  - decimals  byte  ``p+17``
* The record area starts at ``header_length``.  Every record begins with a one
  byte deletion flag (``b' '`` = live, ``b'*'`` = deleted), followed by
  fixed-width field slices in descriptor order.

Design note
-----------
Numeric fields are returned as the *raw text exactly as stored*.  Conversion is
done on demand by :func:`parse_number` / :func:`parse_int` / :func:`parse_float`
because CHGIS uses the DBF "field overflow" marker (``**********``) which must
stay distinguishable from a genuine blank.  Collapsing both into ``None`` at
read time would silently destroy the evidence that the value was lost during
compilation rather than never recorded.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

__all__ = [
    "DbfField",
    "DbfRecord",
    "DbfTable",
    "DbfFormatError",
    "parse_number",
    "parse_int",
    "parse_float",
    "is_overflow_marker",
]

#: One byte at the start of the record area marking a logically deleted row.
_DELETED_FLAG = b"*"
_LIVE_FLAG = b" "

#: Byte that terminates the field descriptor array.
_FIELD_TERMINATOR = 0x0D

#: DBF numeric "value too wide for the field" marker produced by dBase/ArcGIS.
_OVERFLOW_CHAR = "*"

#: Fields whose textual payload should be stripped of surrounding blanks.
_TEXT_TYPES = frozenset({"C", "D", "L", "M"})
_NUMERIC_TYPES = frozenset({"N", "F"})


class DbfFormatError(ValueError):
    """Raised when a byte buffer cannot be interpreted as a DBF table."""


@dataclass(frozen=True)
class DbfField:
    """A single field descriptor from the DBF header.

    Attributes:
      name: Field name, upper-cased exactly as stored (no normalisation).
      type: One character DBF type code, e.g. ``'C'`` or ``'N'``.
      length: Fixed width of the field in bytes.
      decimals: Declared decimal count (0 for integer / text fields).
    """

    name: str
    type: str
    length: int
    decimals: int


@dataclass(frozen=True)
class DbfRecord:
    """One physical record from the record area.

    Attributes:
      index: 1-based physical record index (includes deleted rows so that the
        index stays a stable pointer back into the on-disk byte stream).
      deleted: True when the DBF deletion flag was ``b'*'``.
      raw: Mapping of field name to the raw stripped text value.
    """

    index: int
    deleted: bool
    raw: Dict[str, str]


@dataclass
class DbfTable:
    """A parsed DBF table plus the header metadata used to parse it."""

    label: str
    encoding: str
    record_count: int
    header_length: int
    record_length: int
    fields: List[DbfField] = field(default_factory=list)
    records: List[DbfRecord] = field(default_factory=list)

    @property
    def field_names(self) -> List[str]:
        """Field names in physical descriptor order."""
        return [f.name for f in self.fields]

    @property
    def live_records(self) -> List[DbfRecord]:
        """Records whose deletion flag is 'live'."""
        return [r for r in self.records if not r.deleted]

    @property
    def deleted_count(self) -> int:
        """Number of records flagged as deleted."""
        return sum(1 for r in self.records if r.deleted)


def read_dbf(data: bytes, label: str = "", encoding: str = "utf-8") -> DbfTable:
    """Parse an in-memory DBF byte buffer.

    Args:
      data: Complete contents of the ``.dbf`` file.
      label: Human readable identifier used in error messages and logs.
      encoding: Character encoding for ``C``-type fields.  CHGIS V6 ships
        ``.cpg`` files declaring ``UTF-8``; the caller is expected to have
        read that file and to pass the correct codec here.

    Returns:
      A :class:`DbfTable` with every physical record parsed (deleted rows are
      retained and flagged, never dropped).

    Raises:
      DbfFormatError: If the buffer is too short or the header is inconsistent.
    """
    if len(data) < 32:
        raise DbfFormatError(f"{label}: buffer of {len(data)} bytes is shorter than a DBF header")

    record_count = struct.unpack("<I", data[4:8])[0]
    header_length = struct.unpack("<H", data[8:10])[0]
    record_length = struct.unpack("<H", data[10:12])[0]

    if header_length < 33 or header_length > len(data):
        raise DbfFormatError(
            f"{label}: header_length {header_length} is outside the buffer ({len(data)} bytes)"
        )
    if record_length < 1:
        raise DbfFormatError(f"{label}: record_length {record_length} is not positive")

    fields = _read_field_descriptors(data, header_length, label)

    declared_width = 1 + sum(f.length for f in fields)
    if declared_width != record_length:
        raise DbfFormatError(
            f"{label}: header declares record_length={record_length} but the "
            f"{len(fields)} field descriptors sum to {declared_width} (1 flag byte + fields)"
        )

    available = (len(data) - header_length) // record_length
    if available < record_count:
        raise DbfFormatError(
            f"{label}: header declares {record_count} records but only {available} fit in the buffer"
        )

    records: List[DbfRecord] = []
    for i in range(record_count):
        offset = header_length + i * record_length
        block = data[offset : offset + record_length]
        flag = block[0:1]
        if flag not in (_LIVE_FLAG, _DELETED_FLAG):
            raise DbfFormatError(
                f"{label}: record {i + 1} has an unexpected deletion flag byte {flag!r}"
            )
        raw: Dict[str, str] = {}
        cursor = 1
        for fld in fields:
            chunk = block[cursor : cursor + fld.length]
            cursor += fld.length
            raw[fld.name] = _decode_chunk(chunk, fld, encoding, label, i + 1)
        records.append(DbfRecord(index=i + 1, deleted=flag == _DELETED_FLAG, raw=raw))

    return DbfTable(
        label=label,
        encoding=encoding,
        record_count=record_count,
        header_length=header_length,
        record_length=record_length,
        fields=fields,
        records=records,
    )


def _read_field_descriptors(data: bytes, header_length: int, label: str) -> List[DbfField]:
    """Walk the 32-byte field descriptor array inside the header."""
    fields: List[DbfField] = []
    cursor = 32
    while cursor < header_length:
        if data[cursor] == _FIELD_TERMINATOR:
            break
        if cursor + 32 > header_length:
            raise DbfFormatError(
                f"{label}: truncated field descriptor at offset {cursor}"
            )
        name = data[cursor : cursor + 11].split(b"\x00")[0].decode("latin-1").strip()
        if not name:
            raise DbfFormatError(f"{label}: field descriptor at offset {cursor} has an empty name")
        fields.append(
            DbfField(
                name=name,
                type=chr(data[cursor + 11]).upper(),
                length=data[cursor + 16],
                decimals=data[cursor + 17],
            )
        )
        cursor += 32
    if not fields:
        raise DbfFormatError(f"{label}: no field descriptors found")
    return fields


def _decode_chunk(
    chunk: bytes, fld: DbfField, encoding: str, label: str, record_index: int
) -> str:
    """Decode one fixed-width field slice into its raw stripped text form."""
    try:
        text = chunk.decode(encoding)
    except UnicodeDecodeError as exc:  # pragma: no cover - defensive
        raise DbfFormatError(
            f"{label}: record {record_index} field {fld.name} is not valid {encoding}: {exc}"
        ) from exc
    if fld.type in _TEXT_TYPES:
        return text.strip()
    if fld.type in _NUMERIC_TYPES:
        return text.strip()
    return text.strip()


def is_overflow_marker(text: Optional[str]) -> bool:
    """Return True when the value is the DBF 'field too narrow' asterisk marker."""
    if not text:
        return False
    stripped = text.strip()
    return bool(stripped) and set(stripped) == {_OVERFLOW_CHAR}


def parse_number(text: Optional[str]) -> Optional[float]:
    """Convert a DBF numeric field to ``float``, or ``None`` when unusable.

    Blank values and the all-asterisk overflow marker both map to ``None``;
    callers that must distinguish the two should test
    :func:`is_overflow_marker` first.
    """
    if text is None:
        return None
    stripped = text.strip()
    if not stripped or is_overflow_marker(stripped):
        return None
    stripped = stripped.replace(",", "")
    try:
        return float(stripped)
    except ValueError:
        return None


def parse_int(text: Optional[str]) -> Optional[int]:
    """Convert a DBF numeric field to ``int``, rounding when a fraction is stored."""
    value = parse_number(text)
    if value is None:
        return None
    return int(round(value))


def parse_float(text: Optional[str]) -> Optional[float]:
    """Convert a DBF numeric field to ``float``."""
    return parse_number(text)


def summarise(table: DbfTable) -> Sequence[str]:
    """Return a short human readable description of a parsed table (for logs)."""
    return (
        f"{table.label}: {table.record_count} records "
        f"({table.deleted_count} deleted), {len(table.fields)} fields, "
        f"header={table.header_length}B record={table.record_length}B encoding={table.encoding}",
    )
