from __future__ import annotations

from rdc.daemon_server import DaemonState, _handle_request


def test_handle_ping_status_goto_shutdown() -> None:
    state = DaemonState(capture="capture.rdc", current_eid=0, token="tok")

    ping_resp, running = _handle_request(
        {"id": 1, "method": "ping", "params": {"_token": "tok"}},
        state,
    )
    assert running is True
    assert ping_resp["result"]["ok"] is True

    status_resp, running = _handle_request(
        {"id": 2, "method": "status", "params": {"_token": "tok"}},
        state,
    )
    assert running is True
    assert status_resp["result"]["capture"] == "capture.rdc"
    assert status_resp["result"]["current_eid"] == 0

    goto_resp, running = _handle_request(
        {"id": 3, "method": "goto", "params": {"_token": "tok", "eid": 9}},
        state,
    )
    assert running is True
    assert goto_resp["result"]["current_eid"] == 9
    assert state.current_eid == 9

    shutdown_resp, running = _handle_request(
        {"id": 4, "method": "shutdown", "params": {"_token": "tok"}},
        state,
    )
    assert running is False
    assert shutdown_resp["result"]["ok"] is True


def test_handle_invalid_token_and_unknown_method() -> None:
    state = DaemonState(capture="capture.rdc", current_eid=0, token="tok")

    bad_token_resp, running = _handle_request(
        {"id": 1, "method": "status", "params": {"_token": "bad"}},
        state,
    )
    assert running is True
    assert bad_token_resp["error"]["code"] == -32600

    unknown_resp, running = _handle_request(
        {"id": 2, "method": "unknown", "params": {"_token": "tok"}},
        state,
    )
    assert running is True
    assert unknown_resp["error"]["code"] == -32601
