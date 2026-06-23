"""rdc counters command — GPU performance counters."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands._helpers import call, complete_eid
from rdc.formatters.json_fmt import write_json
from rdc.formatters.options import list_output_options, render_list
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

        def _list_table() -> None:
            tsv_rows = [[c["id"], c["name"], c["unit"], c["type"], c["category"]] for c in counters]
            hdr = ["ID", "NAME", "UNIT", "TYPE", "CATEGORY"]
            write_tsv(tsv_rows, header=hdr, no_header=no_header)

        render_list(
            counters,
            use_json=False,
            use_jsonl=use_jsonl,
            quiet=quiet,
            quiet_key="id",
            table=_list_table,
        )
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

    def _fetch_table() -> None:
        tsv_rows = [[r["eid"], r["counter"], r["value"], r["unit"]] for r in rows]
        write_tsv(tsv_rows, header=["EID", "COUNTER", "VALUE", "UNIT"], no_header=no_header)

    render_list(
        rows,
        use_json=False,
        use_jsonl=use_jsonl,
        quiet=quiet,
        quiet_key="eid",
        table=_fetch_table,
    )
