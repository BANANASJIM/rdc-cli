"""TSV output formatter for rdc-cli.

All list commands output tab-separated values with optional header row.
Numbers are always raw (e.g. 1200000 not 1.2M). Empty fields are '-'.
"""

from __future__ import annotations

import sys
from typing import Any, TextIO


def escape_field(value: Any) -> str:
    """Escape a field value for TSV output.

    Rules:
    - None or empty string → '-'
    - Tabs → '\\t'
    - Newlines → '\\n'
    - Everything else → str(value)
    """
    if value is None:
        return "-"
    s = str(value)
    if not s:
        return "-"
    return s.replace("\t", "\\t").replace("\n", "\\n")


def format_row(fields: list[Any]) -> str:
    """Format a single TSV row."""
    return "\t".join(escape_field(f) for f in fields)


def write_tsv(
    rows: list[list[Any]],
    *,
    header: list[str] | None = None,
    no_header: bool = False,
    out: TextIO | None = None,
) -> None:
    """Write rows as TSV to the given output stream.

    Args:
        rows: List of rows, each row is a list of field values.
        header: Column names for the header row.
        no_header: If True, skip the header row even if provided.
        out: Output stream. Defaults to sys.stdout.
    """
    dest = out or sys.stdout
    if header and not no_header:
        dest.write(format_row(header) + "\n")
    for row in rows:
        dest.write(format_row(row) + "\n")


def write_footer(message: str, err: TextIO | None = None) -> None:
    """Write a footer/summary line to stderr."""
    dest = err or sys.stderr
    dest.write(message + "\n")
