"""Remote RenderDoc server commands: connect, list, capture, setup, status, disconnect."""

from __future__ import annotations

import dataclasses
import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from rdc.capture_core import CaptureResult, capture_result_from_dict
from rdc.commands._helpers import (
    call,
    require_renderdoc,
    split_session_active,
    write_capture_to_path,
)
from rdc.remote_core import (
    build_conn_url,
    connect_remote_server,
    enumerate_remote_targets,
    is_protocol_url,
    parse_url,
    remote_capture,
    warn_if_public,
)
from rdc.remote_state import (
    RemoteServerState,
    delete_remote_state,
    load_latest_remote_state,
    save_remote_state,
)


def _resolve_url(url: str | None) -> tuple[str, int]:
    """Resolve host/port from --url flag or saved state."""
    if url:
        if is_protocol_url(url):
            return url, 0
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


def _ensure_remote_reachable(host: str, port: int) -> None:
    """Validate that a remote host is reachable before listing targets."""
    if split_session_active():
        call("remote_connect_run", {"host": host, "port": port})
        return

    rd = require_renderdoc()
    conn_url = host if is_protocol_url(host) else build_conn_url(host, port)
    try:
        remote = connect_remote_server(rd, conn_url)
    except RuntimeError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None
    try:
        remote.Ping()
    except Exception as exc:  # noqa: BLE001
        click.echo(f"error: connection failed: {exc}", err=True)
        raise SystemExit(1) from None
    finally:
        remote.ShutdownConnection()


@click.group("remote")
def remote_group() -> None:
    """Remote RenderDoc server commands."""


@remote_group.command("connect")
@click.argument("url")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def remote_connect_cmd(url: str, use_json: bool) -> None:
    """Connect to a remote RenderDoc server."""
    try:
        host, port = parse_url(url)
    except ValueError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None
    _check_public_ip(host)
    conn_url = build_conn_url(host, port)

    if split_session_active():
        call("remote_connect_run", {"host": host, "port": port})
    else:
        rd = require_renderdoc()
        try:
            remote = connect_remote_server(rd, conn_url)
        except RuntimeError as exc:
            click.echo(f"error: {exc}", err=True)
            raise SystemExit(1) from None
        try:
            remote.Ping()
        finally:
            remote.ShutdownConnection()

    save_remote_state(RemoteServerState(host=host, port=port, connected_at=time.time()))

    if use_json:
        click.echo(json.dumps({"host": host, "port": port}))
    else:
        click.echo(f"connected: {host}:{port}")


@remote_group.command("list")
@click.option("--url", default=None, help="Override saved remote (host:port).")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def remote_list_cmd(url: str | None, use_json: bool) -> None:
    """List capturable applications on a remote host."""
    host, port = _resolve_url(url)
    if not is_protocol_url(host):
        _check_public_ip(host)
    conn_url = host if is_protocol_url(host) else build_conn_url(host, port)

    if split_session_active():
        _ensure_remote_reachable(host, port)
        rpc_result = call("remote_list_run", {"host": host, "port": port})
        targets = list(rpc_result.get("targets", []))
    else:
        rd = require_renderdoc()
        idents = enumerate_remote_targets(rd, conn_url)
        if not idents:
            _ensure_remote_reachable(host, port)
        targets = []
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

    if use_json:
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
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
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
    use_json: bool,
) -> None:
    """Capture on a remote host and transfer to local."""
    host, port = _resolve_url(url)
    if not is_protocol_url(host):
        _check_public_ip(host)

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

    if split_session_active():
        payload = {
            "host": host,
            "port": port,
            "app": app,
            "args": app_args,
            "workdir": workdir,
            "output": str(output),
            "opts": opts,
            "frame": frame,
            "timeout": timeout,
            "keep_remote": keep_remote,
        }
        result_dict = call("remote_capture_run", payload)
        result = capture_result_from_dict(result_dict)
        if not keep_remote:
            result = _download_split_remote_capture(result, output)
    else:
        rd = require_renderdoc()
        conn_url = host if is_protocol_url(host) else build_conn_url(host, port)
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

    if use_json:
        click.echo(json.dumps(dataclasses.asdict(result)))
        if not result.success:
            raise SystemExit(1)
        return

    if not result.success:
        click.echo(f"error: {result.error}", err=True)
        raise SystemExit(1)

    if result.remote_path:
        click.echo(result.remote_path)
        rmt = host if is_protocol_url(host) else build_conn_url(host, port)
        click.echo(f"next: rdc open --remote {rmt} {result.remote_path}", err=True)
    else:
        click.echo(result.path)
        click.echo(f"next: rdc open {result.path}", err=True)


def _download_split_remote_capture(result: CaptureResult, output: Path) -> CaptureResult:
    if not result.success or not result.path:
        return result
    return write_capture_to_path(result, output)


def _tcp_probe(host: str, port: int, timeout_s: float) -> str | None:
    """Probe TCP reachability. Returns None on success or a failure literal."""
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return None
    except ConnectionRefusedError:
        return "refused"
    except TimeoutError:
        return "timeout"
    except OSError:
        return "unreachable"


def _setup_hint_for(failure: str, host: str, port: int, timeout_s: float = 10.0) -> str:
    """Map a failure literal to an actionable hint string."""
    if failure == "refused":
        return (
            f"rdc serve does not appear to be running on {host}:{port}. "
            f"On the target, run: rdc serve --daemon --port {port}"
        )
    if failure == "timeout":
        return (
            f"cannot reach {host}:{port} within {timeout_s:g}s -- "
            "check network path, firewall, or docker port mapping"
        )
    if failure == "unreachable":
        return f"cannot resolve or reach {host} -- check hostname and network route"
    if failure == "ping_failed":
        return (
            f"TCP reachable but renderdoc handshake failed -- the process listening on "
            f"{host}:{port} may not be renderdoccmd remoteserver, or versions differ. "
            f"Run 'rdc doctor' locally and compare with 'rdc --version' on {host}"
        )
    return f"unknown failure class: {failure}"


def _emit_setup_failure(
    host: str,
    port: int,
    failure: str,
    detail: str,
    timeout_s: float,
    use_json: bool,
) -> None:
    hint = _setup_hint_for(failure, host, port, timeout_s)
    if use_json:
        click.echo(
            json.dumps(
                {
                    "host": host,
                    "port": port,
                    "error": detail,
                    "failure": failure,
                    "hint": hint,
                }
            ),
            err=True,
        )
    else:
        click.echo(f"error: {detail}", err=True)
        click.echo(f"hint: {hint}", err=True)
    raise SystemExit(1)


def _renderdoc_handshake(host: str, port: int) -> None:
    """Perform CreateRemoteServerConnection + Ping + Shutdown. Raises RuntimeError on failure."""
    rd = require_renderdoc()
    conn_url = build_conn_url(host, port)
    remote = connect_remote_server(rd, conn_url)
    try:
        remote.Ping()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(str(exc)) from exc
    finally:
        remote.ShutdownConnection()


@remote_group.command("setup")
@click.argument("url")
@click.option(
    "--timeout", "timeout_s", type=float, default=10.0, help="TCP probe timeout in seconds."
)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def remote_setup_cmd(url: str, timeout_s: float, use_json: bool) -> None:
    """Verify a remote server is reachable, handshake, and save state."""
    try:
        host, port = parse_url(url)
    except ValueError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None
    _check_public_ip(host)

    failure = _tcp_probe(host, port, timeout_s)
    if failure is not None:
        detail_map = {
            "refused": f"cannot reach {host}:{port} (connection refused)",
            "timeout": f"cannot reach {host}:{port} (timeout after {timeout_s:g}s)",
            "unreachable": f"cannot reach {host} (network unreachable)",
        }
        _emit_setup_failure(host, port, failure, detail_map[failure], timeout_s, use_json)

    try:
        _renderdoc_handshake(host, port)
    except RuntimeError as exc:
        _emit_setup_failure(
            host,
            port,
            "ping_failed",
            f"TCP reachable but renderdoc handshake failed: {exc}",
            timeout_s,
            use_json,
        )

    save_remote_state(RemoteServerState(host=host, port=port, connected_at=time.time()))

    if use_json:
        click.echo(json.dumps({"host": host, "port": port, "next": "rdc remote list"}))
    else:
        click.echo(f"connected: {host}:{port}")
        click.echo("next: rdc remote list", err=True)


def _format_age(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m}m"
    if m:
        return f"{m}m{sec}s"
    return f"{sec}s"


@remote_group.command("status")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def remote_status_cmd(use_json: bool) -> None:
    """Show the currently saved remote server state."""
    state = load_latest_remote_state()
    if state is None:
        if use_json:
            click.echo(json.dumps({"state": None}))
        else:
            click.echo("no saved remote state", err=True)
            click.echo(
                "hint: run 'rdc remote setup HOST[:PORT]' "
                "or 'rdc remote connect HOST[:PORT]' first",
                err=True,
            )
        return

    saved_at_iso = datetime.fromtimestamp(state.connected_at, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    age = _format_age(time.time() - state.connected_at)
    if use_json:
        click.echo(
            json.dumps(
                {
                    "host": state.host,
                    "port": state.port,
                    "saved_at": saved_at_iso,
                    "age": age,
                }
            )
        )
    else:
        click.echo(f"host: {state.host}")
        click.echo(f"port: {state.port}")
        click.echo(f"saved_at: {saved_at_iso}")
        click.echo(f"age: {age}")


@remote_group.command("disconnect")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def remote_disconnect_cmd(use_json: bool) -> None:
    """Delete the saved remote server state (local only)."""
    state = load_latest_remote_state()
    if state is None:
        if use_json:
            click.echo(json.dumps({"disconnected": None}))
        else:
            click.echo("nothing to disconnect", err=True)
        return
    delete_remote_state(state.host, state.port)
    label = f"{state.host}:{state.port}"
    if use_json:
        click.echo(json.dumps({"disconnected": label}))
    else:
        click.echo(f"disconnected: {label}")
