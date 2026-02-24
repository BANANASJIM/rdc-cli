"""Tests for handler behavior in remote-mode DaemonState."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from rdc.daemon_server import DaemonState
from rdc.handlers.core import _handle_shutdown, _handle_status
from rdc.handlers.texture import _handle_rt_overlay


def _make_state(*, is_remote: bool = False) -> DaemonState:
    """Build a DaemonState with mock adapter for handler tests."""
    controller = MagicMock()
    state = DaemonState(capture="frame.rdc", current_eid=0, token="tok")
    from rdc.adapter import RenderDocAdapter

    state.adapter = RenderDocAdapter(controller=controller, version=(1, 41))
    state.rd = MagicMock()
    state.is_remote = is_remote
    if is_remote:
        state.remote = MagicMock()
        state.remote_url = "host:39920"
    return state


class TestShutdownRemote:
    def test_remote_calls_close_and_shutdown_connection(self) -> None:
        state = _make_state(is_remote=True)
        resp, running = _handle_shutdown(1, {"_token": "tok"}, state)
        assert running is False
        assert resp["result"]["ok"] is True
        state.remote.CloseCapture.assert_called_once_with(state.adapter.controller)
        state.remote.ShutdownConnection.assert_called_once()

    def test_remote_does_not_call_adapter_shutdown(self) -> None:
        state = _make_state(is_remote=True)
        # Use MagicMock adapter to track shutdown() calls
        mock_adapter = MagicMock()
        mock_adapter.controller = MagicMock()
        state.adapter = mock_adapter  # type: ignore[assignment]
        _handle_shutdown(1, {"_token": "tok"}, state)
        mock_adapter.shutdown.assert_not_called()

    def test_local_calls_adapter_shutdown(self) -> None:
        state = _make_state(is_remote=False)
        mock_adapter = MagicMock()
        mock_adapter.controller = MagicMock()
        state.adapter = mock_adapter  # type: ignore[assignment]
        _handle_shutdown(1, {"_token": "tok"}, state)
        mock_adapter.shutdown.assert_called_once()

    def test_remote_close_capture_exception_ignored(self) -> None:
        state = _make_state(is_remote=True)
        state.remote.CloseCapture.side_effect = RuntimeError("boom")
        resp, _running = _handle_shutdown(1, {"_token": "tok"}, state)
        assert resp["result"]["ok"] is True
        state.remote.ShutdownConnection.assert_called_once()

    def test_remote_stops_ping_thread(self) -> None:
        state = _make_state(is_remote=True)
        stop_event = threading.Event()
        state._ping_stop = stop_event
        state._ping_thread = MagicMock()
        _handle_shutdown(1, {"_token": "tok"}, state)
        assert stop_event.is_set()
        state._ping_thread.join.assert_called_once_with(timeout=5.0)

    def test_shutdown_remote_shuts_down_cap(self) -> None:
        state = _make_state(is_remote=True)
        mock_cap = MagicMock()
        state.cap = mock_cap
        _handle_shutdown(1, {"_token": "tok"}, state)
        mock_cap.Shutdown.assert_called_once()


class TestStatusRemote:
    def test_remote_includes_remote_fields(self) -> None:
        state = _make_state(is_remote=True)
        resp, running = _handle_status(1, {"_token": "tok"}, state)
        assert running is True
        result = resp["result"]
        assert result["remote"] == "host:39920"
        assert result["remote_connected"] is True

    def test_remote_disconnected(self) -> None:
        state = _make_state(is_remote=True)
        state.remote = None
        resp, _running = _handle_status(1, {"_token": "tok"}, state)
        assert resp["result"]["remote_connected"] is False

    def test_local_no_remote_fields(self) -> None:
        state = _make_state(is_remote=False)
        resp, _running = _handle_status(1, {"_token": "tok"}, state)
        assert "remote" not in resp["result"]


class TestRtOverlayRemote:
    def test_remote_returns_error(self) -> None:
        state = _make_state(is_remote=True)
        resp, running = _handle_rt_overlay(1, {"_token": "tok", "overlay": "wireframe"}, state)
        assert running is True
        assert resp["error"]["code"] == -32002
        assert "remote mode" in resp["error"]["message"]

    def test_local_does_not_return_remote_error(self) -> None:
        state = _make_state(is_remote=False)
        state.temp_dir = None
        resp, _running = _handle_rt_overlay(1, {"_token": "tok", "overlay": "wireframe"}, state)
        # Local mode proceeds past the remote guard; may hit other guards
        # but should NOT return the remote-mode error
        if "error" in resp:
            assert "remote mode" not in resp["error"]["message"]
