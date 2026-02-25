"""VFS commands: ls, cat, tree, _complete."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from click.shell_completion import CompletionItem

from rdc.commands._helpers import call, fetch_remote_file
from rdc.formatters.json_fmt import write_json, write_jsonl
from rdc.formatters.kv import format_kv
from rdc.session_state import load_session as _load_session
from rdc.vfs.formatter import render_ls, render_ls_long, render_tree_root
from rdc.vfs.router import resolve_path


def _fmt_log(data: dict[str, Any]) -> str:
    messages = data.get("messages", [])
    lines = ["LEVEL\tEID\tMESSAGE"]
    for m in messages:
        msg = str(m.get("message", "-")).replace("\t", " ").replace("\n", " ")
        lines.append(f"{m.get('level', '-')}\t{m.get('eid', 0)}\t{msg}")
    return "\n".join(lines)


def _fmt_pixel_mod(m: dict[str, Any]) -> str:
    d = m["depth"]
    depth_s = f"{d:.4f}" if d is not None else "-"
    passed_s = "yes" if m["passed"] else "no"
    flags_s = ",".join(m["flags"]) or "-"
    return f"{m['eid']}\t{m['fragment']}\t{depth_s}\t{passed_s}\t{flags_s}"


_EXTRACTORS: dict[str, Callable[..., str]] = {
    "info": lambda r: format_kv(r),
    "stats": lambda r: format_kv(r),
    "event": lambda r: format_kv(r),
    "pass": lambda r: format_kv(r),
    "resource": lambda r: format_kv(r.get("resource", r)),
    "pipeline": lambda r: format_kv(r.get("row", r)),
    "shader_disasm": lambda r: r.get("disasm", ""),
    "shader_source": lambda r: r.get("source", r.get("disasm", "")),
    "shader_reflect": lambda r: format_kv(r),
    "shader_constants": lambda r: format_kv(r),
    "log": lambda r: _fmt_log(r),
    "tex_info": lambda r: format_kv(r),
    "buf_info": lambda r: format_kv(r),
    "shader_list_info": lambda r: format_kv(r),
    "shader_list_disasm": lambda r: r.get("disasm", ""),
    "usage": lambda r: (
        "EID\tUSAGE\n" + "\n".join(f"{e['eid']}\t{e['usage']}" for e in r.get("entries", []))
    ),
    "counter_list": lambda r: (
        "ID\tNAME\tUNIT\tTYPE\tCATEGORY\n"
        + "\n".join(
            f"{c['id']}\t{c['name']}\t{c['unit']}\t{c['type']}\t{c['category']}"
            for c in r.get("counters", [])
        )
    ),
    "descriptors": lambda r: (
        "STAGE\tTYPE\tINDEX\tARRAY_EL\tRESOURCE\tFORMAT\tBYTE_SIZE\n"
        + "\n".join(
            f"{d['stage']}\t{d['type']}\t{d['index']}\t{d['array_element']}\t{d['resource_id']}\t{d['format']}\t{d['byte_size']}"
            for d in r.get("descriptors", [])
        )
    ),
    "pixel_history": lambda r: (
        "EID\tFRAG\tDEPTH\tPASSED\tFLAGS\n"
        + "\n".join(_fmt_pixel_mod(m) for m in r.get("modifications", []))
    ),
}


def _complete_vfs_path(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Shell completion callback for VFS paths."""
    if "/" in incomplete:
        last_slash = incomplete.rfind("/")
        dir_path = incomplete[: last_slash + 1].rstrip("/") or "/"
        prefix = incomplete[last_slash + 1 :]
    else:
        dir_path = "/"
        prefix = incomplete

    try:
        result = call("vfs_ls", {"path": dir_path})
    except SystemExit:
        return []

    base = dir_path if dir_path == "/" else dir_path + "/"
    items: list[CompletionItem] = []
    for child in result.get("children", []):
        name = child["name"]
        if name.startswith(prefix):
            suffix = "/" if child.get("kind") == "dir" else ""
            items.append(CompletionItem(base + name + suffix))
    return items


@click.command("ls")
@click.argument("path", default="/", shell_complete=_complete_vfs_path)
@click.option("-F", "--classify", is_flag=True, help="Append type indicator (/ * @)")
@click.option("-l", "--long", "use_long", is_flag=True, help="Long format (TSV with metadata)")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--no-header", is_flag=True, help="Omit TSV header (with -l)")
@click.option("--jsonl", "use_jsonl", is_flag=True, help="JSONL output (with -l)")
@click.option("-q", "--quiet", is_flag=True, help="Print name only (with -l)")
def ls_cmd(
    path: str,
    classify: bool,
    use_long: bool,
    use_json: bool,
    no_header: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """List VFS directory contents."""
    if classify and use_long:
        click.echo("error: -F and -l are mutually exclusive", err=True)
        raise SystemExit(1)

    params: dict[str, Any] = {"path": path}
    if use_long:
        params["long"] = True

    result = call("vfs_ls", params)
    if result.get("kind") != "dir":
        click.echo(f"error: {path}: Not a directory", err=True)
        raise SystemExit(1)

    children = result.get("children", [])

    if use_json:
        if use_long and result.get("long"):
            write_json(result)
        else:
            write_json(children)
        return

    if use_long and result.get("long"):
        if use_jsonl:
            write_jsonl(children)
        elif quiet:
            for child in children:
                sys.stdout.write(str(child.get("name", "")) + "\n")
        else:
            columns = result.get("columns", [])
            click.echo(render_ls_long(children, columns, no_header=no_header))
    else:
        click.echo(render_ls(children, classify=classify))


def _stdout_is_tty() -> bool:
    return sys.stdout.isatty()


def _deliver_binary(path: str, match: Any, raw: bool, output: str | None) -> None:
    """Handle binary leaf delivery: TTY protection, -o, or pipe."""
    if _stdout_is_tty() and not raw and output is None:
        click.echo(
            f"error: {path}: binary data, use redirect (>) or -o",
            err=True,
        )
        raise SystemExit(1)

    content_result = call(match.handler, match.args)
    temp_path = content_result.get("path")
    if temp_path is None:
        click.echo(f"error: {path}: handler did not return file path", err=True)
        raise SystemExit(1)

    session = _load_session()
    pid = getattr(session, "pid", 1) if session else 1

    if pid == 0:
        try:
            data = fetch_remote_file(temp_path)
            if output is not None:
                Path(output).write_bytes(data)
            else:
                sys.stdout.buffer.write(data)
        except OSError as exc:
            click.echo(f"error: {path}: {exc}", err=True)
            raise SystemExit(1) from None
        return

    temp = Path(temp_path)
    if not temp.exists():
        click.echo(f"error: {path}: temp file missing", err=True)
        raise SystemExit(1)

    try:
        if output is not None:
            shutil.move(str(temp), output)
        else:
            sys.stdout.buffer.write(temp.read_bytes())
            temp.unlink(missing_ok=True)
    except OSError as exc:
        click.echo(f"error: {path}: {exc}", err=True)
        raise SystemExit(1) from None


@click.command("cat")
@click.argument("path", shell_complete=_complete_vfs_path)
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--raw", is_flag=True, help="Force raw output even on TTY")
@click.option("-o", "--output", type=click.Path(), default=None, help="Write binary output to file")
def cat_cmd(path: str, use_json: bool, raw: bool, output: str | None) -> None:
    """Output VFS leaf node content."""
    result = call("vfs_ls", {"path": path})
    kind = result.get("kind")
    resolved_path = result.get("path", path)

    if kind == "dir":
        click.echo(f"error: {path}: Is a directory", err=True)
        raise SystemExit(1)
    if kind == "alias":
        click.echo(f"error: {path}: no event selected (use 'rdc goto' first)", err=True)
        raise SystemExit(1)

    match = resolve_path(resolved_path)
    if match is None or match.handler is None:
        click.echo(f"error: {path}: no content handler", err=True)
        raise SystemExit(1)

    if kind == "leaf_bin":
        _deliver_binary(path, match, raw, output)
        return

    content_result = call(match.handler, match.args)

    if use_json:
        write_json(content_result)
        return

    extractor = _EXTRACTORS.get(match.handler)
    if extractor:
        click.echo(extractor(content_result))
    else:
        click.echo(format_kv(content_result))


@click.command("tree")
@click.argument("path", default="/", shell_complete=_complete_vfs_path)
@click.option("--depth", default=2, type=click.IntRange(1, 8), show_default=True)
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def tree_cmd(path: str, depth: int, use_json: bool) -> None:
    """Display VFS subtree structure."""
    result = call("vfs_tree", {"path": path, "depth": depth})
    if use_json:
        write_json(result)
        return
    click.echo(render_tree_root(path, result["tree"], depth))


@click.command("_complete", hidden=True)
@click.argument("partial")
def complete_cmd(partial: str) -> None:
    """Tab completion helper (hidden command)."""
    if "/" in partial:
        last_slash = partial.rfind("/")
        dir_path = partial[: last_slash + 1].rstrip("/") or "/"
        prefix = partial[last_slash + 1 :]
    else:
        dir_path = "/"
        prefix = partial

    try:
        result = call("vfs_ls", {"path": dir_path})
    except SystemExit:
        return

    children = result.get("children", [])
    base = dir_path if dir_path == "/" else dir_path + "/"
    for child in children:
        name = child["name"]
        if name.startswith(prefix):
            suffix = "/" if child.get("kind") == "dir" else ""
            click.echo(base + name + suffix)
