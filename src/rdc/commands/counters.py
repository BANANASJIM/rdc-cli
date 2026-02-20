"""rdc counters command — GPU performance counters."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands.info import _daemon_call
from rdc.formatters.json_fmt import write_json


@click.command("counters")
@click.option("--list", "show_list", is_flag=True, help="List available counters.")
@click.option("--eid", type=int, default=None, help="Filter to specific event ID.")
@click.option("--name", "name_filter", default=None, help="Filter counters by name substring.")
@click.option("--json", "use_json", is_flag=True, help="JSON output.")
def counters_cmd(
    show_list: bool,
    eid: int | None,
    name_filter: str | None,
    use_json: bool,
) -> None:
    """Query GPU performance counters.

    Use --list to enumerate available counters, or run without --list
    to fetch counter values for all draw events.
    """
    if show_list:
        result = _daemon_call("counter_list")
        if use_json:
            write_json(result)
            return
        click.echo("ID\tNAME\tUNIT\tTYPE\tCATEGORY")
        for c in result.get("counters", []):
            click.echo(f"{c['id']}\t{c['name']}\t{c['unit']}\t{c['type']}\t{c['category']}")
        return

    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    if name_filter is not None:
        params["name"] = name_filter
    result = _daemon_call("counter_fetch", params)
    if use_json:
        write_json(result)
        return
    click.echo("EID\tCOUNTER\tVALUE\tUNIT")
    for r in result.get("rows", []):
        click.echo(f"{r['eid']}\t{r['counter']}\t{r['value']}\t{r['unit']}")
