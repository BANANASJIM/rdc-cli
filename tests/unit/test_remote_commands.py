"""Tests for remote CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from rdc.capture_core import CaptureResult
from rdc.commands.remote import (
    remote_capture_cmd,
    remote_connect_cmd,
    remote_group,
    remote_list_cmd,
)
from rdc.remote_state import RemoteServerState, save_remote_state


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")


def _mock_rd(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Provide a mock renderdoc module and patch find_renderdoc."""
    rd = MagicMock()
    monkeypatch.setattr("rdc.commands._helpers.find_renderdoc", lambda: rd)
    return rd


def _save_state() -> None:
    save_remote_state(RemoteServerState(host="192.168.1.10", port=39920, connected_at=1000.0))


def _mock_remote_connection(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    remote = MagicMock()
    monkeypatch.setattr("rdc.commands.remote.connect_remote_server", lambda rd, url: remote)
    return remote


# --- remote connect ---


class TestRemoteConnect:
    def test_success_saves_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd(monkeypatch)
        mock_remote = MagicMock()
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: mock_remote,
        )

        result = CliRunner().invoke(remote_connect_cmd, ["192.168.1.10"])
        assert result.exit_code == 0
        assert "connected" in result.output
        assert "192.168.1.10:39920" in result.output
        mock_remote.ShutdownConnection.assert_called_once()

    def test_success_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )

        result = CliRunner().invoke(remote_connect_cmd, ["192.168.1.10", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["host"] == "192.168.1.10"
        assert data["port"] == 39920

    def test_failure_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            MagicMock(side_effect=RuntimeError("connection failed (code 1)")),
        )

        result = CliRunner().invoke(remote_connect_cmd, ["192.168.1.10"])
        assert result.exit_code == 1

    def test_no_renderdoc_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands._helpers.find_renderdoc", lambda: None)
        result = CliRunner().invoke(remote_connect_cmd, ["192.168.1.10"])
        assert result.exit_code == 1

    def test_public_ip_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        stderr_lines: list[str] = []
        orig_echo = click.echo

        def spy_echo(message: Any = None, err: bool = False, **kw: Any) -> Any:
            if err:
                stderr_lines.append(str(message))
            return orig_echo(message, err=err, **kw)

        monkeypatch.setattr("rdc.commands.remote.click.echo", spy_echo)
        result = CliRunner().invoke(remote_connect_cmd, ["8.8.8.8"])
        assert result.exit_code == 0
        assert any("not a private IP" in s for s in stderr_lines)

    def test_private_ip_no_warn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        stderr_lines: list[str] = []
        orig_echo = click.echo

        def spy_echo(message: Any = None, err: bool = False, **kw: Any) -> Any:
            if err:
                stderr_lines.append(str(message))
            return orig_echo(message, err=err, **kw)

        monkeypatch.setattr("rdc.commands.remote.click.echo", spy_echo)
        result = CliRunner().invoke(remote_connect_cmd, ["192.168.1.10"])
        assert result.exit_code == 0
        assert not any("not a private IP" in s for s in stderr_lines)

    def test_custom_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd(monkeypatch)
        captured_urls: list[str] = []

        def fake_connect(rd: Any, url: str) -> MagicMock:
            captured_urls.append(url)
            return MagicMock()

        monkeypatch.setattr("rdc.commands.remote.connect_remote_server", fake_connect)
        result = CliRunner().invoke(remote_connect_cmd, ["myhost:12345"])
        assert result.exit_code == 0
        assert "myhost:12345" in captured_urls[0]

    def test_split_mode_routes_rpc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands.remote.split_session_active", lambda: True)
        called: dict[str, Any] = {}

        def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
            called["method"] = method
            called["params"] = params
            return {}

        monkeypatch.setattr("rdc.commands.remote.call", fake_call)
        result = CliRunner().invoke(remote_connect_cmd, ["192.168.1.10"])
        assert result.exit_code == 0
        assert called["method"] == "remote_connect_run"
        assert called["params"] == {"host": "192.168.1.10", "port": 39920}


# --- remote list ---


class TestRemoteList:
    def test_no_targets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        _mock_rd(monkeypatch)
        _mock_remote_connection(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote.enumerate_remote_targets", lambda rd, url: [])

        result = CliRunner().invoke(remote_list_cmd, [])
        assert result.exit_code == 0
        assert "no targets found" in result.output

    def test_one_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        rd = _mock_rd(monkeypatch)
        _mock_remote_connection(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote.enumerate_remote_targets", lambda rd, url: [1])

        tc = MagicMock()
        tc.GetTarget.return_value = "myapp"
        tc.GetPID.return_value = 12345
        tc.GetAPI.return_value = "Vulkan"
        rd.CreateTargetControl.return_value = tc

        result = CliRunner().invoke(remote_list_cmd, [])
        assert result.exit_code == 0
        assert "ident=1" in result.output
        assert "myapp" in result.output

    def test_multiple_targets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        rd = _mock_rd(monkeypatch)
        _mock_remote_connection(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.enumerate_remote_targets", lambda rd, url: [1, 2, 3]
        )

        tc = MagicMock()
        tc.GetTarget.return_value = "app"
        tc.GetPID.return_value = 100
        tc.GetAPI.return_value = "Vulkan"
        rd.CreateTargetControl.return_value = tc

        result = CliRunner().invoke(remote_list_cmd, [])
        assert result.exit_code == 0
        assert result.output.count("ident=") == 3

    def test_json_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        rd = _mock_rd(monkeypatch)
        _mock_remote_connection(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote.enumerate_remote_targets", lambda rd, url: [1])

        tc = MagicMock()
        tc.GetTarget.return_value = "myapp"
        tc.GetPID.return_value = 12345
        tc.GetAPI.return_value = "Vulkan"
        rd.CreateTargetControl.return_value = tc

        result = CliRunner().invoke(remote_list_cmd, ["--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["targets"]) == 1
        assert data["targets"][0]["target"] == "myapp"

    def test_no_saved_state_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd(monkeypatch)
        result = CliRunner().invoke(remote_list_cmd, [])
        assert result.exit_code == 1

    def test_url_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # No saved state but --url provided
        _mock_rd(monkeypatch)
        _mock_remote_connection(monkeypatch)
        captured_urls: list[str] = []

        def fake_enum(rd: Any, url: str) -> list[int]:
            captured_urls.append(url)
            return []

        monkeypatch.setattr("rdc.commands.remote.enumerate_remote_targets", fake_enum)

        result = CliRunner().invoke(remote_list_cmd, ["--url", "host2:39920"])
        assert result.exit_code == 0
        assert "host2:39920" in captured_urls[0]

    def test_no_renderdoc_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        monkeypatch.setattr("rdc.commands._helpers.find_renderdoc", lambda: None)
        result = CliRunner().invoke(remote_list_cmd, [])
        assert result.exit_code == 1

    def test_tc_connect_failure_skips_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        rd = _mock_rd(monkeypatch)
        _mock_remote_connection(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote.enumerate_remote_targets", lambda rd, url: [1])
        rd.CreateTargetControl.return_value = None

        result = CliRunner().invoke(remote_list_cmd, [])
        assert result.exit_code == 0
        assert "unknown" in result.output

    def test_split_mode_uses_rpc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        monkeypatch.setattr("rdc.commands.remote.split_session_active", lambda: True)
        response = {"targets": [{"ident": 1, "target": "demo", "pid": 42, "api": "Vulkan"}]}
        calls: list[tuple[str, dict[str, Any]]] = []

        def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
            calls.append((method, params))
            if method == "remote_connect_run":
                return {"host": "192.168.1.10", "port": 39920}
            return response

        monkeypatch.setattr("rdc.commands.remote.call", fake_call)

        result = CliRunner().invoke(remote_list_cmd, [])
        assert result.exit_code == 0
        assert "demo" in result.output
        assert calls == [
            ("remote_connect_run", {"host": "192.168.1.10", "port": 39920}),
            ("remote_list_run", {"host": "192.168.1.10", "port": 39920}),
        ]

    def test_unreachable_url_reports_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            MagicMock(side_effect=RuntimeError("connection failed: timeout")),
        )

        result = CliRunner().invoke(remote_list_cmd, ["--url", "bad.host:39920"])
        assert result.exit_code == 1
        assert "error: connection failed: timeout" in result.output
        assert "no targets found" not in result.output


# --- remote capture ---


class TestRemoteCapture:
    def test_success_prints_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

    def test_success_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

        result = CliRunner().invoke(remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True

    def test_no_output_exits_error(self) -> None:
        result = CliRunner().invoke(remote_capture_cmd, ["myapp"])
        assert result.exit_code != 0

    def test_no_saved_state_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd(monkeypatch)
        result = CliRunner().invoke(remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc"])
        assert result.exit_code == 1

    def test_connect_fails_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            MagicMock(side_effect=RuntimeError("connection failed")),
        )

        result = CliRunner().invoke(remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc"])
        assert result.exit_code == 1

    def test_inject_fails_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        monkeypatch.setattr(
            "rdc.commands.remote.remote_capture",
            lambda *a, **kw: CaptureResult(error="inject failed"),
        )

        result = CliRunner().invoke(remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc"])
        assert result.exit_code == 1

    def test_url_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # No saved state, use --url
        _mock_rd(monkeypatch)
        captured_urls: list[str] = []

        def fake_connect(rd: Any, url: str) -> MagicMock:
            captured_urls.append(url)
            return MagicMock()

        monkeypatch.setattr("rdc.commands.remote.connect_remote_server", fake_connect)
        monkeypatch.setattr(
            "rdc.commands.remote.remote_capture",
            lambda *a, **kw: CaptureResult(success=True, path="/tmp/out.rdc"),
        )

        result = CliRunner().invoke(
            remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc", "--url", "otherhost:12345"]
        )
        assert result.exit_code == 0
        assert "otherhost:12345" in captured_urls[0]

    def test_frame_option(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        captured_kw: list[dict[str, Any]] = []

        def fake_remote_capture(*a: Any, **kw: Any) -> CaptureResult:
            captured_kw.append(kw)
            return CaptureResult(success=True, path="/tmp/out.rdc")

        monkeypatch.setattr("rdc.commands.remote.remote_capture", fake_remote_capture)

        result = CliRunner().invoke(
            remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc", "--frame", "10"]
        )
        assert result.exit_code == 0
        assert captured_kw[0]["frame"] == 10

    def test_capture_options_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        captured_kw: list[dict[str, Any]] = []

        def fake_remote_capture(*a: Any, **kw: Any) -> CaptureResult:
            captured_kw.append(kw)
            return CaptureResult(success=True, path="/tmp/out.rdc")

        monkeypatch.setattr("rdc.commands.remote.remote_capture", fake_remote_capture)

        result = CliRunner().invoke(
            remote_capture_cmd,
            ["myapp", "-o", "/tmp/out.rdc", "--api-validation", "--callstacks"],
        )
        assert result.exit_code == 0
        assert captured_kw[0]["opts"] == {"api_validation": True, "callstacks": True}

    def test_no_renderdoc_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _save_state()
        monkeypatch.setattr("rdc.commands._helpers.find_renderdoc", lambda: None)
        result = CliRunner().invoke(remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc"])
        assert result.exit_code == 1

    def test_public_ip_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        monkeypatch.setattr(
            "rdc.commands.remote.remote_capture",
            lambda *a, **kw: CaptureResult(success=True, path="/tmp/out.rdc"),
        )
        stderr_lines: list[str] = []
        orig_echo = click.echo

        def spy_echo(message: Any = None, err: bool = False, **kw: Any) -> Any:
            if err:
                stderr_lines.append(str(message))
            return orig_echo(message, err=err, **kw)

        monkeypatch.setattr("rdc.commands.remote.click.echo", spy_echo)
        result = CliRunner().invoke(
            remote_capture_cmd, ["myapp", "-o", "/tmp/out.rdc", "--url", "8.8.8.8"]
        )
        assert result.exit_code == 0
        assert any("not a private IP" in s for s in stderr_lines)

    def test_split_mode_calls_rpc(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _save_state()
        monkeypatch.setattr("rdc.commands.remote.split_session_active", lambda: True)
        captured: dict[str, Any] = {}

        def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
            captured["method"] = method
            captured["params"] = params
            return {
                "success": True,
                "path": "/daemon/tmp/out.rdc",
                "frame": 0,
                "byte_size": 0,
                "api": "Vulkan",
                "local": True,
                "ident": 0,
                "pid": 0,
                "error": "",
                "remote_path": "",
            }

        monkeypatch.setattr("rdc.commands.remote.call", fake_call)
        monkeypatch.setattr("rdc.commands._helpers.fetch_remote_file", lambda path: b"data")
        out_path = tmp_path / "out.rdc"
        result = CliRunner().invoke(remote_capture_cmd, ["myapp", "-o", str(out_path)])
        assert result.exit_code == 0
        assert captured["method"] == "remote_capture_run"
        assert captured["params"]["app"] == "myapp"
        assert out_path.exists()
        assert out_path.read_bytes() == b"data"


# --- CLI registration ---


class TestCliRegistration:
    def test_remote_group_registered(self) -> None:
        result = CliRunner().invoke(remote_group, ["--help"])
        assert result.exit_code == 0
        assert "connect" in result.output
        assert "list" in result.output
        assert "capture" in result.output

    def test_remote_connect_help(self) -> None:
        result = CliRunner().invoke(remote_connect_cmd, ["--help"])
        assert result.exit_code == 0

    def test_remote_list_help(self) -> None:
        result = CliRunner().invoke(remote_list_cmd, ["--help"])
        assert result.exit_code == 0

    def test_remote_capture_help(self) -> None:
        result = CliRunner().invoke(remote_capture_cmd, ["--help"])
        assert result.exit_code == 0
