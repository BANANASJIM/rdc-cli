"""Remote RenderDoc server commands: connect, list, capture."""

from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path
from typing import Any

import click

from rdc.discover import find_renderdoc
from rdc.remote_core import (
    build_conn_url,
    connect_remote_server,
    enumerate_remote_targets,
    parse_url,
    remote_capture,
    warn_if_public,
)
from rdc.remote_state import (
    RemoteServerState,
    load_latest_remote_state,
    save_remote_state,
)


def _require_renderdoc() -> Any:
    """Find and return the renderdoc module, or exit with error."""
    rd = find_renderdoc()
    if rd is None:
        click.echo("error: renderdoc module not found", err=True)
        raise SystemExit(1)
    return rd


def _resolve_url(url: str | None) -> tuple[str, int]:
    """Resolve host/port from --url flag or saved state."""
    if url:
        try:
            return parse_url(url)
        except ValueError as exc:
            click.echo(f"error: {exc}", err=True)
            raise SystemExit(1) from None
    state = load_latest_remote_state()
    if state is None:
        click.echo("error: no remote connection (run 'rdc remote connect' first)", err=True)
        raise SystemExit(1)
    return state.host, state.port


def _check_public_ip(host: str) -> None:
    """Emit warning to stderr if host appears to be a public IP."""
    warning = warn_if_public(host)
    if warning:
        click.echo(warning, err=True)


@click.group("remote")
def remote_group() -> None:
    """Remote RenderDoc server commands."""


@remote_group.command("connect")
@click.argument("url")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def remote_connect_cmd(url: str, as_json: bool) -> None:
    """Connect to a remote RenderDoc server."""
    try:
        host, port = parse_url(url)
    except ValueError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None
    _check_public_ip(host)
    rd = _require_renderdoc()

    conn_url = build_conn_url(host, port)
    try:
        remote = connect_remote_server(rd, conn_url)
    except RuntimeError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None

    try:
        remote.Ping()
        save_remote_state(RemoteServerState(host=host, port=port, connected_at=time.time()))
    finally:
        remote.ShutdownConnection()

    if as_json:
        click.echo(json.dumps({"host": host, "port": port}))
    else:
        click.echo(f"connected: {host}:{port}")


@remote_group.command("list")
@click.option("--url", default=None, help="Override saved remote (host:port).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def remote_list_cmd(url: str | None, as_json: bool) -> None:
    """List capturable applications on a remote host."""
    host, port = _resolve_url(url)
    _check_public_ip(host)
    rd = _require_renderdoc()

    conn_url = build_conn_url(host, port)
    idents = enumerate_remote_targets(rd, conn_url)

    targets: list[dict[str, Any]] = []
    for ident in idents:
        tc = rd.CreateTargetControl(conn_url, ident, "rdc-cli", False)
        if tc is None:
            targets.append({"ident": ident, "target": "unknown", "pid": 0, "api": "unknown"})
            continue
        try:
            targets.append(
                {
                    "ident": ident,
                    "target": tc.GetTarget(),
                    "pid": tc.GetPID(),
                    "api": tc.GetAPI(),
                }
            )
        finally:
            tc.Shutdown()

    if as_json:
        click.echo(json.dumps({"targets": targets}))
    else:
        if not targets:
            click.echo("no targets found")
        for t in targets:
            click.echo(f"ident={t['ident']}  target={t['target']}  pid={t['pid']}  api={t['api']}")


@remote_group.command("capture")
@click.argument("app")
@click.option(
    "-o", "--output", required=True, type=click.Path(path_type=Path), help="Local output path."
)
@click.option("--url", default=None, help="Override saved remote (host:port).")
@click.option("--args", "app_args", default="", help="Arguments for remote app.")
@click.option("--workdir", default="", help="Remote working directory.")
@click.option("--frame", type=int, default=None, help="Queue capture at frame N.")
@click.option("--timeout", type=float, default=60.0, help="Capture timeout in seconds.")
@click.option("--api-validation", is_flag=True, help="Enable API validation.")
@click.option("--callstacks", is_flag=True, help="Capture callstacks.")
@click.option("--hook-children", is_flag=True, help="Hook child processes.")
@click.option("--ref-all-resources", is_flag=True, help="Reference all resources.")
@click.option("--soft-memory-limit", type=int, default=None, help="Soft memory limit (MB).")
@click.option(
    "--keep-remote",
    is_flag=True,
    help="Skip transfer; print remote path for use with 'rdc open --remote'.",
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def remote_capture_cmd(
    app: str,
    output: Path,
    url: str | None,
    app_args: str,
    workdir: str,
    frame: int | None,
    timeout: float,
    api_validation: bool,
    callstacks: bool,
    hook_children: bool,
    ref_all_resources: bool,
    soft_memory_limit: int | None,
    keep_remote: bool,
    as_json: bool,
) -> None:
    """Capture on a remote host and transfer to local."""
    host, port = _resolve_url(url)
    _check_public_ip(host)
    rd = _require_renderdoc()

    opts: dict[str, Any] = {}
    if api_validation:
        opts["api_validation"] = True
    if callstacks:
        opts["callstacks"] = True
    if hook_children:
        opts["hook_children"] = True
    if ref_all_resources:
        opts["ref_all_resources"] = True
    if soft_memory_limit is not None:
        opts["soft_memory_limit"] = soft_memory_limit

    conn_url = build_conn_url(host, port)
    try:
        remote = connect_remote_server(rd, conn_url)
    except RuntimeError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None

    try:
        result = remote_capture(
            rd,
            remote,
            conn_url,
            app,
            args=app_args,
            workdir=workdir,
            output=str(output),
            opts=opts,
            frame=frame,
            timeout=timeout,
            keep_remote=keep_remote,
        )
    finally:
        remote.ShutdownConnection()

    if as_json:
        click.echo(json.dumps(dataclasses.asdict(result)))
        if not result.success:
            raise SystemExit(1)
        return

    if not result.success:
        click.echo(f"error: {result.error}", err=True)
        raise SystemExit(1)

    if result.remote_path:
        click.echo(result.remote_path)
        host_str = f"{host}:{port}"
        click.echo(f"next: rdc open --remote {host_str} {result.remote_path}", err=True)
    else:
        click.echo(result.path)
        click.echo(f"next: rdc open {result.path}", err=True)
