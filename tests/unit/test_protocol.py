from __future__ import annotations

import pytest

from rdc.protocol import ping_request, shutdown_request


def test_ping_request_shape() -> None:
    payload = ping_request(7)
    assert payload == {"jsonrpc": "2.0", "method": "ping", "id": 7}


def test_shutdown_request_shape() -> None:
    payload = shutdown_request(9)
    assert payload == {"jsonrpc": "2.0", "method": "shutdown", "id": 9}


def test_negative_request_id_rejected() -> None:
    with pytest.raises(ValueError):
        ping_request(-1)
