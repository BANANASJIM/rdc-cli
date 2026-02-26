"""Commands: rdc events, rdc draws, rdc event, rdc draw."""

from __future__ import annotations

import sys
from typing import Any

import click

from rdc.commands._helpers import call, complete_eid, complete_pass_name
from rdc.formatters.json_fmt import write_json, write_jsonl
from rdc.formatters.kv import write_kv
from rdc.formatters.tsv import write_footer, write_tsv


@click.command("events")
@click.option("--type", "event_type", default=None, help="Filter by type")
@click.option("--filter", "pattern", default=None, help="Filter by name glob")
@click.option("--limit", type=int, default=None, help="Max rows")
@click.option("--range", "eid_range", default=None, help="EID range N:M")
@click.option("--no-header", is_flag=True, help="Omit TSV header")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--jsonl", "use_jsonl", is_flag=True, help="JSONL output")
@click.option("-q", "--quiet", is_flag=True, help="Only EID column")
def events_cmd(
    event_type: str | None,
    pattern: str | None,
    limit: int | None,
    eid_range: str | None,
    no_header: bool,
    use_json: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """List all events."""
    params: dict[str, Any] = {}
    if event_type:
        params["type"] = event_type
    if pattern:
        params["filter"] = pattern
    if limit is not None:
        params["limit"] = limit
    if eid_range:
        params["range"] = eid_range
    result = call("events", params)
    rows_data = result.get("events", [])
    if use_json:
        write_json(rows_data)
        return
    if use_jsonl:
        write_jsonl(rows_data)
        return
    if quiet:
        for r in rows_data:
            sys.stdout.write(str(r["eid"]) + chr(10))
        return
    header = ["EID", "TYPE", "NAME"]
    rows = [[r["eid"], r["type"], r["name"]] for r in rows_data]
    write_tsv(rows, header=header, no_header=no_header)


@click.command("draws")
@click.option(
    "--pass",
    "pass_name",
    default=None,
    help="Filter by pass name",
    shell_complete=complete_pass_name,
)
@click.option("--sort", "sort_field", default=None, help="Sort field")
@click.option("--limit", type=int, default=None, help="Max rows")
@click.option("--no-header", is_flag=True, help="Omit TSV header")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--jsonl", "use_jsonl", is_flag=True, help="JSONL output")
@click.option("-q", "--quiet", is_flag=True, help="Only EID column")
def draws_cmd(
    pass_name: str | None,
    sort_field: str | None,
    limit: int | None,
    no_header: bool,
    use_json: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """List draw calls."""
    params: dict[str, Any] = {}
    if pass_name:
        params["pass"] = pass_name
    if sort_field:
        params["sort"] = sort_field
    if limit is not None:
        params["limit"] = limit
    result = call("draws", params)
    rows_data = result.get("draws", [])
    summary = result.get("summary", "")
    if use_json:
        write_json(rows_data)
        return
    if use_jsonl:
        write_jsonl(rows_data)
        return
    if quiet:
        for r in rows_data:
            sys.stdout.write(str(r["eid"]) + chr(10))
        return
    header = ["EID", "TYPE", "TRIANGLES", "INSTANCES", "PASS", "MARKER"]
    rows = [
        [
            r["eid"],
            r["type"],
            r["triangles"],
            r["instances"],
            r.get("pass", "-"),
            r.get("marker", "-"),
        ]
        for r in rows_data
    ]
    write_tsv(rows, header=header, no_header=no_header)
    if summary:
        write_footer(summary)


@click.command("event")
@click.argument("eid", type=int, shell_complete=complete_eid)
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def event_cmd(eid: int, use_json: bool) -> None:
    """Show single API call detail."""
    result = call("event", {"eid": eid})
    if use_json:
        write_json(result)
        return
    write_kv(result)


@click.command("draw")
@click.argument("eid", type=int, required=False, default=None, shell_complete=complete_eid)
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def draw_cmd(eid: int | None, use_json: bool) -> None:
    """Show draw call detail."""
    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    result = call("draw", params)
    if use_json:
        write_json(result)
        return
    write_kv(result)
