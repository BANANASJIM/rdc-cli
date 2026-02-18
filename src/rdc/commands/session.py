from __future__ import annotations

import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import click

from rdc.daemon_client import send_request
from rdc.protocol import goto_request, ping_request, shutdown_request, status_request
from rdc.session_state import (
    create_session,
    delete_session,
    is_pid_alive,
    load_session,
    save_session,
    session_path,
)


def _pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_daemon(capture: str, port: int, token: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "rdc.daemon_server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--capture",
            capture,
            "--token",
            token,
            "--idle-timeout",
            "1800",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _wait_for_ping(host: str, port: int, token: str, timeout_s: float = 2.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            resp = send_request(host, port, ping_request(token, request_id=1), timeout=0.5)
            if resp.get("result", {}).get("ok") is True:
                return True
        except Exception:  # noqa: BLE001
            time.sleep(0.05)
    return False


@click.command("open")
@click.argument("capture", type=click.Path(path_type=Path))
def open_cmd(capture: Path) -> None:
    """Create local default session and start daemon skeleton."""
    existing = load_session()
    if existing is not None:
        if is_pid_alive(existing.pid):
            click.echo("error: active session exists, run `rdc close` first", err=True)
            raise SystemExit(1)
        delete_session()

    host = "127.0.0.1"
    port = _pick_port()
    token = secrets.token_hex(16)
    proc = _start_daemon(str(capture), port, token)

    if not _wait_for_ping(host, port, token):
        proc.kill()
        click.echo("error: daemon failed to start", err=True)
        raise SystemExit(1)

    state = create_session(
        capture=str(capture),
        host=host,
        port=port,
        token=token,
        pid=proc.pid,
    )
    click.echo(f"opened: {state.capture}")
    click.echo(f"session: {session_path()}")


@click.command("status")
def status_cmd() -> None:
    """Show current daemon-backed session status."""
    state = load_session()
    if state is None:
        click.echo("error: no active session", err=True)
        raise SystemExit(1)

    if not is_pid_alive(state.pid):
        delete_session()
        click.echo("error: stale session detected and cleaned", err=True)
        raise SystemExit(1)

    try:
        resp = send_request(
            state.host,
            state.port,
            status_request(state.token, request_id=2),
        )
    except Exception as exc:  # noqa: BLE001
        click.echo(f"error: daemon unreachable: {exc}", err=True)
        raise SystemExit(1) from exc

    if "error" in resp:
        click.echo(f"error: {resp['error']['message']}", err=True)
        raise SystemExit(1)

    current_eid = int(resp["result"]["current_eid"])
    state.current_eid = current_eid
    save_session(state)

    click.echo(f"capture: {state.capture}")
    click.echo(f"current_eid: {state.current_eid}")
    click.echo(f"opened_at: {state.opened_at}")
    click.echo(f"daemon: {state.host}:{state.port} pid={state.pid}")


@click.command("goto")
@click.argument("eid", type=int)
def goto_cmd(eid: int) -> None:
    """Update current event id via daemon."""
    if eid < 0:
        click.echo("error: eid must be >= 0", err=True)
        raise SystemExit(1)

    state = load_session()
    if state is None:
        click.echo("error: no active session", err=True)
        raise SystemExit(1)

    if not is_pid_alive(state.pid):
        delete_session()
        click.echo("error: stale session detected and cleaned", err=True)
        raise SystemExit(1)

    try:
        resp = send_request(
            state.host,
            state.port,
            goto_request(state.token, eid, request_id=3),
        )
    except Exception as exc:  # noqa: BLE001
        click.echo(f"error: daemon unreachable: {exc}", err=True)
        raise SystemExit(1) from exc

    if "error" in resp:
        click.echo(f"error: {resp['error']['message']}", err=True)
        raise SystemExit(1)

    state.current_eid = int(resp["result"]["current_eid"])
    save_session(state)
    click.echo(f"current_eid set to {state.current_eid}")


@click.command("close")
def close_cmd() -> None:
    """Close daemon-backed session."""
    state = load_session()
    if state is None:
        click.echo("error: no active session", err=True)
        raise SystemExit(1)

    if not is_pid_alive(state.pid):
        delete_session()
        click.echo("stale session cleaned", err=True)
        raise SystemExit(1)

    try:
        send_request(
            state.host,
            state.port,
            shutdown_request(state.token, request_id=4),
        )
    except Exception:
        pass

    removed = delete_session()
    if not removed:
        click.echo("error: no active session", err=True)
        raise SystemExit(1)
    click.echo("session closed")
