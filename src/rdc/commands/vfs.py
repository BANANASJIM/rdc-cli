"""VFS commands: ls, cat, tree, _complete."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from rdc.commands.info import _daemon_call
from rdc.formatters.json_fmt import write_json
from rdc.vfs.formatter import render_ls, render_tree_root
from rdc.vfs.router import resolve_path


def _kv_text(data: dict[str, Any]) -> str:
    if not isinstance(data, dict) or not data:
        return str(data)
    max_key = max(len(str(k)) for k in data)
    lines: list[str] = []
    for k, v in data.items():
        if v is None or v == "":
            v = "-"
        label = str(k) + ":"
        lines.append(f"{label:<{max_key + 2}}{v}")
    return "\n".join(lines)


def _fmt_log(data: dict[str, Any]) -> str:
    messages = data.get("messages", [])
    lines = ["LEVEL\tEID\tMESSAGE"]
    for m in messages:
        msg = str(m.get("message", "-")).replace("\t", " ").replace("\n", " ")
        lines.append(f"{m.get('level', '-')}\t{m.get('eid', 0)}\t{msg}")
    return "\n".join(lines)


_EXTRACTORS: dict[str, Callable[..., str]] = {
    "info": lambda r: _kv_text(r),
    "stats": lambda r: _kv_text(r),
    "event": lambda r: _kv_text(r),
    "pass": lambda r: _kv_text(r),
    "resource": lambda r: _kv_text(r.get("resource", r)),
    "pipeline": lambda r: _kv_text(r.get("row", r)),
    "shader_disasm": lambda r: r.get("disasm", ""),
    "shader_source": lambda r: r.get("source", r.get("disasm", "")),
    "shader_reflect": lambda r: _kv_text(r),
    "shader_constants": lambda r: _kv_text(r),
    "log": lambda r: _fmt_log(r),
    "tex_info": lambda r: _kv_text(r),
    "buf_info": lambda r: _kv_text(r),
    "shader_list_info": lambda r: _kv_text(r),
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
}


@click.command("ls")
@click.argument("path", default="/")
@click.option("-F", "--classify", is_flag=True, help="Append type indicator (/ * @)")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def ls_cmd(path: str, classify: bool, use_json: bool) -> None:
    """List VFS directory contents."""
    result = _daemon_call("vfs_ls", {"path": path})
    if result.get("kind") != "dir":
        click.echo(f"error: {path}: Not a directory", err=True)
        raise SystemExit(1)

    children = result.get("children", [])
    if use_json:
        write_json(children)
        return
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

    content_result = _daemon_call(match.handler, match.args)
    temp_path = content_result.get("path")
    if temp_path is None:
        click.echo(f"error: {path}: handler did not return file path", err=True)
        raise SystemExit(1)

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
@click.argument("path")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--raw", is_flag=True, help="Force raw output even on TTY")
@click.option("-o", "--output", type=click.Path(), default=None, help="Write binary output to file")
def cat_cmd(path: str, use_json: bool, raw: bool, output: str | None) -> None:
    """Output VFS leaf node content."""
    result = _daemon_call("vfs_ls", {"path": path})
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

    content_result = _daemon_call(match.handler, match.args)

    if use_json:
        write_json(content_result)
        return

    extractor = _EXTRACTORS.get(match.handler)
    if extractor:
        click.echo(extractor(content_result))
    else:
        click.echo(_kv_text(content_result))


@click.command("tree")
@click.argument("path", default="/")
@click.option("--depth", default=2, type=click.IntRange(1, 8), show_default=True)
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def tree_cmd(path: str, depth: int, use_json: bool) -> None:
    """Display VFS subtree structure."""
    result = _daemon_call("vfs_tree", {"path": path, "depth": depth})
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
        result = _daemon_call("vfs_ls", {"path": dir_path})
    except SystemExit:
        return

    children = result.get("children", [])
    base = dir_path if dir_path == "/" else dir_path + "/"
    for child in children:
        name = child["name"]
        if name.startswith(prefix):
            suffix = "/" if child.get("kind") == "dir" else ""
            click.echo(base + name + suffix)
