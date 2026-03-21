"""Resources inspection commands."""

from __future__ import annotations

import sys
from typing import Any

import click
from click.shell_completion import CompletionItem

from rdc.commands._helpers import (
    _sort_numeric_like,
    call,
    complete_pass_identifier,
    completion_call,
)
from rdc.formatters.json_fmt import write_json, write_jsonl
from rdc.formatters.kv import format_kv
from rdc.formatters.options import list_output_options
from rdc.formatters.tsv import format_row, write_tsv


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
@click.option(
    "--table",
    is_flag=True,
    default=False,
    help="Per-pass I/O table (requires --deps).",
)
@click.option(
    "--switches",
    is_flag=True,
    default=False,
    help="Show RT switch count per pass (TBR flush risk).",
)
@list_output_options
def passes_cmd(  # noqa: PLR0913
    use_json: bool,
    deps: bool,
    dot: bool,
    graph: bool,
    table: bool,
    switches: bool,
    no_header: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """List render passes."""
    if (dot or graph or table) and not deps:
        raise click.UsageError("--dot/--graph/--table requires --deps")
    if table and dot:
        raise click.UsageError("--table and --dot are mutually exclusive")
    if table and graph:
        raise click.UsageError("--table and --graph are mutually exclusive")
    if deps and (no_header or use_jsonl or quiet):
        raise click.UsageError("--deps only supports --json, --dot, --graph, and --table")
    if deps:
        _passes_deps(use_json, dot, graph, table)
        return

    params: dict[str, Any] = {}
    if switches:
        params["switches"] = True
    result = call("passes", params)
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
        header = ["NAME", "DRAWS", "DISPATCHES", "TRIANGLES", "BEGIN_EID", "END_EID"]
        if switches:
            header.append("RT_SWITCHES")
        tsv_rows = [
            [
                p.get("name", "-"),
                p.get("draws", 0),
                p.get("dispatches", 0),
                p.get("triangles", 0),
                p.get("begin_eid", "-"),
                p.get("end_eid", "-"),
            ]
            + ([p.get("rt_switches", {}).get("count", 0)] if switches else [])
            for p in passes
        ]
        write_tsv(tsv_rows, header=header, no_header=no_header)


def _passes_deps(use_json: bool, dot: bool, graph: bool, table: bool) -> None:
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
    if table:
        _format_io_table(result.get("per_pass", []))
        return
    click.echo(format_row(["SRC", "DST", "RESOURCES"]))
    for e in edges:
        rids = ",".join(str(r) for r in e["resources"])
        click.echo(format_row([e["src"], e["dst"], rids]))


def _format_dot(edges: list[dict[str, Any]]) -> None:
    click.echo("digraph {")
    for e in edges:
        label = ",".join(str(r) for r in e["resources"])
        src = e["src"].replace("\\", "\\\\").replace('"', '\\"')
        dst = e["dst"].replace("\\", "\\\\").replace('"', '\\"')
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
        marker = "*" if out.get(node) else "o"
        click.echo(f"  [{lbl[node]}] {marker} {node}")
    click.echo("")

    # Graph: each node shows outgoing edges
    click.echo("Graph:")
    for node in nodes:
        targets = out.get(node, [])
        producers = inc.get(node, set())
        from_part = f"  < {','.join(lbl[p] for p in nodes if p in producers)}" if producers else ""
        if targets:
            to_part = " --> " + ", ".join(lbl[t] for t in targets)
            click.echo(f"  {lbl[node]}{to_part}{from_part}")
        else:
            click.echo(f"  {lbl[node]}  (sink){from_part}")


def _format_ops(ops: list[Any]) -> str:
    """Format load/store ops list to a compact string."""
    if not ops:
        return "-"
    return ",".join(f"{t}={o}" for t, o in ops)


def _format_io_table(per_pass: list[dict[str, Any]]) -> None:
    write_tsv(
        [
            [
                p.get("name", "-"),
                ",".join(str(r) for r in p.get("reads", [])) or "-",
                ",".join(str(r) for r in p.get("writes", [])) or "-",
                _format_ops(p.get("load_ops", [])),
                _format_ops(p.get("store_ops", [])),
            ]
            for p in per_pass
        ],
        header=["PASS", "READS", "WRITES", "LOAD", "STORE"],
    )


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
    color_targets = data.get("color_targets", [])
    depth = data.get("depth_target")
    kv: dict[str, Any] = {
        "Pass": data.get("name", "-"),
        "Begin EID": data.get("begin_eid", "-"),
        "End EID": data.get("end_eid", "-"),
        "Draw Calls": data.get("draws", 0),
        "Dispatches": data.get("dispatches", 0),
        "Triangles": data.get("triangles", 0),
        "Color Targets": ", ".join(_format_target(t) for t in color_targets)
        if color_targets
        else "-",
        "Depth Target": _format_target(depth) if depth else "-",
    }
    load_ops = data.get("load_ops", [])
    store_ops = data.get("store_ops", [])
    if load_ops:
        kv["Load Ops"] = _format_ops(load_ops)
    if store_ops:
        kv["Store Ops"] = _format_ops(store_ops)
    click.echo(format_kv(kv))


def _format_target(target: Any) -> str:
    """Format an enriched attachment target dict for display."""
    if isinstance(target, int):
        return str(target)
    if not isinstance(target, dict):
        return str(target)
    rid = str(target.get("id", "-"))
    parts: list[str] = []
    name = target.get("name")
    if name:
        parts.append(name)
    fmt = target.get("format")
    if fmt:
        parts.append(fmt)
    w, h = target.get("width"), target.get("height")
    if w is not None and h is not None:
        parts.append(f"{w}x{h}")
    if parts:
        return f"{rid} ({', '.join(parts)})"
    return rid
