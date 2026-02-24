"""Tests for --keep-remote flag on remote capture."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from rdc.capture_core import CaptureResult
from rdc.commands.remote import remote_capture_cmd
from rdc.remote_state import RemoteServerState, save_remote_state


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")


def _save_state() -> None:
    save_remote_state(RemoteServerState(host="192.168.1.10", port=39920, connected_at=1000.0))


def _mock_rd(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    rd = MagicMock()
    monkeypatch.setattr("rdc.commands._helpers.find_renderdoc", lambda: rd)
    return rd


class TestKeepRemoteFlag:
    def test_keep_remote_passes_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        captured_kw: list[dict[str, Any]] = []

        def fake_remote_capture(*a: Any, **kw: Any) -> CaptureResult:
            captured_kw.append(kw)
            return CaptureResult(
                success=True, path="/remote/frame.rdc", remote_path="/remote/frame.rdc"
            )

        monkeypatch.setattr("rdc.commands.remote.remote_capture", fake_remote_capture)

        result = CliRunner().invoke(
            remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc", "--keep-remote"]
        )
        assert result.exit_code == 0
        assert captured_kw[0]["keep_remote"] is True

    def test_keep_remote_prints_remote_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        monkeypatch.setattr(
            "rdc.commands.remote.remote_capture",
            lambda *a, **kw: CaptureResult(
                success=True,
                path="/remote/frame.rdc",
                remote_path="/remote/frame.rdc",
            ),
        )

        result = CliRunner().invoke(
            remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc", "--keep-remote"]
        )
        assert result.exit_code == 0
        assert "/remote/frame.rdc" in result.output

    def test_keep_remote_prints_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        monkeypatch.setattr(
            "rdc.commands.remote.remote_capture",
            lambda *a, **kw: CaptureResult(
                success=True,
                path="/remote/frame.rdc",
                remote_path="/remote/frame.rdc",
            ),
        )

        result = CliRunner().invoke(
            remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc", "--keep-remote"]
        )
        assert result.exit_code == 0
        assert "rdc open --remote" in result.output

    def test_no_keep_remote_prints_local_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        monkeypatch.setattr(
            "rdc.commands.remote.remote_capture",
            lambda *a, **kw: CaptureResult(success=True, path="/tmp/out.rdc"),
        )

        result = CliRunner().invoke(remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc"])
        assert result.exit_code == 0
        assert "/tmp/out.rdc" in result.output
        assert "rdc open --remote" not in result.output


class TestRemoteCoreKeepRemote:
    def test_keep_remote_skips_copy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """remote_capture with keep_remote=True skips CopyCaptureFromRemote."""
        from rdc.remote_core import remote_capture

        rd = MagicMock()
        monkeypatch.setattr("rdc.capture_core.find_renderdoc", lambda: rd)
        remote = MagicMock()

        exec_result = MagicMock()
        exec_result.result = 0
        exec_result.ident = 42
        remote.ExecuteAndInject.return_value = exec_result

        tc = MagicMock()
        tc.Connected.return_value = True
        msg = MagicMock()
        msg.type = 4
        nc = MagicMock()
        nc.path = "/remote/tmp/frame.rdc"
        nc.frameNumber = 0
        nc.byteSize = 1024
        nc.api = "Vulkan"
        nc.local = False
        msg.newCapture = nc
        tc.ReceiveMessage.return_value = msg
        rd.CreateTargetControl.return_value = tc

        # Mock build_capture_options
        rd.GetDefaultCaptureOptions.return_value = MagicMock()

        result = remote_capture(
            rd,
            remote,
            "host:39920",
            "/app",
            output="/tmp/out.rdc",
            keep_remote=True,
        )
        assert result.success
        assert result.remote_path == "/remote/tmp/frame.rdc"
        remote.CopyCaptureFromRemote.assert_not_called()

    def test_no_keep_remote_copies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """remote_capture without keep_remote calls CopyCaptureFromRemote."""
        from rdc.remote_core import remote_capture

        rd = MagicMock()
        monkeypatch.setattr("rdc.capture_core.find_renderdoc", lambda: rd)
        remote = MagicMock()

        exec_result = MagicMock()
        exec_result.result = 0
        exec_result.ident = 42
        remote.ExecuteAndInject.return_value = exec_result

        tc = MagicMock()
        tc.Connected.return_value = True
        msg = MagicMock()
        msg.type = 4
        nc = MagicMock()
        nc.path = "/remote/tmp/frame.rdc"
        nc.frameNumber = 0
        nc.byteSize = 1024
        nc.api = "Vulkan"
        nc.local = False
        msg.newCapture = nc
        tc.ReceiveMessage.return_value = msg
        rd.CreateTargetControl.return_value = tc

        rd.GetDefaultCaptureOptions.return_value = MagicMock()

        result = remote_capture(
            rd,
            remote,
            "host:39920",
            "/app",
            output="/tmp/out.rdc",
            keep_remote=False,
        )
        assert result.success
        assert result.remote_path == ""
        remote.CopyCaptureFromRemote.assert_called_once()
