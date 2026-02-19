from __future__ import annotations

import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from rdc.daemon_client import send_request
from rdc.protocol import goto_request, ping_request, shutdown_request, status_request
from rdc.session_state import (
    SessionState,
    create_session,
    delete_session,
    is_pid_alive,
    load_session,
    save_session,
)


def pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _renderdoc_available() -> bool:
    """Check if renderdoc module can be imported."""
    from rdc.discover import find_renderdoc

    return find_renderdoc() is not None


def start_daemon(capture: str, port: int, token: str) -> subprocess.Popen[str]:
    cmd = [
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
    ]
    if not _renderdoc_available():
        cmd.append("--no-replay")
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def wait_for_ping(host: str, port: int, token: str, timeout_s: float = 2.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            resp = send_request(host, port, ping_request(token, request_id=1), timeout=0.5)
            if resp.get("result", {}).get("ok") is True:
                return True
        except Exception:  # noqa: BLE001
            time.sleep(0.05)
    return False


def open_session(capture: Path) -> tuple[bool, str]:
    existing = load_session()
    if existing is not None:
        if is_pid_alive(existing.pid):
            return False, "error: active session exists, run `rdc close` first"
        delete_session()

    host = "127.0.0.1"
    port = pick_port()
    token = secrets.token_hex(16)
    proc = start_daemon(str(capture), port, token)

    if not wait_for_ping(host, port, token):
        proc.kill()
        return False, "error: daemon failed to start"

    create_session(
        capture=str(capture),
        host=host,
        port=port,
        token=token,
        pid=proc.pid,
    )
    return True, f"opened: {capture}"


def _load_live_session() -> tuple[SessionState | None, str | None]:
    state = load_session()
    if state is None:
        return None, "error: no active session"
    if not is_pid_alive(state.pid):
        delete_session()
        return None, "error: stale session detected and cleaned"
    return state, None


def status_session() -> tuple[bool, dict[str, Any] | str]:
    state, err = _load_live_session()
    if err:
        return False, err
    assert state is not None

    try:
        resp = send_request(state.host, state.port, status_request(state.token, request_id=2))
    except Exception as exc:  # noqa: BLE001
        return False, f"error: daemon unreachable: {exc}"

    if "error" in resp:
        return False, f"error: {resp['error']['message']}"

    state.current_eid = int(resp["result"]["current_eid"])
    save_session(state)

    return True, {
        "capture": state.capture,
        "current_eid": state.current_eid,
        "opened_at": state.opened_at,
        "daemon": f"{state.host}:{state.port} pid={state.pid}",
    }


def goto_session(eid: int) -> tuple[bool, str]:
    if eid < 0:
        return False, "error: eid must be >= 0"

    state, err = _load_live_session()
    if err:
        return False, err
    assert state is not None

    try:
        resp = send_request(state.host, state.port, goto_request(state.token, eid, request_id=3))
    except Exception as exc:  # noqa: BLE001
        return False, f"error: daemon unreachable: {exc}"

    if "error" in resp:
        return False, f"error: {resp['error']['message']}"

    state.current_eid = int(resp["result"]["current_eid"])
    save_session(state)
    return True, f"current_eid set to {state.current_eid}"


def close_session() -> tuple[bool, str]:
    state = load_session()
    if state is None:
        return False, "error: no active session"

    if not is_pid_alive(state.pid):
        delete_session()
        return False, "stale session cleaned"

    try:
        send_request(state.host, state.port, shutdown_request(state.token, request_id=4))
    except Exception:
        pass

    removed = delete_session()
    if not removed:
        return False, "error: no active session"
    return True, "session closed"
