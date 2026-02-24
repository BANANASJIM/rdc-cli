"""Tests for capture_core module — Python API capture via ExecuteAndInject."""

from __future__ import annotations

import signal
import sys
from types import SimpleNamespace
from typing import Any

import mock_renderdoc as mock_rd
import pytest


def _make_mock_rd(
    *,
    inject_result: int = 0,
    inject_ident: int = 12345,
    messages: list[mock_rd.TargetControlMessage] | None = None,
) -> SimpleNamespace:
    """Build a fake renderdoc module with configurable ExecuteAndInject and TargetControl."""
    tc = mock_rd.MockTargetControl(messages=messages)
    calls: dict[str, list[Any]] = {"inject": [], "tc_create": [], "queue": [], "trigger": []}

    # Patch QueueCapture / TriggerCapture to record calls
    _orig_queue = tc.QueueCapture
    _orig_trigger = tc.TriggerCapture

    def _queue(frame: int, n: int = 1) -> None:
        calls["queue"].append((frame, n))
        _orig_queue(frame, n)

    def _trigger(n: int = 1) -> None:
        calls["trigger"].append(n)
        _orig_trigger(n)

    tc.QueueCapture = _queue
    tc.TriggerCapture = _trigger

    def fake_execute(  # noqa: N803
        app: str,
        working_dir: str,
        cmd_line: str,
        env_list: list[str],
        capturefile: str,
        opts: Any,
        wait_for_exit: bool = False,
    ) -> mock_rd.ExecuteResult:
        calls["inject"].append((app, working_dir, cmd_line, capturefile))
        return mock_rd.ExecuteResult(result=inject_result, ident=inject_ident)

    def fake_create_tc(
        url: str, ident: int, client_name: str, force_connection: bool
    ) -> mock_rd.MockTargetControl:
        calls["tc_create"].append((url, ident, client_name))
        return tc

    rd = SimpleNamespace(
        ExecuteAndInject=fake_execute,
        CreateTargetControl=fake_create_tc,
        GetDefaultCaptureOptions=mock_rd.GetDefaultCaptureOptions,
        CaptureOptions=mock_rd.CaptureOptions,
        _calls=calls,
        _tc=tc,
    )
    return rd


@pytest.fixture()
def _patch_discover(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch find_renderdoc to return mock_rd module."""
    monkeypatch.setattr("rdc.capture_core.find_renderdoc", lambda: mock_rd)


class TestBuildCaptureOptions:
    @pytest.mark.usefixtures("_patch_discover")
    def test_defaults(self) -> None:
        from rdc.capture_core import build_capture_options

        opts = build_capture_options({})
        assert opts.allowFullscreen is True
        assert opts.allowVSync is True
        assert opts.debugOutputMute is True
        assert opts.apiValidation is False

    @pytest.mark.usefixtures("_patch_discover")
    def test_all_flags(self) -> None:
        from rdc.capture_core import build_capture_options

        overrides = {
            "api_validation": True,
            "callstacks": True,
            "callstacks_only_actions": True,
            "hook_children": True,
            "ref_all_resources": True,
            "capture_all_cmd_lists": True,
            "allow_fullscreen": False,
            "allow_vsync": False,
            "verify_buffer_access": True,
            "debug_output_mute": False,
            "delay_for_debugger": 5,
            "soft_memory_limit": 512,
        }
        opts = build_capture_options(overrides)
        assert opts.apiValidation is True
        assert opts.captureCallstacks is True
        assert opts.captureCallstacksOnlyActions is True
        assert opts.hookIntoChildren is True
        assert opts.refAllResources is True
        assert opts.captureAllCmdLists is True
        assert opts.allowFullscreen is False
        assert opts.allowVSync is False
        assert opts.verifyBufferAccess is True
        assert opts.debugOutputMute is False
        assert opts.delayForDebugger == 5
        assert opts.softMemoryLimit == 512


class TestExecuteAndCapture:
    def test_capture_success(self) -> None:
        from rdc.capture_core import execute_and_capture

        new_cap = mock_rd.NewCaptureData(
            path="/tmp/cap.rdc", frameNumber=0, byteSize=4096, api="Vulkan", local=True
        )
        msg = mock_rd.TargetControlMessage(
            type=mock_rd.TargetControlMessageType.NewCapture, newCapture=new_cap
        )
        rd = _make_mock_rd(messages=[msg])

        result = execute_and_capture(rd, "/usr/bin/app", output="/tmp/cap.rdc")
        assert result.success is True
        assert result.path == "/tmp/cap.rdc"
        assert result.api == "Vulkan"
        assert result.ident == 12345

    def test_capture_queue_frame(self) -> None:
        from rdc.capture_core import execute_and_capture

        new_cap = mock_rd.NewCaptureData(
            path="/tmp/f5.rdc", frameNumber=5, byteSize=1024, api="Vulkan"
        )
        msg = mock_rd.TargetControlMessage(
            type=mock_rd.TargetControlMessageType.NewCapture, newCapture=new_cap
        )
        rd = _make_mock_rd(messages=[msg])

        result = execute_and_capture(rd, "/usr/bin/app", frame=5)
        assert result.success is True
        assert result.frame == 5
        assert result.ident == 12345
        assert rd._calls["queue"] == [(5, 1)]

    def test_capture_timeout(self) -> None:
        from rdc.capture_core import execute_and_capture

        # No NewCapture message — only Noop forever
        rd = _make_mock_rd(messages=[])

        result = execute_and_capture(rd, "/usr/bin/app", timeout=0.05)
        assert result.success is False
        assert "timeout" in result.error

    def test_capture_disconnect(self) -> None:
        from rdc.capture_core import execute_and_capture

        msg = mock_rd.TargetControlMessage(type=mock_rd.TargetControlMessageType.Disconnected)
        rd = _make_mock_rd(messages=[msg])

        result = execute_and_capture(rd, "/usr/bin/app")
        assert result.success is False
        assert "disconnect" in result.error

    def test_capture_inject_failure(self) -> None:
        from rdc.capture_core import execute_and_capture

        rd = _make_mock_rd(inject_result=1)

        result = execute_and_capture(rd, "/usr/bin/app")
        assert result.success is False
        assert "inject failed" in result.error

    def test_capture_trigger_mode(self) -> None:
        from rdc.capture_core import execute_and_capture

        rd = _make_mock_rd()

        result = execute_and_capture(rd, "/usr/bin/app", trigger=True)
        assert result.success is True
        assert result.ident == 12345
        # Trigger path connects briefly to get PID, then shuts down
        assert len(rd._calls["tc_create"]) == 1

    def test_capture_timeout_has_ident(self) -> None:
        from rdc.capture_core import execute_and_capture

        rd = _make_mock_rd(messages=[])
        result = execute_and_capture(rd, "/usr/bin/app", timeout=0.05)
        assert result.success is False
        assert result.ident == 12345

    def test_capture_disconnect_has_ident(self) -> None:
        from rdc.capture_core import execute_and_capture

        msg = mock_rd.TargetControlMessage(type=mock_rd.TargetControlMessageType.Disconnected)
        rd = _make_mock_rd(messages=[msg])
        result = execute_and_capture(rd, "/usr/bin/app")
        assert result.success is False
        assert result.ident == 12345

    def test_create_target_control_returns_none(self) -> None:
        """CreateTargetControl returning None (process exited) gives error with ident."""
        from rdc.capture_core import execute_and_capture

        rd = _make_mock_rd()
        rd.CreateTargetControl = lambda *_args, **_kw: None

        result = execute_and_capture(rd, "/usr/bin/app")
        assert result.success is False
        assert result.ident == 12345
        assert "failed to connect" in result.error

    def test_capture_trigger_returns_nonzero_pid(self) -> None:
        from rdc.capture_core import execute_and_capture

        rd = _make_mock_rd()
        result = execute_and_capture(rd, "/usr/bin/app", trigger=True)
        assert result.success is True
        assert result.pid != 0

    def test_capture_trigger_connects_briefly_then_shuts_down(self) -> None:
        from rdc.capture_core import execute_and_capture

        rd = _make_mock_rd()
        execute_and_capture(rd, "/usr/bin/app", trigger=True)
        assert len(rd._calls["tc_create"]) == 1
        assert rd._tc.shutdown_count >= 1

    def test_capture_trigger_connect_failure_still_succeeds(self) -> None:
        from rdc.capture_core import execute_and_capture

        rd = _make_mock_rd()
        rd.CreateTargetControl = lambda *_a, **_kw: None
        result = execute_and_capture(rd, "/usr/bin/app", trigger=True)
        assert result.success is True
        assert result.pid == 0


class TestTerminateProcess:
    @pytest.mark.skipif(
        sys.platform == "win32", reason="Unix signals: Windows uses TerminateProcess"
    )
    def test_sends_sigterm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.capture_core import terminate_process

        calls: list[tuple[int, int]] = []
        monkeypatch.setattr("rdc._platform.os.kill", lambda pid, sig: calls.append((pid, sig)))

        assert terminate_process(42) is True
        assert calls == [(42, signal.SIGTERM)]

    def test_process_already_exited(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.capture_core import terminate_process

        def fake_kill(pid: int, sig: int) -> None:
            raise ProcessLookupError

        monkeypatch.setattr("rdc._platform.os.kill", fake_kill)
        assert terminate_process(42) is False

    def test_permission_denied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.capture_core import terminate_process

        def fake_kill(pid: int, sig: int) -> None:
            raise PermissionError

        monkeypatch.setattr("rdc._platform.os.kill", fake_kill)
        assert terminate_process(42) is False

    def test_invalid_pid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.capture_core import terminate_process

        calls: list[tuple[int, int]] = []
        monkeypatch.setattr("rdc._platform.os.kill", lambda pid, sig: calls.append((pid, sig)))

        assert terminate_process(0) is False
        assert calls == []
