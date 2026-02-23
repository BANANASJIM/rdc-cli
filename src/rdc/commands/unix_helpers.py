"""Unix-tool-friendly helper commands: rdc count, rdc shader-map."""

from __future__ import annotations

import sys
from typing import Any

import click

from rdc.commands._helpers import call
from rdc.formatters.json_fmt import write_json, write_jsonl
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
@click.option("--pass", "pass_name", default=None, help="Filter by render pass name.")
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
@click.option("--no-header", is_flag=True, default=False, help="Omit TSV header row.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.option("--jsonl", "use_jsonl", is_flag=True, help="JSONL output.")
@click.option("-q", "--quiet", is_flag=True, help="Print EID column only.")
def shader_map_cmd(no_header: bool, as_json: bool, use_jsonl: bool, quiet: bool) -> None:
    """Output EID-to-shader mapping as TSV."""
    rows: list[dict[str, Any]] = call("shader_map", {})["rows"]
    if as_json:
        write_json(rows)
    elif use_jsonl:
        write_jsonl(rows)
    elif quiet:
        for row in rows:
            sys.stdout.write(str(row["eid"]) + "\n")
    else:
        tsv_rows = [[row[c] for c in _SHADER_MAP_COLS] for row in rows]
        write_tsv(tsv_rows, header=_SHADER_MAP_HEADER, no_header=no_header)
