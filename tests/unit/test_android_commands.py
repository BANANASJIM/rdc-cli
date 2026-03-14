"""Tests for Android remote debug commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from rdc.cli import main
from rdc.commands.android import (
    _get_forwarded_port,
    android_group,
    android_setup_cmd,
    android_stop_cmd,
)
from rdc.remote_state import (
    RemoteServerState,
    load_latest_remote_state,
    save_remote_state,
)


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")


def _mock_rd_android(
    monkeypatch: pytest.MonkeyPatch,
    devices: list[str] | None = None,
    friendly_name: str = "Test Device",
    is_supported: bool = True,
    start_ok: bool = True,
    start_message: str = "",
    connect_ok: bool = True,
) -> tuple[MagicMock, MagicMock]:
    """Mock renderdoc module with Device Protocol API."""
    mock_ctrl = MagicMock()
    mock_ctrl.GetDevices.return_value = devices if devices is not None else []
    mock_ctrl.GetFriendlyName.return_value = friendly_name
    mock_ctrl.IsSupported.return_value = is_supported

    mock_start_result = MagicMock()
    mock_start_result.OK.return_value = start_ok
    mock_start_result.Message.return_value = start_message
    mock_ctrl.StartRemoteServer.return_value = mock_start_result

    mock_remote = MagicMock()
    mock_rd = MagicMock()
    mock_rd.GetDeviceProtocolController.return_value = mock_ctrl

    if connect_ok:
        mock_rd.CreateRemoteServerConnection.return_value = (0, mock_remote)
    else:
        mock_rd.CreateRemoteServerConnection.return_value = (6, None)

    monkeypatch.setattr("rdc.commands.android.find_renderdoc", lambda: mock_rd)
    return mock_rd, mock_ctrl


# --- android setup ---


class TestAndroidSetup:
    def test_single_device(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd, ctrl = _mock_rd_android(monkeypatch, devices=["adb://ABC123"], friendly_name="Pixel 7")
        result = CliRunner().invoke(android_setup_cmd, [])
        assert result.exit_code == 0
        assert "Pixel 7" in result.output
        assert "adb://ABC123" in result.output
        ctrl.StartRemoteServer.assert_called_once_with("adb://ABC123")
        rd.CreateRemoteServerConnection.assert_called_once_with("adb://ABC123")

    def test_json_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd_android(monkeypatch, devices=["adb://ABC123"], friendly_name="Pixel 7")
        result = CliRunner().invoke(android_setup_cmd, ["--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["device"] == "Pixel 7"
        assert data["url"] == "adb://ABC123"
        assert data["connected"] is True

    def test_state_persisted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd_android(monkeypatch, devices=["adb://ABC123"])
        CliRunner().invoke(android_setup_cmd, [])
        state = load_latest_remote_state()
        assert state is not None
        assert state.host == "adb://ABC123"
        assert state.port == 0
        assert state.connected_at > 0

    def test_no_renderdoc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands.android.find_renderdoc", lambda: None)
        result = CliRunner().invoke(android_setup_cmd, [])
        assert result.exit_code == 1

    def test_no_devices(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd_android(monkeypatch, devices=[])
        result = CliRunner().invoke(android_setup_cmd, [])
        assert result.exit_code == 1

    def test_multi_no_serial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd_android(monkeypatch, devices=["adb://AAA", "adb://BBB"])
        result = CliRunner().invoke(android_setup_cmd, [])
        assert result.exit_code == 1
        assert "--serial" in result.output

    def test_multi_with_serial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, ctrl = _mock_rd_android(monkeypatch, devices=["adb://AAA", "adb://BBB"])
        result = CliRunner().invoke(android_setup_cmd, ["--serial", "BBB"])
        assert result.exit_code == 0
        ctrl.StartRemoteServer.assert_called_once_with("adb://BBB")

    def test_serial_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd_android(monkeypatch, devices=["adb://AAA", "adb://BBB"])
        result = CliRunner().invoke(android_setup_cmd, ["--serial", "ZZZ"])
        assert result.exit_code == 1
        assert "ZZZ" in result.output

    def test_device_unsupported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd_android(monkeypatch, devices=["adb://ABC123"], is_supported=False)
        result = CliRunner().invoke(android_setup_cmd, [])
        assert result.exit_code == 1

    def test_start_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd_android(
            monkeypatch,
            devices=["adb://ABC123"],
            start_ok=False,
            start_message="APK install failed",
        )
        result = CliRunner().invoke(android_setup_cmd, [])
        assert result.exit_code == 1
        assert "APK install failed" in result.output

    def test_connect_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd_android(monkeypatch, devices=["adb://ABC123"], connect_ok=False)
        result = CliRunner().invoke(android_setup_cmd, [])
        assert result.exit_code == 1


# --- android stop ---


class TestAndroidStop:
    def test_happy_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, ctrl = _mock_rd_android(monkeypatch, devices=["adb://ABC123"])
        save_remote_state(RemoteServerState(host="adb://ABC123", port=0, connected_at=1000.0))
        result = CliRunner().invoke(android_stop_cmd, [])
        assert result.exit_code == 0
        ctrl.StopRemoteServer.assert_called_once_with("adb://ABC123")
        assert load_latest_remote_state() is None

    def test_no_stop_method(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, ctrl = _mock_rd_android(monkeypatch, devices=["adb://ABC123"])
        del ctrl.StopRemoteServer
        save_remote_state(RemoteServerState(host="adb://ABC123", port=0, connected_at=1000.0))
        result = CliRunner().invoke(android_stop_cmd, [])
        assert result.exit_code == 0
        assert load_latest_remote_state() is None

    def test_stop_with_serial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, ctrl = _mock_rd_android(monkeypatch, devices=["adb://AAA", "adb://BBB"])
        result = CliRunner().invoke(android_stop_cmd, ["--serial", "BBB"])
        assert result.exit_code == 0
        ctrl.StopRemoteServer.assert_called_once_with("adb://BBB")

    def test_no_renderdoc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands.android.find_renderdoc", lambda: None)
        result = CliRunner().invoke(android_stop_cmd, [])
        assert result.exit_code == 1

    def test_no_devices(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_rd_android(monkeypatch, devices=[])
        result = CliRunner().invoke(android_stop_cmd, [])
        assert result.exit_code == 1


# --- Mali GPU detection ---


class TestMaliDetection:
    def test_mali_friendly_name_upstream_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd, _ = _mock_rd_android(
            monkeypatch,
            devices=["adb://ABC123"],
            friendly_name="Mali-G78 Device",
        )
        rd.GetVersionString.return_value = "1.41"
        result = CliRunner().invoke(android_setup_cmd, [])
        assert result.exit_code == 0
        assert "ARM Performance Studio" in result.output

    def test_mali_platform_prop_upstream_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd, _ = _mock_rd_android(
            monkeypatch,
            devices=["adb://ABC123"],
            friendly_name="Unknown Device",
        )
        rd.GetVersionString.return_value = "1.41"

        mock_proc = MagicMock()
        mock_proc.stdout = "orlando\n"

        with (
            patch("rdc.commands.android.shutil.which", return_value="/usr/bin/adb"),
            patch("rdc.commands.android.subprocess.run", return_value=mock_proc),
        ):
            result = CliRunner().invoke(android_setup_cmd, [])

        assert result.exit_code == 0
        assert "ARM Performance Studio" in result.output

    def test_mali_arm_fork_no_warn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd, _ = _mock_rd_android(
            monkeypatch,
            devices=["adb://ABC123"],
            friendly_name="Mali-G78 Device",
        )
        rd.GetVersionString.return_value = "2025.4"
        result = CliRunner().invoke(android_setup_cmd, [])
        assert result.exit_code == 0
        assert "ARM Performance Studio" not in result.output

    def test_adreno_no_warn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd, _ = _mock_rd_android(
            monkeypatch,
            devices=["adb://ABC123"],
            friendly_name="Adreno 740",
        )
        rd.GetVersionString.return_value = "1.41"
        result = CliRunner().invoke(android_setup_cmd, [])
        assert result.exit_code == 0
        assert "ARM Performance Studio" not in result.output


# --- CLI registration ---


class TestCliRegistration:
    def test_android_group_help(self) -> None:
        result = CliRunner().invoke(android_group, ["--help"])
        assert result.exit_code == 0
        assert "setup" in result.output
        assert "stop" in result.output

    def test_android_setup_help(self) -> None:
        result = CliRunner().invoke(main, ["android", "setup", "--help"])
        assert result.exit_code == 0
        assert "--serial" in result.output

    def test_main_android_help(self) -> None:
        result = CliRunner().invoke(main, ["android", "--help"])
        assert result.exit_code == 0
        assert "setup" in result.output
        assert "stop" in result.output


# --- forwarded port detection ---


class TestGetForwardedPort:
    def test_parses_forward_list(self) -> None:
        mock_proc = MagicMock()
        mock_proc.stdout = "ABC123 tcp:12345 tcp:39920\n"
        with (
            patch("rdc.commands.android.shutil.which", return_value="/usr/bin/adb"),
            patch("rdc.commands.android.subprocess.run", return_value=mock_proc),
        ):
            port = _get_forwarded_port(None, "adb://ABC123")
        assert port == 12345

    def test_no_match(self) -> None:
        mock_proc = MagicMock()
        mock_proc.stdout = "ABC123 tcp:12345 tcp:9999\n"
        with (
            patch("rdc.commands.android.shutil.which", return_value="/usr/bin/adb"),
            patch("rdc.commands.android.subprocess.run", return_value=mock_proc),
        ):
            port = _get_forwarded_port(None, "adb://ABC123")
        assert port is None

    def test_no_adb(self) -> None:
        with patch("rdc.commands.android.shutil.which", return_value=None):
            port = _get_forwarded_port(None, "adb://ABC123")
        assert port is None

    def test_uses_serial(self) -> None:
        mock_proc = MagicMock()
        mock_proc.stdout = "XYZ tcp:54321 tcp:39920\n"
        with (
            patch("rdc.commands.android.shutil.which", return_value="/usr/bin/adb"),
            patch("rdc.commands.android.subprocess.run", return_value=mock_proc) as m,
        ):
            port = _get_forwarded_port("XYZ", "adb://XYZ")
        assert port == 54321
        args = m.call_args[0][0]
        assert "-s" in args
        assert "XYZ" in args

    def test_setup_uses_forwarded_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd, _ = _mock_rd_android(
            monkeypatch,
            devices=["adb://ABC123"],
            friendly_name="Pixel 7",
        )
        monkeypatch.setattr(
            "rdc.commands.android._get_forwarded_port",
            lambda s, u: 12345,
        )
        CliRunner().invoke(android_setup_cmd, [])
        rd.CreateRemoteServerConnection.assert_called_once_with("localhost:12345")

    def test_setup_falls_back_to_adb_url(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rd, _ = _mock_rd_android(
            monkeypatch,
            devices=["adb://ABC123"],
            friendly_name="Pixel 7",
        )
        monkeypatch.setattr(
            "rdc.commands.android._get_forwarded_port",
            lambda s, u: None,
        )
        CliRunner().invoke(android_setup_cmd, [])
        rd.CreateRemoteServerConnection.assert_called_once_with("adb://ABC123")
