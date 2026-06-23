"""Shared output options and the list-output ladder for list commands."""

from __future__ import annotations

import functools
import sys
from collections.abc import Callable
from typing import Any, TextIO

import click

from rdc.formatters.json_fmt import write_json, write_jsonl


def list_output_options(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Attach --no-header, --json, --jsonl, -q to a Click command."""

    @click.option("--no-header", is_flag=True, help="Omit TSV header")
    @click.option("--json", "use_json", is_flag=True, help="JSON output")
    @click.option("--jsonl", "use_jsonl", is_flag=True, help="JSONL output")
    @click.option("-q", "--quiet", is_flag=True, help="Print primary key column only")
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    return wrapper


def render_list(
    rows: list[dict[str, Any]],
    *,
    use_json: bool,
    use_jsonl: bool,
    quiet: bool,
    quiet_key: str,
    quiet_default: Any = "",
    table: Callable[[], None],
    out: TextIO | None = None,
) -> None:
    """Render list-command rows through the json/jsonl/quiet/table ladder.

    The first matching branch wins, mirroring the hand-written ladder used
    across the list commands:

    1. ``use_json``  -> dump ``rows`` as a single JSON array.
    2. ``use_jsonl`` -> dump each row as a JSON line.
    3. ``quiet``     -> print ``row.get(quiet_key, quiet_default)`` per row.
    4. otherwise     -> invoke ``table`` (the per-command table renderer).

    The quiet branch uses ``dict.get`` uniformly, so a row missing the quiet
    key yields ``quiet_default`` instead of raising ``KeyError``.

    Args:
        rows: List of row dicts to render in the json/jsonl/quiet branches.
        use_json: Emit a single JSON array.
        use_jsonl: Emit one JSON object per line.
        quiet: Emit only the quiet-key column.
        quiet_key: Row key used for the quiet column.
        quiet_default: Value used when a row lacks ``quiet_key``.
        table: Callback that renders the heterogeneous table branch.
        out: Output stream for the quiet branch. Defaults to ``sys.stdout``.
    """
    if use_json:
        write_json(rows, out=out)
        return
    if use_jsonl:
        write_jsonl(rows, out=out)
        return
    if quiet:
        dest = out or sys.stdout
        for row in rows:
            dest.write(str(row.get(quiet_key, quiet_default)) + "\n")
        return
    table()
