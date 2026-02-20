"""rdc usage command — resource cross-reference."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands.info import _daemon_call
from rdc.formatters.json_fmt import write_json


@click.command("usage")
@click.argument("resource_id", required=False, type=int)
@click.option("--all", "show_all", is_flag=True, help="Show all resources usage matrix.")
@click.option("--type", "res_type", default=None, help="Filter by resource type.")
@click.option("--usage", "usage_filter", default=None, help="Filter by usage type.")
@click.option("--json", "use_json", is_flag=True, help="JSON output.")
def usage_cmd(
    resource_id: int | None,
    show_all: bool,
    res_type: str | None,
    usage_filter: str | None,
    use_json: bool,
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
        result = _daemon_call("usage_all", params)
        if use_json:
            write_json(result)
            return
        rows = result.get("rows", [])
        click.echo("ID\tNAME\tEID\tUSAGE")
        for r in rows:
            click.echo(f"{r['id']}\t{r['name']}\t{r['eid']}\t{r['usage']}")
        return

    if resource_id is None:
        click.echo("error: provide RESOURCE_ID or use --all", err=True)
        raise SystemExit(1)

    result = _daemon_call("usage", {"id": resource_id})
    if use_json:
        write_json(result)
        return
    click.echo("EID\tUSAGE")
    for entry in result.get("entries", []):
        click.echo(f"{entry['eid']}\t{entry['usage']}")
