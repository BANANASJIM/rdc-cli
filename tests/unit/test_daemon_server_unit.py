from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request, _load_replay, _set_frame_event

# Make mock module importable
sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))


class TestHandleRequest:
    def _state(self) -> DaemonState:
        return DaemonState(capture="capture.rdc", current_eid=0, token="tok")

    def _state_with_adapter(self, *, event_count: int = 1000) -> DaemonState:
        calls: list[tuple[int, bool]] = []
        controller = SimpleNamespace(
            SetFrameEvent=lambda eid, force: calls.append((eid, force)),
            Shutdown=lambda: None,
        )
        state = self._state()
        state.adapter = RenderDocAdapter(controller=controller, version=(1, 33))
        state.event_count = event_count
        state._set_frame_calls = calls  # type: ignore[attr-defined]
        return state

    def test_ping(self) -> None:
        state = self._state()
        resp, running = _handle_request(
            {"id": 1, "method": "ping", "params": {"_token": "tok"}}, state
        )
        assert running is True
        assert resp["result"]["ok"] is True

    def test_status_returns_metadata(self) -> None:
        state = self._state()
        state.api_name = "Vulkan"
        state.event_count = 500
        resp, running = _handle_request(
            {"id": 2, "method": "status", "params": {"_token": "tok"}}, state
        )
        assert running is True
        assert resp["result"]["capture"] == "capture.rdc"
        assert resp["result"]["api"] == "Vulkan"
        assert resp["result"]["event_count"] == 500
        assert resp["result"]["current_eid"] == 0

    def test_goto_calls_set_frame_event(self) -> None:
        state = self._state_with_adapter()
        resp, running = _handle_request(
            {"id": 3, "method": "goto", "params": {"_token": "tok", "eid": 142}}, state
        )
        assert running is True
        assert resp["result"]["current_eid"] == 142
        assert state._set_frame_calls == [(142, True)]  # type: ignore[attr-defined]

    def test_goto_caches_eid(self) -> None:
        state = self._state_with_adapter()
        _set_frame_event(state, 142)
        _set_frame_event(state, 142)  # should be cached
        assert len(state._set_frame_calls) == 1  # type: ignore[attr-defined]
        assert state.current_eid == 142

    def test_goto_incremental(self) -> None:
        state = self._state_with_adapter()
        _set_frame_event(state, 100)
        _set_frame_event(state, 200)
        calls = state._set_frame_calls  # type: ignore[attr-defined]
        assert len(calls) == 2
        assert calls[1] == (200, True)

    def test_goto_out_of_range(self) -> None:
        state = self._state_with_adapter(event_count=500)
        resp, running = _handle_request(
            {"id": 3, "method": "goto", "params": {"_token": "tok", "eid": 9999}}, state
        )
        assert running is True
        assert resp["error"]["code"] == -32002

    def test_goto_negative_eid(self) -> None:
        state = self._state_with_adapter(event_count=500)
        err = _set_frame_event(state, -1)
        assert err is not None
        assert "eid must be >= 0" in err

    def test_shutdown_calls_adapter_and_cap(self) -> None:
        ctrl_shutdown = {"called": False}
        cap_shutdown = {"called": False}
        controller = SimpleNamespace(Shutdown=lambda: ctrl_shutdown.update(called=True))
        cap = SimpleNamespace(Shutdown=lambda: cap_shutdown.update(called=True))

        state = self._state()
        state.adapter = RenderDocAdapter(controller=controller, version=(1, 33))
        state.cap = cap

        resp, running = _handle_request(
            {"id": 4, "method": "shutdown", "params": {"_token": "tok"}}, state
        )
        assert running is False
        assert resp["result"]["ok"] is True
        assert ctrl_shutdown["called"] is True
        assert cap_shutdown["called"] is True

    def test_shutdown_without_adapter(self) -> None:
        state = self._state()
        resp, running = _handle_request(
            {"id": 4, "method": "shutdown", "params": {"_token": "tok"}}, state
        )
        assert running is False
        assert resp["result"]["ok"] is True

    def test_invalid_token(self) -> None:
        state = self._state()
        resp, running = _handle_request(
            {"id": 1, "method": "status", "params": {"_token": "bad"}}, state
        )
        assert running is True
        assert resp["error"]["code"] == -32600

    def test_unknown_method(self) -> None:
        state = self._state()
        resp, running = _handle_request(
            {"id": 2, "method": "unknown", "params": {"_token": "tok"}}, state
        )
        assert running is True
        assert resp["error"]["code"] == -32601

    def test_resources_no_adapter(self) -> None:
        """Test resources handler without adapter."""
        state = self._state()  # No adapter
        resp, running = _handle_request(
            {"id": 1, "method": "resources", "params": {"_token": "tok"}}, state
        )
        assert "error" in resp
        assert resp["error"]["code"] == -32002

    def test_resource_no_adapter(self) -> None:
        """Test resource handler without adapter."""
        state = self._state()
        resp, running = _handle_request(
            {"id": 1, "method": "resource", "params": {"_token": "tok", "id": 1}}, state
        )
        assert "error" in resp
        assert resp["error"]["code"] == -32002

    def test_passes_no_adapter(self) -> None:
        """Test passes handler without adapter."""
        state = self._state()
        resp, running = _handle_request(
            {"id": 1, "method": "passes", "params": {"_token": "tok"}}, state
        )
        assert "error" in resp
        assert resp["error"]["code"] == -32002


class TestLoadReplay:
    """Test _load_replay with mock renderdoc module (P1 fix)."""

    def test_load_replay_success(self) -> None:
        import mock_renderdoc as mock_rd

        sys.modules["renderdoc"] = mock_rd  # type: ignore[assignment]
        try:
            state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
            err = _load_replay(state)
            assert err is None
            assert state.adapter is not None
            assert state.cap is not None
            assert state.api_name == "Vulkan"
        finally:
            sys.modules.pop("renderdoc", None)

    def test_load_replay_import_failure(self) -> None:
        sys.modules.pop("renderdoc", None)
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        err = _load_replay(state)
        assert err is not None
        assert "renderdoc" in err
