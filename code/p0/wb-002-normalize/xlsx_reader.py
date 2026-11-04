"""Minimal pure-standard-library reader for ``.xlsx`` workbooks.

The CHGIS V6 data dictionary is distributed as
``CHGIS_data_dictionary.zip`` containing six ``.xlsx`` workbooks.  Converting
those to CSV without ``openpyxl`` requires reading the OOXML zip container by
hand, which is what this module does.

Supported subset
----------------
* ``xl/sharedStrings.xml`` (``t="s"`` cells) -- present in most workbooks.
* ``t="inlineStr"`` cells (``<is><t>text</t></is>``) -- what CHGIS ships.
* ``t="str"`` formula results and plain numeric ``<v>`` cells.
* Column letters are resolved through the ``r`` attribute so that horizontally
  sparse sheets keep their columns aligned.

Anything outside that subset (styles, merged cells, dates stored as serial
numbers) is returned as the raw cell text.  Callers that need temporal values
must interpret them explicitly rather than relying on an implicit locale.
"""

from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Sequence

__all__ = ["XlsxError", "read_xlsx_bytes", "read_xlsx_from_zip", "find_sheet_paths"]

_NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

_COLUMN_REF = re.compile(r"^([A-Z]+)")


class XlsxError(ValueError):
    """Raised when a workbook cannot be read with the supported subset."""


def _column_index(cell_ref: str) -> int:
    """Convert an A1-style cell reference to a zero-based column index."""
    match = _COLUMN_REF.match(cell_ref or "")
    if not match:
        return 0
    index = 0
    for char in match.group(1):
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def find_sheet_paths(archive: zipfile.ZipFile) -> List[str]:
    """Return worksheet part names inside an xlsx archive, in workbook order."""
    names = [n for n in archive.namelist() if n.startswith("xl/worksheets/") and n.endswith(".xml")]
    return sorted(names)


def _read_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    """Load ``xl/sharedStrings.xml`` into an ordered list of strings."""
    try:
        payload = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(payload)
    strings: List[str] = []
    for si in root.iter(_NS_MAIN + "si"):
        strings.append("".join(node.text or "" for node in si.iter(_NS_MAIN + "t")))
    return strings


def _cell_text(cell: ET.Element, shared: Sequence[str]) -> str:
    """Extract the display text from a single ``<c>`` element."""
    cell_type = cell.get("t", "")
    if cell_type == "inlineStr":
        inline = cell.find(_NS_MAIN + "is")
        if inline is None:
            return ""
        return "".join(node.text or "" for node in inline.iter(_NS_MAIN + "t"))
    value_node = cell.find(_NS_MAIN + "v")
    if value_node is None or value_node.text is None:
        return ""
    if cell_type == "s":
        try:
            return shared[int(value_node.text)]
        except (ValueError, IndexError):
            return ""
    return value_node.text


def read_xlsx_bytes(data: bytes, sheet_name: Optional[str] = None) -> List[List[str]]:
    """Read one worksheet out of an in-memory ``.xlsx`` file.

    Args:
      data: Raw bytes of the ``.xlsx`` container.
      sheet_name: Optional worksheet part name, e.g. ``'xl/worksheets/sheet1.xml'``.
        Defaults to the first worksheet found.

    Returns:
      Rows of cell text.  Rows are padded to the widest row length so that
      callers can index columns positionally.

    Raises:
      XlsxError: If the container holds no readable worksheet.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise XlsxError(f"not a zip container: {exc}") from exc

    with archive:
        sheets = find_sheet_paths(archive)
        if not sheets:
            raise XlsxError("workbook contains no xl/worksheets/*.xml part")
        target = sheet_name if sheet_name in sheets else sheets[0]
        shared = _read_shared_strings(archive)
        root = ET.fromstring(archive.read(target))

    grid: List[List[str]] = []
    for row in root.iter(_NS_MAIN + "row"):
        cells: Dict[int, str] = {}
        for position, cell in enumerate(row.iter(_NS_MAIN + "c")):
            ref = cell.get("r")
            index = _column_index(ref) if ref else position
            cells[index] = _cell_text(cell, shared)
        if not cells:
            grid.append([])
            continue
        width = max(cells) + 1
        grid.append([cells.get(i, "") for i in range(width)])

    width = max((len(r) for r in grid), default=0)
    for row in grid:
        while len(row) < width:
            row.append("")
    return grid


def read_xlsx_from_zip(
    outer_zip_path: str, member_name: str, sheet_name: Optional[str] = None
) -> List[List[str]]:
    """Read a worksheet from an ``.xlsx`` nested inside an outer zip archive.

    The CHGIS data dictionary ships as ``CHGIS_data_dictionary.zip`` whose
    members are themselves ``.xlsx`` files, so two zip layers must be opened.

    Args:
      outer_zip_path: Filesystem path to the outer archive.
      member_name: Name of the ``.xlsx`` member inside the outer archive.
      sheet_name: Optional worksheet part name.

    Returns:
      Rows of cell text, as produced by :func:`read_xlsx_bytes`.
    """
    with zipfile.ZipFile(outer_zip_path) as outer:
        payload = outer.read(member_name)
    return read_xlsx_bytes(payload, sheet_name=sheet_name)


def rows_to_dicts(grid: Sequence[Sequence[str]]) -> List[Dict[str, str]]:
    """Turn a grid whose first row is a header into a list of dicts."""
    if not grid:
        return []
    header = [h.strip() for h in grid[0]]
    records: List[Dict[str, str]] = []
    for row in grid[1:]:
        if not any(cell.strip() for cell in row):
            continue
        record = {}
        for index, name in enumerate(header):
            if not name:
                continue
            record[name] = row[index] if index < len(row) else ""
        records.append(record)
    return records
