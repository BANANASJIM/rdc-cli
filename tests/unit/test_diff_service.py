from __future__ import annotations

import os
import signal
from unittest.mock import MagicMock, patch

import pytest

from rdc.services import diff_service
from rdc.services.diff_service import (
    DiffContext,
    query_both,
    query_both_sync,
    start_diff_session,
    stop_diff_session,
)

# ---------------------------------------------------------------------------
# #1  DiffContext construction
# ---------------------------------------------------------------------------


def test_diff_context_fields() -> None:
    ctx = DiffContext(
        session_id="aabbccddeeff",
        host="127.0.0.1",
        port_a=5000,
        port_b=5001,
        token_a="tok_a",
        token_b="tok_b",
        pid_a=100,
        pid_b=200,
        capture_a="a.rdc",
        capture_b="b.rdc",
    )
    assert ctx.session_id == "aabbccddeeff"
    assert ctx.host == "127.0.0.1"
    assert ctx.port_a == 5000
    assert ctx.port_b == 5001
    assert ctx.token_a == "tok_a"
    assert ctx.token_b == "tok_b"
    assert ctx.pid_a == 100
    assert ctx.pid_b == 200
    assert ctx.capture_a == "a.rdc"
    assert ctx.capture_b == "b.rdc"


# ---------------------------------------------------------------------------
# #2–7  start_diff_session — happy path
# ---------------------------------------------------------------------------


def _mock_start_daemon(capture: str, port: int, token: str, **kw: object) -> MagicMock:
    proc = MagicMock()
    proc.pid = port  # unique per call
    return proc


def _mock_wait_ok(*args: object, **kwargs: object) -> tuple[bool, str]:
    return True, ""


def test_start_diff_session_happy(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setattr(diff_service, "start_daemon", _mock_start_daemon)
    monkeypatch.setattr(diff_service, "wait_for_ping", _mock_wait_ok)
    monkeypatch.setattr(diff_service, "pick_port", MagicMock(side_effect=[5000, 5001]))

    ctx, err = start_diff_session("a.rdc", "b.rdc")
    assert ctx is not None
    assert err == ""
    assert ctx.capture_a == "a.rdc"
    assert ctx.capture_b == "b.rdc"


def test_start_diff_session_id_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "start_daemon", _mock_start_daemon)
    monkeypatch.setattr(diff_service, "wait_for_ping", _mock_wait_ok)
    monkeypatch.setattr(diff_service, "pick_port", MagicMock(side_effect=[5000, 5001]))

    ctx, _ = start_diff_session("a.rdc", "b.rdc")
    assert ctx is not None
    assert len(ctx.session_id) == 12
    assert all(c in "0123456789abcdef" for c in ctx.session_id)


def test_start_diff_session_distinct_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "start_daemon", _mock_start_daemon)
    monkeypatch.setattr(diff_service, "wait_for_ping", _mock_wait_ok)
    monkeypatch.setattr(diff_service, "pick_port", MagicMock(side_effect=[5000, 5001]))

    ctx, _ = start_diff_session("a.rdc", "b.rdc")
    assert ctx is not None
    assert ctx.token_a != ctx.token_b


def test_start_diff_session_distinct_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "start_daemon", _mock_start_daemon)
    monkeypatch.setattr(diff_service, "wait_for_ping", _mock_wait_ok)
    monkeypatch.setattr(diff_service, "pick_port", MagicMock(side_effect=[5000, 5001]))

    ctx, _ = start_diff_session("a.rdc", "b.rdc")
    assert ctx is not None
    assert ctx.port_a != ctx.port_b


def test_start_diff_session_registers_atexit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "start_daemon", _mock_start_daemon)
    monkeypatch.setattr(diff_service, "wait_for_ping", _mock_wait_ok)
    monkeypatch.setattr(diff_service, "pick_port", MagicMock(side_effect=[5000, 5001]))

    with patch("atexit.register") as mock_atexit:
        ctx, _ = start_diff_session("a.rdc", "b.rdc")
        assert mock_atexit.called


def test_start_diff_session_idle_timeout_120(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def capturing_start_daemon(capture: str, port: int, token: str, **kw: object) -> MagicMock:
        calls.append(kw)
        proc = MagicMock()
        proc.pid = port
        return proc

    monkeypatch.setattr(diff_service, "start_daemon", capturing_start_daemon)
    monkeypatch.setattr(diff_service, "wait_for_ping", _mock_wait_ok)
    monkeypatch.setattr(diff_service, "pick_port", MagicMock(side_effect=[5000, 5001]))

    start_diff_session("a.rdc", "b.rdc")
    assert all(c.get("idle_timeout") == 120 for c in calls)


# ---------------------------------------------------------------------------
# #8–11  start_diff_session — failure paths
# ---------------------------------------------------------------------------


def _mock_wait_fail(*args: object, **kwargs: object) -> tuple[bool, str]:
    return False, "ping failed"


def test_start_diff_session_a_fails_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    kill_pids: list[int] = []

    def killing_start(capture: str, port: int, token: str, **kw: object) -> MagicMock:
        proc = MagicMock()
        proc.pid = port
        proc.kill = lambda: kill_pids.append(port)
        return proc

    call_count = 0

    def wait_a_fails(*args: object, **kwargs: object) -> tuple[bool, str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False, "A failed"
        return True, ""

    monkeypatch.setattr(diff_service, "start_daemon", killing_start)
    monkeypatch.setattr(diff_service, "wait_for_ping", wait_a_fails)
    monkeypatch.setattr(diff_service, "pick_port", MagicMock(side_effect=[5000, 5001]))

    ctx, err = start_diff_session("a.rdc", "b.rdc")
    assert ctx is None
    assert err != ""


def test_start_diff_session_b_fails_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0

    def wait_b_fails(*args: object, **kwargs: object) -> tuple[bool, str]:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return False, "B failed"
        return True, ""

    monkeypatch.setattr(diff_service, "start_daemon", _mock_start_daemon)
    monkeypatch.setattr(diff_service, "wait_for_ping", wait_b_fails)
    monkeypatch.setattr(diff_service, "pick_port", MagicMock(side_effect=[5000, 5001]))

    ctx, err = start_diff_session("a.rdc", "b.rdc")
    assert ctx is None
    assert err != ""


def test_start_diff_session_popen_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0

    def second_raises(capture: str, port: int, token: str, **kw: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise OSError("spawn failed")
        proc = MagicMock()
        proc.pid = port
        return proc

    monkeypatch.setattr(diff_service, "start_daemon", second_raises)
    monkeypatch.setattr(diff_service, "pick_port", MagicMock(side_effect=[5000, 5001]))

    ctx, err = start_diff_session("a.rdc", "b.rdc")
    assert ctx is None
    assert "spawn failed" in err


def test_start_diff_session_both_fail_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "start_daemon", _mock_start_daemon)
    monkeypatch.setattr(diff_service, "wait_for_ping", _mock_wait_fail)
    monkeypatch.setattr(diff_service, "pick_port", MagicMock(side_effect=[5000, 5001]))

    ctx, err = start_diff_session("a.rdc", "b.rdc")
    assert ctx is None
    assert err != ""


# ---------------------------------------------------------------------------
# #12–15  stop_diff_session
# ---------------------------------------------------------------------------


def _make_ctx(**overrides: object) -> DiffContext:
    defaults: dict[str, object] = {
        "session_id": "aabbccddeeff",
        "host": "127.0.0.1",
        "port_a": 5000,
        "port_b": 5001,
        "token_a": "ta",
        "token_b": "tb",
        "pid_a": 100,
        "pid_b": 200,
        "capture_a": "a.rdc",
        "capture_b": "b.rdc",
    }
    defaults.update(overrides)
    return DiffContext(**defaults)  # type: ignore[arg-type]


def test_stop_diff_session_clean_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "send_request", lambda *a, **kw: {"result": {"ok": True}})
    monkeypatch.setattr(diff_service, "is_pid_alive", lambda pid: False)
    kill_calls: list[int] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: kill_calls.append(pid))

    stop_diff_session(_make_ctx())
    assert kill_calls == []


def test_stop_diff_session_rpc_fails_sigterm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "send_request", MagicMock(side_effect=ConnectionRefusedError))
    monkeypatch.setattr(diff_service, "is_pid_alive", lambda pid: True)
    kill_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: kill_calls.append((pid, sig)))

    stop_diff_session(_make_ctx())
    assert (100, signal.SIGTERM) in kill_calls
    assert (200, signal.SIGTERM) in kill_calls


def test_stop_diff_session_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "send_request", lambda *a, **kw: {"result": {"ok": True}})
    monkeypatch.setattr(diff_service, "is_pid_alive", lambda pid: False)

    ctx = _make_ctx()
    stop_diff_session(ctx)
    stop_diff_session(ctx)  # no exception


def test_stop_diff_session_process_lookup_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "send_request", MagicMock(side_effect=ConnectionRefusedError))
    monkeypatch.setattr(diff_service, "is_pid_alive", lambda pid: True)

    def raise_lookup(pid: int, sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr(os, "kill", raise_lookup)
    stop_diff_session(_make_ctx())  # must not raise


# ---------------------------------------------------------------------------
# #16–21  query_both
# ---------------------------------------------------------------------------


def test_query_both_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_send(host: str, port: int, payload: dict, **kw: object) -> dict:
        return {"result": {"port": port}}

    monkeypatch.setattr(diff_service, "send_request", mock_send)

    ctx = _make_ctx()
    ra, rb, err = query_both(ctx, "status", {})
    assert ra is not None and rb is not None
    assert err == ""
    assert ra["result"]["port"] == 5000
    assert rb["result"]["port"] == 5001


def test_query_both_token_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_tokens: list[str] = []

    def mock_send(host: str, port: int, payload: dict, **kw: object) -> dict:
        sent_tokens.append(payload["params"]["_token"])
        return {"result": {}}

    monkeypatch.setattr(diff_service, "send_request", mock_send)

    ctx = _make_ctx()
    query_both(ctx, "status", {})
    assert "ta" in sent_tokens
    assert "tb" in sent_tokens


def test_query_both_no_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "send_request", lambda *a, **kw: {"result": {}})

    original = {"key": "val"}
    query_both(_make_ctx(), "status", original)
    assert "_token" not in original


def test_query_both_a_error(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0

    def mock_send(host: str, port: int, payload: dict, **kw: object) -> dict:
        nonlocal call_count
        call_count += 1
        if port == 5000:
            return {"error": {"message": "fail"}}
        return {"result": {"ok": True}}

    monkeypatch.setattr(diff_service, "send_request", mock_send)

    ra, rb, err = query_both(_make_ctx(), "test", {})
    assert ra is None
    assert rb is not None


def test_query_both_b_connection_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_send(host: str, port: int, payload: dict, **kw: object) -> dict:
        if port == 5001:
            raise ConnectionRefusedError
        return {"result": {"ok": True}}

    monkeypatch.setattr(diff_service, "send_request", mock_send)

    ra, rb, err = query_both(_make_ctx(), "test", {})
    assert ra is not None
    assert rb is None


def test_query_both_both_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff_service, "send_request", MagicMock(side_effect=ConnectionRefusedError))

    ra, rb, err = query_both(_make_ctx(), "test", {})
    assert ra is None
    assert rb is None
    assert err != ""


# ---------------------------------------------------------------------------
# #22–23  query_both_sync
# ---------------------------------------------------------------------------


def test_query_both_sync_ordering(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_send(host: str, port: int, payload: dict, **kw: object) -> dict:
        method = payload["method"]
        return {"result": {"method": method, "port": port}}

    monkeypatch.setattr(diff_service, "send_request", mock_send)

    calls = [("m1", {"x": 1}), ("m2", {"x": 2})]
    ra_list, rb_list, err = query_both_sync(_make_ctx(), calls)
    assert err == ""
    assert ra_list[0] is not None and ra_list[0]["result"]["method"] == "m1"
    assert ra_list[1] is not None and ra_list[1]["result"]["method"] == "m2"
    assert rb_list[0] is not None and rb_list[0]["result"]["method"] == "m1"
    assert rb_list[1] is not None and rb_list[1]["result"]["method"] == "m2"


def test_query_both_sync_partial_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_send(host: str, port: int, payload: dict, **kw: object) -> dict:
        if port == 5000 and payload["method"] == "m2":
            raise ConnectionRefusedError
        return {"result": {"ok": True}}

    monkeypatch.setattr(diff_service, "send_request", mock_send)

    calls = [("m1", {}), ("m2", {})]
    ra_list, rb_list, err = query_both_sync(_make_ctx(), calls)
    assert ra_list[0] is not None
    assert ra_list[1] is None
    assert rb_list[0] is not None
    assert rb_list[1] is not None
