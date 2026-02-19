"""JSON and JSONL output formatters for rdc-cli."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO


def write_json(data: Any, *, out: TextIO | None = None, indent: int = 2) -> None:
    """Write data as formatted JSON to the given output stream."""
    dest = out or sys.stdout
    dest.write(json.dumps(data, default=str, indent=indent) + "\n")


def write_jsonl(rows: list[dict[str, Any]], *, out: TextIO | None = None) -> None:
    """Write rows as JSONL (one JSON object per line)."""
    dest = out or sys.stdout
    for row in rows:
        dest.write(json.dumps(row, default=str) + "\n")
