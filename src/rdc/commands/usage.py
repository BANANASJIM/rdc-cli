"""rdc usage command — resource cross-reference."""

from __future__ import annotations

import sys
from typing import Any

import click

from rdc.commands._helpers import call
from rdc.formatters.json_fmt import write_json, write_jsonl
from rdc.formatters.options import list_output_options
from rdc.formatters.tsv import write_tsv


@click.command("usage")
@click.argument("resource_id", required=False, type=int)
@click.option("--all", "show_all", is_flag=True, help="Show all resources usage matrix.")
@click.option("--type", "res_type", default=None, help="Filter by resource type.")
@click.option("--usage", "usage_filter", default=None, help="Filter by usage type.")
@click.option("--json", "use_json", is_flag=True, help="JSON output.")
@list_output_options
def usage_cmd(
    resource_id: int | None,
    show_all: bool,
    res_type: str | None,
    usage_filter: str | None,
    use_json: bool,
    no_header: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """Show resource usage (which events read/write a resource).

    Provide a RESOURCE_ID to query a single resource, or use --all for
    the full cross-resource usage matrix.
    """
    if show_all:
        params: dict[str, Any] = {}
        if res_type is not None:
            params["type"] = res_type
        if usage_filter is not None:
            params["usage"] = usage_filter
        result = call("usage_all", params)
        if use_json:
            write_json(result)
            return
        rows = result.get("rows", [])
        if use_jsonl:
            write_jsonl(rows)
        elif quiet:
            for r in rows:
                sys.stdout.write(str(r["id"]) + "\n")
        else:
            tsv_rows = [[r["id"], r["name"], r["eid"], r["usage"]] for r in rows]
            write_tsv(tsv_rows, header=["ID", "NAME", "EID", "USAGE"], no_header=no_header)
        return

    if resource_id is None:
        click.echo("error: provide RESOURCE_ID or use --all", err=True)
        raise SystemExit(1)

    result = call("usage", {"id": resource_id})
    if use_json:
        write_json(result)
        return
    entries = result.get("entries", [])
    if use_jsonl:
        write_jsonl(entries)
    elif quiet:
        for entry in entries:
            sys.stdout.write(str(entry["eid"]) + "\n")
    else:
        tsv_rows = [[entry["eid"], entry["usage"]] for entry in entries]
        write_tsv(tsv_rows, header=["EID", "USAGE"], no_header=no_header)
