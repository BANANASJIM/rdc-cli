from __future__ import annotations

import pytest

from rdc.protocol import goto_request, ping_request, shutdown_request, status_request


def test_ping_request_shape() -> None:
    payload = ping_request("tok", 7)
    assert payload == {
        "jsonrpc": "2.0",
        "method": "ping",
        "id": 7,
        "params": {"_token": "tok"},
    }


def test_shutdown_request_shape() -> None:
    payload = shutdown_request("tok", 9)
    assert payload == {
        "jsonrpc": "2.0",
        "method": "shutdown",
        "id": 9,
        "params": {"_token": "tok"},
    }


def test_status_and_goto_request_shape() -> None:
    assert status_request("tok", 1)["method"] == "status"
    assert goto_request("tok", 42, 2)["params"]["eid"] == 42


def test_negative_request_id_rejected() -> None:
    with pytest.raises(ValueError):
        ping_request("tok", -1)
