from __future__ import annotations

import secrets
import socket
import subprocess
import sys
import time
from unittest.mock import MagicMock

import pytest

from rdc._transport import recv_line
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


# ---------------------------------------------------------------------------
# recv_line unit tests
# ---------------------------------------------------------------------------


def test_recv_line_exceeds_max_bytes() -> None:
    mock_sock = MagicMock()
    mock_sock.recv.return_value = b"A" * 4096
    with pytest.raises(ValueError, match="max_bytes"):
        recv_line(mock_sock, max_bytes=100)


def test_recv_line_within_limit() -> None:
    mock_sock = MagicMock()
    mock_sock.recv.return_value = b'{"ok": true}\n'
    result = recv_line(mock_sock, max_bytes=1000)
    assert result == '{"ok": true}'


def test_recv_line_eof() -> None:
    mock_sock = MagicMock()
    mock_sock.recv.return_value = b""
    result = recv_line(mock_sock)
    assert result == ""


# ---------------------------------------------------------------------------
# B10: large-message transport tests
# ---------------------------------------------------------------------------


def test_recv_line_default_limit_is_large_enough_for_debug() -> None:
    """A ~1 MB debug trace payload must not hit the default limit."""
    # Build a JSON payload resembling a debug trace (~1 MB)
    step = '{"step":0,"instruction":0,"file":"s.comp","line":1,"changes":[]}'
    trace_body = ",".join([step] * 20_000)
    payload = f'{{"result":{{"trace":[{trace_body}]}}}}\n'.encode()
    assert len(payload) > 1_000_000  # sanity: > 1 MB

    chunks = [payload[i : i + 4096] for i in range(0, len(payload), 4096)]
    call_iter = iter(chunks)
    mock_sock = MagicMock()
    mock_sock.recv.side_effect = lambda _sz: next(call_iter)

    result = recv_line(mock_sock)
    assert "trace" in result


def test_recv_line_large_message_at_limit() -> None:
    """Exactly max_bytes bytes ending with newline should succeed."""
    limit = 200
    body = b"A" * (limit - 1) + b"\n"
    assert len(body) == limit

    chunks = [body[i : i + 4096] for i in range(0, len(body), 4096)]
    call_iter = iter(chunks)
    mock_sock = MagicMock()
    mock_sock.recv.side_effect = lambda _sz: next(call_iter)

    result = recv_line(mock_sock, max_bytes=limit)
    assert result == "A" * (limit - 1)


def test_recv_line_large_message_just_over_limit() -> None:
    """One byte over max_bytes must raise ValueError."""
    limit = 200
    body = b"A" * (limit + 1)

    chunks = [body[i : i + 4096] for i in range(0, len(body), 4096)]
    call_iter = iter(chunks)
    mock_sock = MagicMock()
    mock_sock.recv.side_effect = lambda _sz: next(call_iter)

    with pytest.raises(ValueError, match="max_bytes"):
        recv_line(mock_sock, max_bytes=limit)
