"""Regression test: stats RPC must emit event_count (drives diff summary 'events')."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import mock_renderdoc as rd
from conftest import make_daemon_state, rpc_request

from rdc.daemon_server import _handle_request


def _make_state(max_eid: int) -> Any:
    ctrl = rd.MockReplayController()
    ctrl._actions = []
    return make_daemon_state(
        capture="x.rdc",
        ctrl=ctrl,
        structured_file=SimpleNamespace(chunks=[]),
        max_eid=max_eid,
    )


def test_stats_result_carries_event_count() -> None:
    """The stats RPC result includes event_count equal to state.max_eid."""
    state = _make_state(max_eid=137)
    resp, _ = _handle_request(rpc_request("stats"), state)
    result = resp["result"]
    assert "event_count" in result, "stats RPC must emit event_count"
    assert result["event_count"] == 137


def test_stats_event_count_matches_status_rpc() -> None:
    """stats and status report the same event_count (both = max_eid)."""
    state = _make_state(max_eid=42)
    stats_resp, _ = _handle_request(rpc_request("stats"), state)
    status_resp, _ = _handle_request(rpc_request("status"), state)
    assert stats_resp["result"]["event_count"] == status_resp["result"]["event_count"] == 42
