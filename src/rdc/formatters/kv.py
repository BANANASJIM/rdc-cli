"""Key-value pair formatting (aligned columns)."""

from __future__ import annotations

import sys
from typing import Any, TextIO


def format_kv(data: dict[str, Any]) -> str:
    """Format a dict as aligned key-value pairs.

    Returns a multi-line string. Non-dict or empty input falls through to str().
    None and empty-string values render as ``-``.
    """
    if not isinstance(data, dict) or not data:
        return str(data)
    max_key = max(len(str(k)) for k in data)
    lines: list[str] = []
    for k, v in data.items():
        if v is None or v == "":
            v = "-"
        label = str(k) + ":"
        lines.append(f"{label:<{max_key + 2}}{v}")
    return "\n".join(lines)


def write_kv(data: dict[str, Any], out: TextIO | None = None) -> None:
    """Format a dict as aligned key-value pairs and write to a stream."""
    dest = out or sys.stdout
    dest.write(format_kv(data) + "\n")
