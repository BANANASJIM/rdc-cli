"""Export convenience commands: texture, rt, buffer."""

from __future__ import annotations

from pathlib import Path

import click

from rdc.commands._helpers import call, complete_eid, fetch_remote_file
from rdc.commands.vfs import _deliver_binary
from rdc.session_state import load_session
from rdc.vfs.router import resolve_path


def _export_vfs_path(vfs_path: str, output: str | None, raw: bool) -> None:
    """Resolve a VFS path and deliver binary content."""
    result = call("vfs_ls", {"path": vfs_path})
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
@click.argument("eid", type=int, required=False, default=None, shell_complete=complete_eid)
@click.option("-o", "--output", type=click.Path(), default=None, help="Write to file")
@click.option("--target", default=0, type=int, help="Color target index (default 0)")
@click.option("--raw", is_flag=True, help="Force raw output even on TTY")
@click.option(
    "--overlay",
    type=click.Choice(
        [
            "wireframe",
            "depth",
            "stencil",
            "backface",
            "viewport",
            "nan",
            "clipping",
            "overdraw",
            "triangle-size",
        ]
    ),
    default=None,
    help="Render with debug overlay",
)
@click.option("--width", type=int, default=256, help="Overlay render width")
@click.option("--height", type=int, default=256, help="Overlay render height")
def rt_cmd(
    eid: int | None,
    output: str | None,
    target: int,
    raw: bool,
    overlay: str | None,
    width: int,
    height: int,
) -> None:
    """Export render target as PNG."""
    if overlay:
        params: dict[str, object] = {"overlay": overlay, "width": width, "height": height}
        if eid is not None:
            params["eid"] = eid
        result = call("rt_overlay", params)
        src_path = result["path"]
        if output:
            data = fetch_remote_file(src_path)
            Path(output).write_bytes(data)
            click.echo(
                f"overlay: {result['overlay']} {result['size']} bytes -> {output}",
                err=True,
            )
        else:
            session = load_session()
            pid = getattr(session, "pid", 1) if session else 1
            if pid == 0:
                click.echo(
                    "error: --output is required when connected to a remote daemon",
                    err=True,
                )
                raise SystemExit(1)
            click.echo(src_path)
        return

    if eid is None:
        raise click.UsageError("EID is required when --overlay is not used")
    _export_vfs_path(f"/draws/{eid}/targets/color{target}.png", output, raw)


@click.command("buffer")
@click.argument("id", type=int)
@click.option("-o", "--output", type=click.Path(), default=None, help="Write to file")
@click.option("--raw", is_flag=True, help="Force raw output even on TTY")
def buffer_cmd(id: int, output: str | None, raw: bool) -> None:
    """Export buffer raw data."""
    _export_vfs_path(f"/buffers/{id}/data", output, raw)
