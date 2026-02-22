"""Unix-tool-friendly helper commands: rdc count, rdc shader-map."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands._helpers import call
from rdc.formatters.tsv import format_row

_COUNT_TARGETS = ["draws", "events", "resources", "triangles", "passes", "dispatches", "clears"]
_SHADER_MAP_HEADER = ["EID", "VS", "HS", "DS", "GS", "PS", "CS"]
_SHADER_MAP_COLS = ["eid", "vs", "hs", "ds", "gs", "ps", "cs"]


@click.command("count")
@click.argument("what", type=click.Choice(_COUNT_TARGETS, case_sensitive=False))
@click.option("--pass", "pass_name", default=None, help="Filter by render pass name.")
def count_cmd(what: str, pass_name: str | None) -> None:
    """Output a single integer count to stdout.

    Targets: draws, events, resources, triangles, passes, dispatches, clears.
    """
    params: dict[str, Any] = {"what": what}
    if pass_name is not None:
        params["pass"] = pass_name
    result = call("count", params)
    click.echo(result["value"])


@click.command("shader-map")
@click.option("--no-header", is_flag=True, default=False, help="Omit TSV header row.")
def shader_map_cmd(no_header: bool) -> None:
    """Output EID-to-shader mapping as TSV."""
    rows: list[dict[str, Any]] = call("shader_map", {})["rows"]
    if not no_header:
        click.echo(format_row(_SHADER_MAP_HEADER))
    for row in rows:
        click.echo(format_row([row[c] for c in _SHADER_MAP_COLS]))
