from __future__ import annotations

import secrets
import socket
import subprocess
import sys
import time

from rdc.daemon_client import send_request
from rdc.protocol import goto_request, ping_request, shutdown_request, status_request


def _pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_daemon(
    port: int, token: str, *, idle_timeout: int | None = None
) -> subprocess.Popen[bytes]:
    cmd = [
        sys.executable,
        "-m",
        "rdc.daemon_server",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--capture",
        "capture.rdc",
        "--token",
        token,
        "--no-replay",
    ]
    if idle_timeout is not None:
        cmd += ["--idle-timeout", str(idle_timeout)]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_ready(port: int, token: str, timeout_s: float = 2.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            response = send_request("127.0.0.1", port, ping_request(token, 1), timeout=0.2)
            if response.get("result", {}).get("ok"):
                return
        except Exception:  # noqa: BLE001
            time.sleep(0.05)
    raise AssertionError("daemon did not become ready")


def test_daemon_status_goto_and_shutdown() -> None:
    port = _pick_port()
    token = secrets.token_hex(8)
    proc = _start_daemon(port, token)

    try:
        _wait_ready(port, token)

        status = send_request("127.0.0.1", port, status_request(token, 2))
        assert status["result"]["current_eid"] == 0

        goto = send_request("127.0.0.1", port, goto_request(token, 77, 3))
        assert goto["result"]["current_eid"] == 77

        status2 = send_request("127.0.0.1", port, status_request(token, 4))
        assert status2["result"]["current_eid"] == 77

        send_request("127.0.0.1", port, shutdown_request(token, 5))
    finally:
        proc.terminate()


def test_daemon_idle_timeout_exits() -> None:
    port = _pick_port()
    token = secrets.token_hex(8)
    proc = _start_daemon(port, token, idle_timeout=1)

    _wait_ready(port, token)
    proc.wait(timeout=3)
    assert proc.returncode == 0


def test_daemon_rejects_invalid_token() -> None:
    port = _pick_port()
    token = secrets.token_hex(8)
    proc = _start_daemon(port, token)

    try:
        _wait_ready(port, token)
        bad = send_request("127.0.0.1", port, status_request("bad-token", 6))
        assert bad["error"]["code"] == -32600
    finally:
        proc.terminate()
