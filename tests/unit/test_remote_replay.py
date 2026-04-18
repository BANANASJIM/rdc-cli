"""Tests for remote replay infrastructure in daemon_server.py."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from rdc.daemon_server import (
    DaemonState,
    _load_remote_replay,
    _load_replay,
    _start_ping_thread,
    _stop_ping_thread,
)


def _make_mock_rd(
    *,
    connect_result: int = 0,
    open_capture_result: int = 0,
    open_file_result: int = 0,
    copy_to_remote_path: str = "/tmp/RenderDoc/frame.rdc",
) -> tuple[MagicMock, MagicMock]:
    """Build mock rd module and remote server."""
    mock_remote = MagicMock()
    mock_remote.OpenCapture.return_value = (open_capture_result, MagicMock())
    mock_remote.CopyCaptureToRemote.return_value = copy_to_remote_path
    mock_remote.CopyCaptureFromRemote.return_value = None
    mock_remote.Ping.return_value = None
    mock_remote.CloseCapture.return_value = None
    mock_remote.ShutdownConnection.return_value = None

    mock_cap = MagicMock()
    mock_cap.OpenFile.return_value = open_file_result
    mock_cap.GetStructuredData.return_value = MagicMock()

    rd = MagicMock()
    rd.ResultCode.Succeeded = 0
    rd.InitialiseReplay.return_value = None
    rd.CreateRemoteServerConnection.return_value = (connect_result, mock_remote)
    rd.RemoteServer.NoPreference = 0
    rd.ReplayOptions.return_value = MagicMock()
    rd.OpenCaptureFile.return_value = mock_cap
    rd.GetVersionString.return_value = "1.41"

    return rd, mock_remote


class TestLoadRemoteReplay:
    def test_no_renderdoc_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: None)
        state = DaemonState(capture="/tmp/frame.rdc", current_eid=0, token="tok")
        err = _load_remote_replay(state, "host:39920")
        assert err is not None
        assert "failed to import renderdoc module" in err

    def test_init_replay_fails_continues(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """B39: InitialiseReplay failure does not abort remote replay."""
        rd, _remote = _make_mock_rd()
        rd.InitialiseReplay.side_effect = RuntimeError("no local GPU")
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        with patch("rdc.daemon_server._init_adapter_state"):
            err = _load_remote_replay(state, "host:39920")

        assert err is None

    def test_init_replay_failure_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """B39: InitialiseReplay failure emits a warning log."""
        rd, _remote = _make_mock_rd()
        rd.InitialiseReplay.side_effect = RuntimeError("no local GPU")
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        with caplog.at_level(logging.WARNING, logger="rdc.daemon"):
            with patch("rdc.daemon_server._init_adapter_state"):
                _load_remote_replay(state, "host:39920")

        assert any("InitialiseReplay" in r.message for r in caplog.records)

    def test_connection_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd, _remote = _make_mock_rd(connect_result=1)
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)
        state = DaemonState(capture="/tmp/frame.rdc", current_eid=0, token="tok")
        err = _load_remote_replay(state, "host:39920")
        assert err is not None
        assert "remote connection failed" in err

    def test_local_file_uploads(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        rd, mock_remote = _make_mock_rd()
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        with patch("rdc.daemon_server._init_adapter_state"):
            err = _load_remote_replay(state, "host:39920")

        assert err is None
        args = mock_remote.CopyCaptureToRemote.call_args[0]
        assert args[0] == str(local_capture)
        assert callable(args[1])
        assert state.local_capture_path == str(local_capture)

    def test_remote_path_downloads(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        rd, mock_remote = _make_mock_rd()
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        state = DaemonState(capture="/remote/captures/frame.rdc", current_eid=0, token="tok12345")

        with patch("rdc.daemon_server._init_adapter_state"):
            err = _load_remote_replay(state, "host:39920")

        assert err is None
        mock_remote.CopyCaptureFromRemote.assert_called_once()
        assert state.local_capture_path != ""
        assert "rdc-remote-" in state.local_capture_path
        assert state.local_capture_is_temp

    def test_copy_from_remote_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd, mock_remote = _make_mock_rd()
        mock_remote.CopyCaptureFromRemote.side_effect = OSError("network error")
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        state = DaemonState(capture="/remote/captures/frame.rdc", current_eid=0, token="tok12345")
        err = _load_remote_replay(state, "host:39920")
        assert err is not None
        assert "at step 'download capture'" in err
        mock_remote.ShutdownConnection.assert_called_once()

    def test_open_capture_fails(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        rd, mock_remote = _make_mock_rd(open_capture_result=1)
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")
        err = _load_remote_replay(state, "host:39920")
        assert err is not None
        assert "remote OpenCapture failed" in err
        mock_remote.ShutdownConnection.assert_called_once()

    def test_local_openfile_fails(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        rd, mock_remote = _make_mock_rd(open_file_result=1)
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")
        err = _load_remote_replay(state, "host:39920")
        assert err is not None
        assert "local OpenFile (metadata) failed" in err
        mock_remote.CloseCapture.assert_called_once()
        mock_remote.ShutdownConnection.assert_called_once()

    def test_success_sets_state_fields(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rd, _mock_remote = _make_mock_rd()
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        with patch("rdc.daemon_server._init_adapter_state"):
            err = _load_remote_replay(state, "host:39920")

        assert err is None
        assert state.is_remote is True
        assert state.remote_url == "host:39920"
        assert state.adapter is not None
        assert state.cap is not None
        assert state._ping_thread is not None


class TestLoadRemoteReplayStepLabels:
    """T24 group C: step labels in remote replay setup failure messages."""

    def test_upload_capture_runtime_error_step_label(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rd, mock_remote = _make_mock_rd()
        mock_remote.CopyCaptureToRemote.side_effect = RuntimeError("upload bang")
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        err = _load_remote_replay(state, "host:39920")
        assert err is not None
        assert "at step 'upload capture'" in err
        assert "upload bang" in err
        mock_remote.ShutdownConnection.assert_called_once()

    def test_upload_capture_os_error_step_label(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rd, mock_remote = _make_mock_rd()
        mock_remote.CopyCaptureToRemote.side_effect = OSError("disk full")
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        err = _load_remote_replay(state, "host:39920")
        assert err is not None
        assert "at step 'upload capture'" in err
        assert "disk full" in err

    def test_gpu_probe_failure_is_non_fatal(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """GPU probe errors are swallowed into a warning; setup continues."""
        rd, _mock_remote = _make_mock_rd()
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        def _boom_match(_cap: Any, _sd: Any = None) -> Any:
            raise RuntimeError("gpu probe bang")

        monkeypatch.setattr("rdc.daemon_server._match_capture_gpu", _boom_match)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        with caplog.at_level(logging.WARNING, logger="rdc.daemon"):
            with patch("rdc.daemon_server._init_adapter_state"):
                err = _load_remote_replay(state, "host:39920")

        assert err is None
        assert any("GPU probe skipped" in r.message for r in caplog.records)

    def test_gpu_probe_tmp_cap_shutdown_on_openfile_success(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """T24 group E: tmp_cap.Shutdown runs after a successful OpenFile probe."""
        rd, _mock_remote = _make_mock_rd()
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        tmp_cap = MagicMock()
        tmp_cap.OpenFile.return_value = rd.ResultCode.Succeeded

        cap_for_metadata = MagicMock()
        cap_for_metadata.OpenFile.return_value = rd.ResultCode.Succeeded
        rd.OpenCaptureFile.side_effect = [tmp_cap, cap_for_metadata]

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        with patch("rdc.daemon_server._init_adapter_state"):
            err = _load_remote_replay(state, "host:39920")

        assert err is None
        tmp_cap.Shutdown.assert_called_once()

    def test_gpu_probe_tmp_cap_shutdown_on_openfile_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """T24 group E: tmp_cap.Shutdown still runs when OpenFile returns non-Succeeded."""
        rd, _mock_remote = _make_mock_rd()
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        tmp_cap = MagicMock()
        tmp_cap.OpenFile.return_value = 1  # anything != Succeeded (which is 0)

        cap_for_metadata = MagicMock()
        cap_for_metadata.OpenFile.return_value = rd.ResultCode.Succeeded
        rd.OpenCaptureFile.side_effect = [tmp_cap, cap_for_metadata]

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        with patch("rdc.daemon_server._init_adapter_state"):
            err = _load_remote_replay(state, "host:39920")

        assert err is None
        tmp_cap.Shutdown.assert_called_once()

    def test_gpu_probe_tmp_cap_shutdown_when_match_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """T24 group E: tmp_cap.Shutdown runs even when _match_capture_gpu raises."""
        rd, _mock_remote = _make_mock_rd()
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        tmp_cap = MagicMock()
        tmp_cap.OpenFile.return_value = rd.ResultCode.Succeeded

        cap_for_metadata = MagicMock()
        cap_for_metadata.OpenFile.return_value = rd.ResultCode.Succeeded
        rd.OpenCaptureFile.side_effect = [tmp_cap, cap_for_metadata]

        def _boom_match(_cap: Any, _sd: Any = None) -> Any:
            raise RuntimeError("gpu boom")

        monkeypatch.setattr("rdc.daemon_server._match_capture_gpu", _boom_match)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        with patch("rdc.daemon_server._init_adapter_state"):
            err = _load_remote_replay(state, "host:39920")

        assert err is None
        tmp_cap.Shutdown.assert_called_once()

    def test_outer_catchall_labels_init_adapter_state(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Unexpected exception in _init_adapter_state is wrapped with step label + type."""
        rd, mock_remote = _make_mock_rd()
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)

        def _boom(_state: Any) -> None:
            raise ValueError("adapter bang")

        monkeypatch.setattr("rdc.daemon_server._init_adapter_state", _boom)

        local_capture = tmp_path / "frame.rdc"
        local_capture.write_bytes(b"\x00")
        state = DaemonState(capture=str(local_capture), current_eid=0, token="tok12345")

        err = _load_remote_replay(state, "host:39920")
        assert err is not None
        assert "at step 'init adapter state'" in err
        assert "ValueError" in err
        assert "adapter bang" in err
        mock_remote.ShutdownConnection.assert_called_once()


class TestLoadReplayRegressionB39:
    """B39 regression: _load_replay must still fail on InitialiseReplay error."""

    def test_load_replay_still_fails_on_init_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd = MagicMock()
        rd.InitialiseReplay.side_effect = RuntimeError("init boom")
        monkeypatch.setattr("rdc.discover.find_renderdoc", lambda: rd)
        state = DaemonState(capture="/tmp/frame.rdc", current_eid=0, token="tok")
        err = _load_replay(state)
        assert err is not None
        assert "InitialiseReplay failed" in err


class TestPingThread:
    def test_start_sets_state(self) -> None:
        state = DaemonState(capture="frame.rdc", current_eid=0, token="tok")
        state.remote = MagicMock()
        _start_ping_thread(state)
        try:
            assert isinstance(state._ping_stop, threading.Event)
            assert isinstance(state._ping_thread, threading.Thread)
            assert state._ping_thread.is_alive()
        finally:
            _stop_ping_thread(state)

    def test_ping_exception_exits_loop(self) -> None:
        state = DaemonState(capture="frame.rdc", current_eid=0, token="tok")
        state.remote = MagicMock()
        state.remote.Ping.side_effect = OSError("disconnect")
        _start_ping_thread(state)
        # Thread waits 3s then calls Ping() which raises; join with enough margin
        state._ping_thread.join(timeout=5.0)
        assert not state._ping_thread.is_alive()

    def test_stop_signals_and_joins(self) -> None:
        state = DaemonState(capture="frame.rdc", current_eid=0, token="tok")
        state.remote = MagicMock()
        _start_ping_thread(state)
        _stop_ping_thread(state)
        assert state._ping_stop.is_set()
        assert not state._ping_thread.is_alive()

    def test_stop_noop_when_not_started(self) -> None:
        state = DaemonState(capture="frame.rdc", current_eid=0, token="tok")
        _stop_ping_thread(state)  # should not raise
