"""Deterministic CSV writing helpers.

All WB-002 CSV artefacts are written as **UTF-8 with BOM, CRLF line endings,
comma delimited, minimal double-quote quoting**, because they are meant to be
opened directly in Excel on a Chinese-locale Windows machine, where a BOM is what
makes the Chinese columns render instead of turning into mojibake.

Determinism: rows are written in the order supplied by the caller and no
timestamps, dictionaries or sets are iterated without sorting first, so two runs
with the same inputs and the same ``ingested_at`` stamp produce byte-identical
files.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

__all__ = ["write_csv", "write_json", "file_sha256", "file_size"]

#: Excel on Windows expects CRLF inside a BOM-prefixed UTF-8 file.
_LINE_TERMINATOR = "\r\n"


def write_csv(path: Path, columns: Sequence[str], rows: Iterable[Dict[str, str]]) -> int:
    """Write one CSV table.

    Args:
      path: Destination file; parent directories are created as needed.
      columns: Header and column order.  Values missing from a row are written as
        an empty cell rather than raising, so a partially populated table still
        produces a well-formed file.
      rows: Row mappings keyed by column name.

    Returns:
      The number of data rows written (header excluded).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(
            handle,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator=_LINE_TERMINATOR,
        )
        writer.writerow(list(columns))
        for row in rows:
            writer.writerow([row.get(column, "") for column in columns])
            count += 1
    return count


def write_json(path: Path, payload: object) -> None:
    """Write a JSON document with stable key order and UTF-8 encoding."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    """Return the lowercase hex SHA256 digest of a file."""
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_size(path: Path) -> int:
    """Return the size of a file in bytes."""
    return path.stat().st_size
