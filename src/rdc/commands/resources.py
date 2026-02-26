"""Resources inspection commands."""

from __future__ import annotations

import sys
from typing import Any

import click
from click.shell_completion import CompletionItem

from rdc.commands._helpers import call, completion_call
from rdc.formatters.json_fmt import write_json, write_jsonl
from rdc.formatters.kv import format_kv
from rdc.formatters.options import list_output_options
from rdc.formatters.tsv import format_row, write_tsv


def _complete_resource_rows() -> list[dict[str, Any]]:
    result = completion_call("resources", {})
    if result is None:
        return []
    rows = result.get("rows", [])
    return rows if isinstance(rows, list) else []


def _complete_resource_type(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    del ctx, param
    prefix = incomplete.lower()
    seen: set[str] = set()
    values: list[str] = []
    for row in _complete_resource_rows():
        value = str(row.get("type", ""))
        if not value or value in seen:
            continue
        if not value.lower().startswith(prefix):
            continue
        seen.add(value)
        values.append(value)
    return [CompletionItem(value) for value in sorted(values, key=str.lower)]


def _complete_resource_name(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    del ctx, param
    prefix = incomplete.lower()
    seen: set[str] = set()
    values: list[str] = []
    for row in _complete_resource_rows():
        value = str(row.get("name", ""))
        if not value or value in seen:
            continue
        if not value.lower().startswith(prefix):
            continue
        seen.add(value)
        values.append(value)
    return [CompletionItem(value) for value in sorted(values, key=str.lower)]


def _complete_resource_id(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    del ctx, param
    prefix = incomplete.strip()
    values: list[str] = []
    for row in _complete_resource_rows():
        rid = str(row.get("id", ""))
        if not rid or (prefix and not rid.startswith(prefix)):
            continue
        values.append(rid)
    return [CompletionItem(value) for value in sorted(set(values), key=int)]


def _complete_pass_identifier(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    del ctx, param
    result = completion_call("passes", {})
    if result is None:
        return []
    tree = result.get("tree", {})
    passes = tree.get("passes", []) if isinstance(tree, dict) else []
    prefix = incomplete.lower()
    items: list[CompletionItem] = []
    for idx, pass_row in enumerate(passes):
        index_text = str(idx)
        name = str(pass_row.get("name", ""))
        if index_text.startswith(incomplete):
            items.append(CompletionItem(index_text))
        if name and name.lower().startswith(prefix):
            items.append(CompletionItem(name))
    return items


@click.command("resources")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output JSON.")
@click.option(
    "--type",
    "type_filter",
    default=None,
    shell_complete=_complete_resource_type,
    help="Filter by resource type (exact, case-insensitive).",
)  # noqa: E501
@click.option(
    "--name",
    "name_filter",
    default=None,
    shell_complete=_complete_resource_name,
    help="Filter by name substring (case-insensitive).",
)  # noqa: E501
@click.option(
    "--sort",
    type=click.Choice(["id", "name", "type"]),
    default="id",
    show_default=True,
    help="Sort order.",
)
@list_output_options
def resources_cmd(  # noqa: PLR0913
    use_json: bool,
    type_filter: str | None,
    name_filter: str | None,
    sort: str,
    no_header: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """List all resources."""
    params: dict[str, Any] = {}
    if type_filter is not None:
        params["type"] = type_filter
    if name_filter is not None:
        params["name"] = name_filter
    if sort != "id":
        params["sort"] = sort
    result = call("resources", params)
    rows: list[dict[str, Any]] = result.get("rows", [])
    if use_json:
        write_json(rows)
    elif use_jsonl:
        write_jsonl(rows)
    elif quiet:
        for r in rows:
            sys.stdout.write(str(r.get("id", "")) + "\n")
    else:
        tsv_rows = [[r.get("id", "-"), r.get("type", "-"), r.get("name", "-")] for r in rows]
        write_tsv(tsv_rows, header=["ID", "TYPE", "NAME"], no_header=no_header)


@click.command("resource")
@click.argument("resid", type=int, shell_complete=_complete_resource_id)
@click.option("--json", "use_json", is_flag=True, default=False, help="Output JSON.")
def resource_cmd(resid: int, use_json: bool) -> None:
    """Show details of a specific resource."""
    result = call("resource", {"id": resid})
    res = result.get("resource", {})
    if use_json:
        write_json(res)
        return

    click.echo(format_row(["PROPERTY", "VALUE"]))
    for k, v in res.items():
        click.echo(format_row([str(k).upper(), str(v)]))


@click.command("passes")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output JSON.")
@list_output_options
def passes_cmd(use_json: bool, no_header: bool, use_jsonl: bool, quiet: bool) -> None:
    """List render passes."""
    result = call("passes", {})
    tree: dict[str, Any] = result.get("tree", {})
    if use_json:
        write_json(tree)
        return

    passes = tree.get("passes", [])
    if use_jsonl:
        write_jsonl(passes)
    elif quiet:
        for p in passes:
            sys.stdout.write(str(p.get("name", "")) + "\n")
    else:
        tsv_rows = [[p.get("name", "-"), p.get("draws", 0)] for p in passes]
        write_tsv(tsv_rows, header=["NAME", "DRAWS"], no_header=no_header)


@click.command("pass")
@click.argument("identifier", shell_complete=_complete_pass_identifier)
@click.option("--json", "use_json", is_flag=True, default=False, help="Output JSON.")
def pass_cmd(identifier: str, use_json: bool) -> None:
    """Show detail for a single render pass by 0-based index or name."""
    params: dict[str, Any] = {}
    try:
        params["index"] = int(identifier)
    except ValueError:
        params["name"] = identifier
    result = call("pass", params)
    if use_json:
        write_json(result)
        return
    _format_pass_detail(result)


def _format_pass_detail(data: dict[str, Any]) -> None:
    color_ids = [str(t["id"]) for t in data.get("color_targets", [])]
    depth = data.get("depth_target")
    kv = {
        "Pass": data.get("name", "-"),
        "Begin EID": data.get("begin_eid", "-"),
        "End EID": data.get("end_eid", "-"),
        "Draw Calls": data.get("draws", 0),
        "Dispatches": data.get("dispatches", 0),
        "Triangles": data.get("triangles", 0),
        "Color Targets": ", ".join(color_ids) if color_ids else "-",
        "Depth Target": depth if depth else "-",
    }
    click.echo(format_kv(kv))
