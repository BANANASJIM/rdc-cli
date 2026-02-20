"""Export convenience commands: texture, rt, buffer."""

from __future__ import annotations

import click

from rdc.commands.info import _daemon_call
from rdc.commands.vfs import _deliver_binary
from rdc.vfs.router import resolve_path


def _export_vfs_path(vfs_path: str, output: str | None, raw: bool) -> None:
    """Resolve a VFS path and deliver binary content."""
    result = _daemon_call("vfs_ls", {"path": vfs_path})
    kind = result.get("kind")

    if kind != "leaf_bin":
        click.echo(f"error: {vfs_path}: not a binary node", err=True)
        raise SystemExit(1)

    resolved = result.get("path", vfs_path)
    match = resolve_path(resolved)
    if match is None or match.handler is None:
        click.echo(f"error: {vfs_path}: no content handler", err=True)
        raise SystemExit(1)

    _deliver_binary(vfs_path, match, raw, output)


@click.command("texture")
@click.argument("id", type=int)
@click.option("-o", "--output", type=click.Path(), default=None, help="Write to file")
@click.option("--mip", default=0, type=int, help="Mip level (default 0)")
@click.option("--raw", is_flag=True, help="Force raw output even on TTY")
def texture_cmd(id: int, output: str | None, mip: int, raw: bool) -> None:
    """Export texture as PNG."""
    vfs_path = f"/textures/{id}/mips/{mip}.png" if mip > 0 else f"/textures/{id}/image.png"
    _export_vfs_path(vfs_path, output, raw)


@click.command("rt")
@click.argument("eid", type=int)
@click.option("-o", "--output", type=click.Path(), default=None, help="Write to file")
@click.option("--target", default=0, type=int, help="Color target index (default 0)")
@click.option("--raw", is_flag=True, help="Force raw output even on TTY")
def rt_cmd(eid: int, output: str | None, target: int, raw: bool) -> None:
    """Export render target as PNG."""
    _export_vfs_path(f"/draws/{eid}/targets/color{target}.png", output, raw)


@click.command("buffer")
@click.argument("id", type=int)
@click.option("-o", "--output", type=click.Path(), default=None, help="Write to file")
@click.option("--raw", is_flag=True, help="Force raw output even on TTY")
def buffer_cmd(id: int, output: str | None, raw: bool) -> None:
    """Export buffer raw data."""
    _export_vfs_path(f"/buffers/{id}/data", output, raw)
