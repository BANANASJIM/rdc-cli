"""rdc counters command — GPU performance counters."""

from __future__ import annotations

import sys
from typing import Any

import click

from rdc.commands._helpers import call, complete_eid
from rdc.formatters.json_fmt import write_json, write_jsonl
from rdc.formatters.options import list_output_options
from rdc.formatters.tsv import write_tsv


@click.command("counters")
@click.option("--list", "show_list", is_flag=True, help="List available counters.")
@click.option(
    "--eid",
    type=int,
    default=None,
    shell_complete=complete_eid,
    help="Filter to specific event ID.",
)
@click.option("--name", "name_filter", default=None, help="Filter counters by name substring.")
@click.option("--json", "use_json", is_flag=True, help="JSON output.")
@list_output_options
def counters_cmd(
    show_list: bool,
    eid: int | None,
    name_filter: str | None,
    use_json: bool,
    no_header: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """Query GPU performance counters.

    Use --list to enumerate available counters, or run without --list
    to fetch counter values for all draw events.
    """
    if show_list:
        result = call("counter_list", {})
        if use_json:
            write_json(result)
            return
        counters = result.get("counters", [])
        if use_jsonl:
            write_jsonl(counters)
        elif quiet:
            for c in counters:
                sys.stdout.write(str(c["id"]) + "\n")
        else:
            tsv_rows = [[c["id"], c["name"], c["unit"], c["type"], c["category"]] for c in counters]
            hdr = ["ID", "NAME", "UNIT", "TYPE", "CATEGORY"]
            write_tsv(tsv_rows, header=hdr, no_header=no_header)
        return

    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    if name_filter is not None:
        params["name"] = name_filter
    result = call("counter_fetch", params)
    if use_json:
        write_json(result)
        return
    rows = result.get("rows", [])
    if use_jsonl:
        write_jsonl(rows)
    elif quiet:
        for r in rows:
            sys.stdout.write(str(r["eid"]) + "\n")
    else:
        tsv_rows = [[r["eid"], r["counter"], r["value"], r["unit"]] for r in rows]
        write_tsv(tsv_rows, header=["EID", "COUNTER", "VALUE", "UNIT"], no_header=no_header)
