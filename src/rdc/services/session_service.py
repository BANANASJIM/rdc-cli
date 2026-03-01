from __future__ import annotations

import logging
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from rdc import _platform
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

logger = logging.getLogger(__name__)


def pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _renderdoc_available() -> bool:
    """Check if renderdoc module can be imported."""
    from rdc.discover import find_renderdoc

    return find_renderdoc() is not None


def start_daemon(
    capture: str,
    port: int,
    token: str,
    *,
    host: str = "127.0.0.1",
    idle_timeout: int = 1800,
    remote_url: str | None = None,
) -> subprocess.Popen[str]:
    cmd = [
        sys.executable,
        "-m",
        "rdc.daemon_server",
        "--host",
        host,
        "--port",
        str(port),
        "--capture",
        capture,
        "--token",
        token,
        "--idle-timeout",
        str(idle_timeout),
    ]
    if remote_url:
        cmd += ["--remote-url", remote_url]
    elif not _renderdoc_available():
        cmd.append("--no-replay")
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        **_platform.popen_flags(),
    )


def wait_for_ping(
    host: str,
    port: int,
    token: str,
    timeout_s: float = 15.0,
    proc: subprocess.Popen[str] | None = None,
) -> tuple[bool, str]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            return False, f"process exited: exit code {proc.returncode}"
        try:
            resp = send_request(host, port, ping_request(token, request_id=1), timeout=0.5)
            if resp.get("result", {}).get("ok") is True:
                return True, ""
        except Exception:  # noqa: BLE001
            time.sleep(0.05)
    return False, f"timeout ({timeout_s}s)"


def _check_existing_session() -> tuple[bool, str | None]:
    """Check if an active session exists.

    Returns:
        (exists, error_msg) — True + message if a live session blocks new open.
    """
    existing = load_session()
    if existing is None:
        return False, None
    if existing.pid > 0 and is_pid_alive(existing.pid):
        return True, "error: active session exists, run `rdc close` first"
    if existing.pid <= 0:
        try:
            resp = send_request(
                existing.host,
                existing.port,
                ping_request(existing.token, request_id=1),
                timeout=1.0,
            )
            if resp.get("result", {}).get("ok") is True:
                return True, "error: active session exists, run `rdc close` first"
        except Exception:  # noqa: BLE001
            pass
    delete_session()
    return False, None


def open_session(
    capture: str | Path,
    *,
    remote_url: str | None = None,
) -> tuple[bool, str]:
    exists, err = _check_existing_session()
    if exists:
        return False, err or "error: active session exists"

    host = "127.0.0.1"
    detail = "unknown error"
    for _attempt in range(3):
        port = pick_port()
        token = secrets.token_hex(16)
        proc = start_daemon(str(capture), port, token, remote_url=remote_url)

        ok, detail = wait_for_ping(host, port, token, proc=proc)
        if ok:
            break
        proc.kill()
        try:
            _, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stderr = ""
        if stderr and stderr.strip():
            detail = stderr.strip()
    else:
        return False, f"error: daemon failed to start ({detail})"

    create_session(
        capture=str(capture),
        host=host,
        port=port,
        token=token,
        pid=proc.pid,
    )
    msg = f"opened: {capture}"
    if remote_url:
        msg += f" (remote: {remote_url})"
    elif not _renderdoc_available():
        msg += " (no-replay mode: renderdoc unavailable)"
    return True, msg


def _load_live_session() -> tuple[SessionState | None, str | None]:
    state = load_session()
    if state is None:
        return None, "error: no active session"
    if state.pid <= 0:
        try:
            resp = send_request(
                state.host,
                state.port,
                ping_request(state.token, request_id=1),
                timeout=1.0,
            )
            if resp.get("result", {}).get("ok") is True:
                return state, None
        except Exception:  # noqa: BLE001
            pass
        delete_session()
        return None, "error: stale session detected and cleaned"
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

    result: dict[str, Any] = {
        "capture": state.capture,
        "current_eid": state.current_eid,
        "opened_at": state.opened_at,
        "daemon": f"{state.host}:{state.port} pid={state.pid}",
    }
    daemon_result = resp.get("result", {})
    if "remote" in daemon_result:
        result["remote"] = daemon_result["remote"]
    return True, result


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


def close_session(*, force_shutdown: bool = False) -> tuple[bool, str]:
    state = load_session()
    if state is None:
        return False, "error: no active session"

    if state.pid <= 0:
        if force_shutdown:
            try:
                send_request(
                    state.host,
                    state.port,
                    shutdown_request(state.token, request_id=4),
                )
            except Exception:  # noqa: BLE001
                pass
        delete_session()
        return True, "session closed"

    if not is_pid_alive(state.pid):
        delete_session()
        return False, "stale session cleaned"

    try:
        send_request(state.host, state.port, shutdown_request(state.token, request_id=4))
    except Exception:
        logger.debug("shutdown request failed, terminating", exc_info=True)
        _platform.terminate_process(state.pid)

    removed = delete_session()
    if not removed:
        return False, "error: no active session"
    return True, "session closed"


def connect_session(
    host: str,
    port: int,
    token: str,
) -> tuple[bool, str]:
    """Connect to an already-running external daemon.

    Args:
        host: Remote daemon host.
        port: Remote daemon port.
        token: Authentication token.

    Returns:
        (ok, message) tuple.
    """
    exists, err = _check_existing_session()
    if exists:
        return False, err or "error: active session exists"

    try:
        resp = send_request(host, port, status_request(token, request_id=1), timeout=5.0)
    except Exception as exc:  # noqa: BLE001
        return False, f"error: cannot reach daemon at {host}:{port}: {exc}"

    if "error" in resp:
        return False, f"error: {resp['error']['message']}"

    capture = resp.get("result", {}).get("capture", "unknown")
    create_session(capture=capture, host=host, port=port, token=token, pid=0)
    return True, f"connected: {capture} at {host}:{port}"


def _parse_listen_addr(addr: str) -> tuple[str, int]:
    """Parse a listen address string into (host, port).

    Formats: "" -> ("0.0.0.0", auto), "ADDR" -> (ADDR, auto),
             "ADDR:PORT" -> (ADDR, PORT), ":PORT" -> ("0.0.0.0", PORT).
    Port 0 is treated as auto (calls pick_port).
    """
    if not addr:
        return "0.0.0.0", pick_port()
    if ":" in addr:
        host_part, port_str = addr.rsplit(":", 1)
        bind_host = host_part or "0.0.0.0"
        try:
            port = int(port_str)
        except ValueError:
            raise ValueError(f"invalid port: {port_str!r}") from None
        if port != 0 and not 1 <= port <= 65535:
            raise ValueError(f"port out of range: {port} (must be 0 or 1-65535)")
        return bind_host, port if port != 0 else pick_port()
    return addr, pick_port()


def listen_open_session(
    capture: str,
    listen_addr: str,
    *,
    remote_url: str | None = None,
) -> tuple[bool, dict[str, Any] | str]:
    """Open a session with the daemon listening on a specified address.

    Args:
        capture: Path to capture file.
        listen_addr: Bind address string (see _parse_listen_addr).
        remote_url: Optional remote replay URL.

    Returns:
        (ok, info_dict_or_error) tuple.
    """
    exists, err = _check_existing_session()
    if exists:
        return False, err or "error: active session exists"

    bind_host, bind_port = _parse_listen_addr(listen_addr)
    connect_host = "127.0.0.1" if bind_host == "0.0.0.0" else bind_host
    token = secrets.token_hex(16)
    proc = start_daemon(
        capture,
        bind_port,
        token,
        host=bind_host,
        remote_url=remote_url,
    )

    ok, detail = wait_for_ping(connect_host, bind_port, token, proc=proc)
    if not ok:
        proc.kill()
        try:
            _, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stderr = ""
        if stderr and stderr.strip():
            detail = stderr.strip()
        return False, f"error: daemon failed to start ({detail})"

    create_session(
        capture=capture,
        host=connect_host,
        port=bind_port,
        token=token,
        pid=proc.pid,
    )
    return True, {
        "host": bind_host,
        "port": bind_port,
        "token": token,
        "capture": capture,
    }
