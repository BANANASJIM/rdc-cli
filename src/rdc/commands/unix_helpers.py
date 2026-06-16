"""Unix-tool-friendly helper commands: rdc count, rdc shader-map."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands._helpers import call, complete_pass_name
from rdc.formatters.options import list_output_options, render_list
from rdc.formatters.tsv import write_tsv

_COUNT_TARGETS = [
    "draws",
    "events",
    "resources",
    "triangles",
    "passes",
    "dispatches",
    "clears",
    "shaders",
]
_SHADER_MAP_HEADER = ["EID", "VS", "HS", "DS", "GS", "PS", "CS"]
_SHADER_MAP_COLS = ["eid", "vs", "hs", "ds", "gs", "ps", "cs"]


@click.command("count")
@click.argument("what", type=click.Choice(_COUNT_TARGETS, case_sensitive=False))
@click.option(
    "--pass",
    "pass_name",
    default=None,
    help="Filter by render pass name.",
    shell_complete=complete_pass_name,
)
def count_cmd(what: str, pass_name: str | None) -> None:
    """Output a single integer count to stdout.

    Targets: draws, events, resources, triangles, passes, dispatches, clears, shaders.
    """
    params: dict[str, Any] = {"what": what}
    if pass_name is not None:
        params["pass"] = pass_name
    result = call("count", params)
    click.echo(result["value"])


@click.command("shader-map")
@list_output_options
def shader_map_cmd(no_header: bool, use_json: bool, use_jsonl: bool, quiet: bool) -> None:
    """Output EID-to-shader mapping as TSV."""
    rows: list[dict[str, Any]] = call("shader_map", {})["rows"]

    def _table() -> None:
        tsv_rows = [[row[c] for c in _SHADER_MAP_COLS] for row in rows]
        write_tsv(tsv_rows, header=_SHADER_MAP_HEADER, no_header=no_header)

    render_list(
        rows,
        use_json=use_json,
        use_jsonl=use_jsonl,
        quiet=quiet,
        quiet_key="eid",
        table=_table,
    )
