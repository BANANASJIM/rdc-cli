"""Tests for Android remote debug commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from rdc.capture_core import CaptureResult
from rdc.cli import main
from rdc.commands.android import (
    _adb,
    _cleanup_device,
    _clear_gpu_debug_layers,
    _get_app_pid,
    _get_forwarded_port,
    _resolve_serial,
    _set_gpu_debug_layers,
    _wait_for_renderdoc_init,
    android_capture_cmd,
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


# --- _adb helper ---


class TestAdb:
    def test_runs_command(self) -> None:
        mock_proc = MagicMock(stdout="ok\n", stderr="", returncode=0)
        with (
            patch("rdc.commands.android.shutil.which", return_value="/usr/bin/adb"),
            patch("rdc.commands.android.subprocess.run", return_value=mock_proc) as m,
        ):
            result = _adb("ABC123", "shell", "echo", "hello")
        assert result is mock_proc
        m.assert_called_once()
        cmd = m.call_args[0][0]
        assert cmd == ["adb", "-s", "ABC123", "shell", "echo", "hello"]

    def test_no_adb_raises(self) -> None:
        with (
            patch("rdc.commands.android.shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="adb not found"),
        ):
            _adb("ABC123", "shell", "ls")

    def test_timeout_raises(self) -> None:
        import subprocess

        with (
            patch("rdc.commands.android.shutil.which", return_value="/usr/bin/adb"),
            patch(
                "rdc.commands.android.subprocess.run",
                side_effect=subprocess.TimeoutExpired("adb", 10),
            ),
            pytest.raises(RuntimeError, match="timed out"),
        ):
            _adb("ABC123", "shell", "ls")


# --- _resolve_serial ---


class TestResolveSerial:
    def test_returns_given_serial(self) -> None:
        assert _resolve_serial("ABC123") == "ABC123"

    def test_auto_single_device(self) -> None:
        mock_proc = MagicMock(stdout="List of devices attached\nABC123\tdevice\n")
        with (
            patch("rdc.commands.android.shutil.which", return_value="/usr/bin/adb"),
            patch("rdc.commands.android.subprocess.run", return_value=mock_proc),
        ):
            assert _resolve_serial(None) == "ABC123"

    def test_no_adb(self) -> None:
        with (
            patch("rdc.commands.android.shutil.which", return_value=None),
            pytest.raises(SystemExit),
        ):
            _resolve_serial(None)

    def test_no_devices(self) -> None:
        mock_proc = MagicMock(stdout="List of devices attached\n\n")
        with (
            patch("rdc.commands.android.shutil.which", return_value="/usr/bin/adb"),
            patch("rdc.commands.android.subprocess.run", return_value=mock_proc),
            pytest.raises(SystemExit),
        ):
            _resolve_serial(None)

    def test_multiple_devices(self) -> None:
        mock_proc = MagicMock(
            stdout="List of devices attached\nAAA\tdevice\nBBB\tdevice\n",
        )
        with (
            patch("rdc.commands.android.shutil.which", return_value="/usr/bin/adb"),
            patch("rdc.commands.android.subprocess.run", return_value=mock_proc),
            pytest.raises(SystemExit),
        ):
            _resolve_serial(None)


# --- GPU debug layer helpers ---


class TestGpuDebugLayers:
    def test_set_gpu_debug_layers(self) -> None:
        calls: list[list[str]] = []

        def fake_adb(serial: str, *args: str, timeout: int = 10) -> MagicMock:
            calls.append([serial, *args])
            return MagicMock(stdout="", returncode=0)

        with patch("rdc.commands.android._adb", side_effect=fake_adb):
            _set_gpu_debug_layers("ABC123", "com.example.app")

        # Should set gpu_debug_app first, then the 4 layer settings
        assert len(calls) == 5
        assert calls[0][2] == "settings"
        assert "gpu_debug_app" in calls[0]
        assert "com.example.app" in calls[0]

    def test_clear_gpu_debug_layers(self) -> None:
        calls: list[list[str]] = []

        def fake_adb(serial: str, *args: str, timeout: int = 10) -> MagicMock:
            calls.append([serial, *args])
            return MagicMock(stdout="", returncode=0)

        with patch("rdc.commands.android._adb", side_effect=fake_adb):
            _clear_gpu_debug_layers("ABC123")

        # 4 layer settings + gpu_debug_app
        assert len(calls) == 5
        assert all("delete" in c for c in calls)


class TestCleanupDevice:
    def test_kills_and_removes_forwards(self) -> None:
        calls: list[list[str]] = []

        def fake_adb(serial: str, *args: str, timeout: int = 10) -> MagicMock:
            calls.append([serial, *args])
            return MagicMock(stdout="", returncode=0)

        with patch("rdc.commands.android._adb", side_effect=fake_adb):
            _cleanup_device("ABC123")

        assert len(calls) == 2
        assert "pkill" in calls[0]
        assert "forward" in calls[1] and "--remove-all" in calls[1]


class TestGetAppPid:
    def test_returns_pid(self) -> None:
        mock_proc = MagicMock(stdout="12345\n")
        with patch("rdc.commands.android._adb", return_value=mock_proc):
            pid = _get_app_pid("ABC123", "com.example.app", timeout=0.1)
        assert pid == 12345

    def test_returns_zero_on_timeout(self) -> None:
        mock_proc = MagicMock(stdout="")
        with patch("rdc.commands.android._adb", return_value=mock_proc):
            pid = _get_app_pid("ABC123", "com.example.app", timeout=0.1)
        assert pid == 0


class TestWaitForRenderdocInit:
    def test_detects_init(self) -> None:
        mock_proc = MagicMock(stdout="RenderDoc: Listening for target control on port 38920\n")
        with patch("rdc.commands.android._adb", return_value=mock_proc):
            assert _wait_for_renderdoc_init("ABC123", 12345, timeout=0.1) is True

    def test_timeout_returns_false(self) -> None:
        mock_proc = MagicMock(stdout="no relevant logs\n")
        with patch("rdc.commands.android._adb", return_value=mock_proc):
            assert _wait_for_renderdoc_init("ABC123", 12345, timeout=0.1) is False


# --- android capture ---


class TestAndroidCapture:
    def _setup_capture_mocks(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        """Set up mocks for the android capture command."""
        mock_rd = MagicMock()
        monkeypatch.setattr("rdc.commands.android.find_renderdoc", lambda: mock_rd)
        monkeypatch.setattr(
            "rdc.commands.android._resolve_serial",
            lambda s: "ABC123",
        )
        monkeypatch.setattr(
            "rdc.commands.android._cleanup_device",
            lambda s: None,
        )
        monkeypatch.setattr(
            "rdc.commands.android._set_gpu_debug_layers",
            lambda s, p: None,
        )
        monkeypatch.setattr(
            "rdc.commands.android._clear_gpu_debug_layers",
            lambda s: None,
        )
        monkeypatch.setattr(
            "rdc.commands.android._adb",
            lambda s, *a, timeout=10: MagicMock(stdout="", returncode=0),
        )
        monkeypatch.setattr(
            "rdc.commands.android._get_app_pid",
            lambda s, p, timeout=10.0: 12345,
        )
        monkeypatch.setattr(
            "rdc.commands.android._wait_for_renderdoc_init",
            lambda s, pid, timeout=15.0: True,
        )
        monkeypatch.setattr(
            "rdc.commands.android._forward_target_control",
            lambda s, port=38920: port,
        )

        mock_tc = MagicMock()
        mock_rd.CreateTargetControl.return_value = mock_tc

        monkeypatch.setattr(
            "rdc.commands.android.run_target_control_loop",
            lambda tc, timeout=60.0: CaptureResult(
                success=True,
                path="/tmp/test.rdc",
                local=True,
            ),
        )
        return mock_rd

    def test_happy_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._setup_capture_mocks(monkeypatch)
        out = tmp_path / "out.rdc"
        result = CliRunner().invoke(
            android_capture_cmd,
            ["com.example.app/.MainActivity", "-o", str(out)],
        )
        assert result.exit_code == 0

    def test_json_output(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._setup_capture_mocks(monkeypatch)
        out = tmp_path / "out.rdc"
        result = CliRunner().invoke(
            android_capture_cmd,
            ["com.example.app/.MainActivity", "-o", str(out), "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True

    def test_default_output_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._setup_capture_mocks(monkeypatch)
        result = CliRunner().invoke(
            android_capture_cmd,
            ["com.example.app/.MainActivity"],
        )
        assert result.exit_code == 0

    def test_no_renderdoc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands.android.find_renderdoc", lambda: None)
        result = CliRunner().invoke(
            android_capture_cmd,
            ["com.example.app/.MainActivity"],
        )
        assert result.exit_code == 1

    def test_app_not_started(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._setup_capture_mocks(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.android._get_app_pid",
            lambda s, p, timeout=10.0: 0,
        )
        result = CliRunner().invoke(
            android_capture_cmd,
            ["com.example.app/.MainActivity"],
        )
        assert result.exit_code == 1
        assert "did not start" in result.output

    def test_renderdoc_init_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._setup_capture_mocks(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.android._wait_for_renderdoc_init",
            lambda s, pid, timeout=15.0: False,
        )
        result = CliRunner().invoke(
            android_capture_cmd,
            ["com.example.app/.MainActivity"],
        )
        assert result.exit_code == 1
        assert "did not initialize" in result.output

    def test_target_control_connect_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_rd = self._setup_capture_mocks(monkeypatch)
        mock_rd.CreateTargetControl.return_value = None
        result = CliRunner().invoke(
            android_capture_cmd,
            ["com.example.app/.MainActivity"],
        )
        assert result.exit_code == 1
        assert "target control" in result.output

    def test_capture_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._setup_capture_mocks(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.android.run_target_control_loop",
            lambda tc, timeout=60.0: CaptureResult(
                success=False,
                error="timeout waiting for capture",
            ),
        )
        result = CliRunner().invoke(
            android_capture_cmd,
            ["com.example.app/.MainActivity"],
        )
        assert result.exit_code == 1
        assert "timeout" in result.output

    def test_remote_capture_pulled(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._setup_capture_mocks(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.android.run_target_control_loop",
            lambda tc, timeout=60.0: CaptureResult(
                success=True,
                path="/sdcard/capture.rdc",
                local=False,
            ),
        )
        out = tmp_path / "out.rdc"
        result = CliRunner().invoke(
            android_capture_cmd,
            ["com.example.app/.MainActivity", "-o", str(out)],
        )
        assert result.exit_code == 0

    def test_cli_registration(self) -> None:
        result = CliRunner().invoke(android_group, ["--help"])
        assert "capture" in result.output

    def test_main_help(self) -> None:
        result = CliRunner().invoke(main, ["android", "capture", "--help"])
        assert result.exit_code == 0
        assert "--serial" in result.output
        assert "--timeout" in result.output
        assert "--port" in result.output
