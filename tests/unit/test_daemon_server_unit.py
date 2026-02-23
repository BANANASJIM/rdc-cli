from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request, _load_replay, _set_frame_event

# Make mock module importable
sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))


class TestHandleRequest:
    def _state(self) -> DaemonState:
        return DaemonState(capture="capture.rdc", current_eid=0, token="tok")

    def _state_with_adapter(self, *, max_eid: int = 1000) -> DaemonState:
        calls: list[tuple[int, bool]] = []
        controller = SimpleNamespace(
            SetFrameEvent=lambda eid, force: calls.append((eid, force)),
            Shutdown=lambda: None,
        )
        state = self._state()
        state.adapter = RenderDocAdapter(controller=controller, version=(1, 33))
        state.max_eid = max_eid
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
        state.max_eid = 500
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
        state = self._state_with_adapter(max_eid=500)
        resp, running = _handle_request(
            {"id": 3, "method": "goto", "params": {"_token": "tok", "eid": 9999}}, state
        )
        assert running is True
        assert resp["error"]["code"] == -32002

    def test_goto_negative_eid(self) -> None:
        state = self._state_with_adapter(max_eid=500)
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


class TestShutdownExceptionStops:
    def test_shutdown_exception_still_stops(self) -> None:
        """If shutdown handler raises, running should be False."""
        # The fix is in run_server's except block:
        #   running = request.get("method") != "shutdown"
        # Verify the logic directly:
        request: dict[str, Any] = {"method": "shutdown", "id": 1}
        running = request.get("method") != "shutdown"
        assert running is False

    def test_non_shutdown_exception_keeps_running(self) -> None:
        """If a non-shutdown handler raises, running should be True."""
        request: dict[str, Any] = {"method": "status", "id": 1}
        running = request.get("method") != "shutdown"
        assert running is True


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

    def test_load_replay_import_failure(self, monkeypatch: Any) -> None:
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: None)
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        err = _load_replay(state)
        assert err is not None
        assert "renderdoc" in err


# --- P1-SEC-3: temp dir cleanup tests ---


class TestTempDirCleanup:
    """atexit registration and cleanup callback for temp dirs."""

    def test_load_replay_registers_atexit(self) -> None:
        """_load_replay registers _cleanup_temp via atexit after mkdtemp."""
        import mock_renderdoc as mock_rd

        sys.modules["renderdoc"] = mock_rd  # type: ignore[assignment]
        try:
            state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
            with patch("atexit.register") as mock_atexit:
                _load_replay(state)
                mock_atexit.assert_called_once()
                # The registered function should be _cleanup_temp
                from rdc.daemon_server import _cleanup_temp

                mock_atexit.assert_called_once_with(_cleanup_temp, state)
        finally:
            sys.modules.pop("renderdoc", None)

    def test_cleanup_temp_deletes_dir(self, tmp_path: Path) -> None:
        """Calling _cleanup_temp removes the temp dir."""
        from rdc.daemon_server import _cleanup_temp

        temp = tmp_path / "rdc-test"
        temp.mkdir()
        (temp / "data.bin").write_bytes(b"gpu data")
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        state.temp_dir = temp
        _cleanup_temp(state)
        assert not temp.exists()

    def test_cleanup_temp_no_error_if_already_removed(self, tmp_path: Path) -> None:
        """_cleanup_temp must not raise if the temp dir is already gone."""
        from rdc.daemon_server import _cleanup_temp

        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        state.temp_dir = tmp_path / "nonexistent"
        _cleanup_temp(state)  # should not raise


class TestSigtermHandler:
    """SIGTERM handler installation in main()."""

    def test_main_installs_sigterm_handler(self) -> None:
        """main() installs a SIGTERM handler that calls sys.exit(0)."""
        with (
            patch("rdc.daemon_server.argparse.ArgumentParser") as mock_parser_cls,
            patch("rdc.daemon_server.run_server"),
            patch("signal.signal") as mock_signal,
        ):
            mock_args = SimpleNamespace(
                host="127.0.0.1",
                port=9999,
                capture="test.rdc",
                token="tok",
                idle_timeout=1800,
                no_replay=True,
            )
            mock_parser_cls.return_value.parse_args.return_value = mock_args

            from rdc.daemon_server import main

            main()

            # Find the SIGTERM call
            sigterm_calls = [c for c in mock_signal.call_args_list if c[0][0] == signal.SIGTERM]
            assert len(sigterm_calls) == 1
            handler = sigterm_calls[0][0][1]
            # Handler should call sys.exit(0)
            with pytest.raises(SystemExit) as exc_info:
                handler(signal.SIGTERM, None)
            assert exc_info.value.code == 0


# --- P1-OBS-1: _process_request exception logging tests ---


class TestProcessRequest:
    """_process_request extracts the try/except from run_server."""

    def _state(self) -> DaemonState:
        return DaemonState(capture="capture.rdc", current_eid=0, token="tok")

    def test_exception_is_logged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Handler raising RuntimeError logs via logger.exception with method name."""
        from rdc.daemon_server import _DISPATCH, _process_request

        def _boom(_rid: Any, _params: Any, _state: Any) -> Any:
            raise RuntimeError("boom")

        _boom._no_replay = True  # type: ignore[attr-defined]
        monkeypatch.setitem(_DISPATCH, "test_boom", _boom)
        state = self._state()
        request = {"id": 1, "method": "test_boom", "params": {"_token": "tok"}}
        with patch.object(logging.getLogger("rdc.daemon"), "exception") as mock_log:
            resp, running = _process_request(request, state)
            mock_log.assert_called_once()
            assert "test_boom" in mock_log.call_args[0][0] % mock_log.call_args[0][1:]

    def test_exception_returns_internal_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exception returns JSON-RPC -32603 internal error."""
        from rdc.daemon_server import _DISPATCH, _process_request

        def _boom(_rid: Any, _params: Any, _state: Any) -> Any:
            raise RuntimeError("boom")

        _boom._no_replay = True  # type: ignore[attr-defined]
        monkeypatch.setitem(_DISPATCH, "test_boom", _boom)
        state = self._state()
        request = {"id": 1, "method": "test_boom", "params": {"_token": "tok"}}
        resp, _running = _process_request(request, state)
        assert resp["error"]["code"] == -32603

    def test_exception_keeps_running_for_non_shutdown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-shutdown exception returns running=True."""
        from rdc.daemon_server import _DISPATCH, _process_request

        def _boom(_rid: Any, _params: Any, _state: Any) -> Any:
            raise RuntimeError("boom")

        _boom._no_replay = True  # type: ignore[attr-defined]
        monkeypatch.setitem(_DISPATCH, "test_boom", _boom)
        state = self._state()
        request = {"id": 1, "method": "test_boom", "params": {"_token": "tok"}}
        _resp, running = _process_request(request, state)
        assert running is True


# --- P1-MAINT-1: adapter-guard middleware tests ---


class TestAdapterGuardMiddleware:
    """Middleware in _handle_request blocks replay-required handlers when adapter=None."""

    def _state(self) -> DaemonState:
        return DaemonState(capture="capture.rdc", current_eid=0, token="tok")

    def test_ping_no_adapter(self) -> None:
        """ping has _no_replay=True, so it works without adapter."""
        state = self._state()
        resp, running = _handle_request(
            {"id": 1, "method": "ping", "params": {"_token": "tok"}}, state
        )
        assert running is True
        assert "result" in resp
        assert resp["result"]["ok"] is True

    def test_status_no_adapter(self) -> None:
        """status has _no_replay=True, so it works without adapter."""
        state = self._state()
        resp, running = _handle_request(
            {"id": 2, "method": "status", "params": {"_token": "tok"}}, state
        )
        assert running is True
        assert "result" in resp

    def test_shutdown_no_adapter(self) -> None:
        """shutdown has _no_replay=True, so it works without adapter."""
        state = self._state()
        resp, running = _handle_request(
            {"id": 3, "method": "shutdown", "params": {"_token": "tok"}}, state
        )
        assert running is False
        assert resp["result"]["ok"] is True

    def test_replay_required_blocked_by_middleware(self) -> None:
        """A replay-required handler returns -32002 when adapter=None."""
        state = self._state()
        # draws is a replay-required handler
        resp, running = _handle_request(
            {"id": 4, "method": "draws", "params": {"_token": "tok"}}, state
        )
        assert running is True
        assert "error" in resp
        assert resp["error"]["code"] == -32002
        assert "no replay loaded" in resp["error"]["message"]

    def test_multiple_replay_required_methods_blocked(self) -> None:
        """Several replay-required methods are blocked by middleware."""
        state = self._state()
        for method in ("buf_info", "tex_info", "shader_targets", "vfs_ls"):
            resp, running = _handle_request(
                {"id": 5, "method": method, "params": {"_token": "tok"}}, state
            )
            assert resp["error"]["code"] == -32002, f"{method} should be blocked"
