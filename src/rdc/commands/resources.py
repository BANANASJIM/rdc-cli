"""Resources inspection commands."""

from __future__ import annotations

import sys
from typing import Any

import click
from click.shell_completion import CompletionItem

from rdc.commands._helpers import call, complete_pass_identifier, completion_call
from rdc.formatters.json_fmt import write_json, write_jsonl
from rdc.formatters.kv import format_kv
from rdc.formatters.options import list_output_options
from rdc.formatters.tsv import format_row, write_tsv


def _sort_numeric_like(values: set[str] | list[str]) -> list[str]:
    return sorted(values, key=lambda value: (0, int(value)) if value.isdigit() else (1, value))


def _complete_resource_rows() -> list[dict[str, Any]]:
    result = completion_call("resources", {})
    if not isinstance(result, dict):
        return []
    rows = result.get("rows", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _complete_resource_type(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    try:
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
    except Exception:
        return []


def _complete_resource_name(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    try:
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
    except Exception:
        return []


def _complete_resource_id(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    try:
        del ctx, param
        prefix = incomplete.strip()
        values: list[str] = []
        for row in _complete_resource_rows():
            rid = str(row.get("id", ""))
            if not rid or (prefix and not rid.startswith(prefix)):
                continue
            values.append(rid)
        return [CompletionItem(value) for value in _sort_numeric_like(set(values))]
    except Exception:
        return []


def _complete_pass_identifier(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    try:
        del ctx, param
        result = completion_call("passes", {})
        if not isinstance(result, dict):
            return []
        tree = result.get("tree", {})
        passes = tree.get("passes", []) if isinstance(tree, dict) else []
        if not isinstance(passes, list):
            return []
        prefix = incomplete.lower()
        items: list[CompletionItem] = []
        for idx, pass_row in enumerate(passes):
            if not isinstance(pass_row, dict):
                continue
            index_text = str(idx)
            name = str(pass_row.get("name", ""))
            if index_text.startswith(incomplete):
                items.append(CompletionItem(index_text))
            if name and name.lower().startswith(prefix):
                items.append(CompletionItem(name))
        return items
    except Exception:
        return []


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
@click.option("--deps", is_flag=True, default=False, help="Show pass dependency DAG.")
@click.option("--dot", is_flag=True, default=False, help="Graphviz DOT output (requires --deps).")
@click.option(
    "--graph", is_flag=True, default=False, help="Human-readable graph (requires --deps)."
)
@list_output_options
def passes_cmd(
    use_json: bool,
    deps: bool,
    dot: bool,
    graph: bool,
    no_header: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """List render passes."""
    if (dot or graph) and not deps:
        raise click.UsageError("--dot/--graph requires --deps")
    if deps:
        _passes_deps(use_json, dot, graph)
        return

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


def _passes_deps(use_json: bool, dot: bool, graph: bool) -> None:
    result = call("pass_deps", {})
    edges: list[dict[str, Any]] = result.get("edges", [])
    if use_json:
        write_json(result)
        return
    if dot:
        _format_dot(edges)
        return
    if graph:
        _format_graph(edges)
        return
    click.echo(format_row(["SRC", "DST", "RESOURCES"]))
    for e in edges:
        rids = ",".join(str(r) for r in e["resources"])
        click.echo(format_row([e["src"], e["dst"], rids]))


def _format_dot(edges: list[dict[str, Any]]) -> None:
    click.echo("digraph {")
    for e in edges:
        label = ",".join(str(r) for r in e["resources"])
        src = e["src"].replace('"', '\\"')
        dst = e["dst"].replace('"', '\\"')
        click.echo(f'  "{src}" -> "{dst}" [label="{label}"];')
    click.echo("}")


def _format_graph(edges: list[dict[str, Any]]) -> None:
    if not edges:
        click.echo("(no dependencies)")
        return

    # Collect nodes in order, assign short labels
    out: dict[str, list[str]] = {}
    inc: dict[str, set[str]] = {}
    nodes: list[str] = []
    for e in edges:
        src, dst = e["src"], e["dst"]
        out.setdefault(src, []).append(dst)
        inc.setdefault(dst, set()).add(src)
        out.setdefault(dst, [])
        inc.setdefault(src, set())
        if src not in nodes:
            nodes.append(src)
        if dst not in nodes:
            nodes.append(dst)

    # Short labels: A, B, C, ... Z, AA, AB, ...
    labels: dict[str, str] = {}
    for i, n in enumerate(nodes):
        if i < 26:
            labels[n] = chr(65 + i)
        else:
            labels[n] = chr(64 + i // 26) + chr(65 + i % 26)
    lbl = labels  # alias

    # Legend
    click.echo("Legend:")
    for node in nodes:
        marker = "●" if out.get(node) else "○"
        click.echo(f"  [{lbl[node]}] {marker} {node}")
    click.echo("")

    # Graph: each node shows outgoing edges
    click.echo("Graph:")
    for node in nodes:
        targets = out.get(node, [])
        producers = inc.get(node, set())
        from_part = f"  ◀ {','.join(lbl[p] for p in nodes if p in producers)}" if producers else ""
        if targets:
            to_part = " ──▶ " + ", ".join(lbl[t] for t in targets)
            click.echo(f"  {lbl[node]}{to_part}{from_part}")
        else:
            click.echo(f"  {lbl[node]}  (sink){from_part}")


@click.command("pass")
@click.argument("identifier", shell_complete=complete_pass_identifier)
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
