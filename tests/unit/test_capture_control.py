"""Tests for TargetControl CLI commands (bypass daemon, call CreateTargetControl directly)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from rdc.commands.capture_control import (
    attach_cmd,
    capture_copy_cmd,
    capture_list_cmd,
    capture_trigger_cmd,
)
from rdc.target_state import TargetControlState, save_target_state


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))


def _make_mock_tc(
    *,
    connected: bool = True,
    target: str = "myapp",
    pid: int = 9999,
    api: str = "Vulkan",
    messages: list[Any] | None = None,
) -> MagicMock:
    """Build a mock TargetControl object."""
    tc = MagicMock()
    tc.Connected.return_value = connected
    tc.GetTarget.return_value = target
    tc.GetPID.return_value = pid
    tc.GetAPI.return_value = api

    if messages:
        tc.ReceiveMessage.side_effect = messages
    else:
        noop = MagicMock()
        noop.type = 3  # Noop
        noop.newCapture = None
        tc.ReceiveMessage.return_value = noop
    return tc


def _make_mock_rd(tc: MagicMock) -> MagicMock:
    """Build a mock renderdoc module that returns the given TargetControl."""
    rd = MagicMock()
    rd.CreateTargetControl.return_value = tc
    return rd


def _save_state(ident: int = 12345) -> None:
    save_target_state(
        TargetControlState(
            ident=ident,
            target_name="myapp",
            pid=9999,
            api="Vulkan",
            connected_at=time.time(),
        )
    )


# --- attach ---


def test_attach_success(monkeypatch: pytest.MonkeyPatch) -> None:
    tc = _make_mock_tc()
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(attach_cmd, ["12345"])
    assert result.exit_code == 0
    assert "attached" in result.output
    assert "myapp" in result.output
    assert "9999" in result.output
    assert "Vulkan" in result.output
    tc.Shutdown.assert_called_once()


def test_attach_connection_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    tc = _make_mock_tc(connected=False)
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(attach_cmd, ["12345"])
    assert result.exit_code != 0
    assert "error" in result.output.lower() or "error" in (result.stderr or "").lower()


# --- capture-trigger ---


def test_capture_trigger_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _save_state()
    tc = _make_mock_tc()
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_trigger_cmd, [])
    assert result.exit_code == 0
    assert "triggered" in result.output
    tc.TriggerCapture.assert_called_once_with(1)
    tc.Shutdown.assert_called_once()


def test_capture_trigger_no_state(monkeypatch: pytest.MonkeyPatch) -> None:
    rd = MagicMock()
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_trigger_cmd, [])
    assert result.exit_code != 0
    output = result.output.lower() + (result.stderr or "").lower()
    assert "no active target" in output


# --- capture-list ---


def test_capture_list_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _save_state()

    new_cap_msg = MagicMock()
    new_cap_msg.type = 4  # NewCapture
    nc = MagicMock()
    nc.captureId = 0
    nc.path = "/tmp/test.rdc"
    nc.frameNumber = 42
    nc.byteSize = 1024
    nc.api = "Vulkan"
    new_cap_msg.newCapture = nc

    noop_msg = MagicMock()
    noop_msg.type = 3  # Noop
    noop_msg.newCapture = None

    disconnect_msg = MagicMock()
    disconnect_msg.type = 1  # Disconnected
    disconnect_msg.newCapture = None

    tc = _make_mock_tc(messages=[new_cap_msg, noop_msg, disconnect_msg])
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_list_cmd, ["--timeout", "0.1"])
    assert result.exit_code == 0
    assert "/tmp/test.rdc" in result.output
    assert "42" in result.output
    tc.Shutdown.assert_called_once()


# --- capture-copy ---


def test_capture_copy_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _save_state()

    copied_msg = MagicMock()
    copied_msg.type = 5  # CaptureCopied

    tc = _make_mock_tc(messages=[copied_msg])
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_copy_cmd, ["0", "/tmp/out.rdc", "--timeout", "1"])
    assert result.exit_code == 0
    assert "copied" in result.output
    tc.CopyCapture.assert_called_once_with(0, "/tmp/out.rdc")
    tc.Shutdown.assert_called_once()


def test_capture_copy_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _save_state()
    tc = _make_mock_tc()  # default Noop messages -> will timeout
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_copy_cmd, ["0", "/tmp/out.rdc", "--timeout", "0.05"])
    assert result.exit_code != 0


def test_capture_copy_disconnected(monkeypatch: pytest.MonkeyPatch) -> None:
    _save_state()

    disconnect_msg = MagicMock()
    disconnect_msg.type = 1  # Disconnected

    tc = _make_mock_tc(messages=[disconnect_msg])
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_copy_cmd, ["0", "/tmp/out.rdc", "--timeout", "1"])
    assert result.exit_code != 0


def test_capture_copy_no_state(monkeypatch: pytest.MonkeyPatch) -> None:
    rd = MagicMock()
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_copy_cmd, ["0", "/tmp/out.rdc"])
    assert result.exit_code != 0
    output = result.output.lower() + (result.stderr or "").lower()
    assert "no active target" in output


# --- B28: _connect Shutdown on not-connected ---


def test_connect_not_connected_calls_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    tc = _make_mock_tc(connected=False)
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(attach_cmd, ["12345"])
    assert result.exit_code != 0
    tc.Shutdown.assert_called_once()


def test_connect_none_tc_does_not_call_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    rd = MagicMock()
    rd.CreateTargetControl.return_value = None
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(attach_cmd, ["12345"])
    assert result.exit_code != 0


def test_capture_trigger_not_connected_calls_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    tc = _make_mock_tc(connected=False)
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_trigger_cmd, ["--ident", "12345"])
    assert result.exit_code != 0
    tc.Shutdown.assert_called_once()


def test_capture_list_not_connected_calls_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    tc = _make_mock_tc(connected=False)
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_list_cmd, ["--ident", "12345", "--timeout", "0.1"])
    assert result.exit_code != 0
    tc.Shutdown.assert_called_once()
