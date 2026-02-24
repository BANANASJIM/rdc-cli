"""Capture core service: Python API capture via renderdoc.ExecuteAndInject."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from rdc import _platform
from rdc.discover import find_renderdoc

log = logging.getLogger(__name__)


@dataclass
class CaptureResult:
    """Result of a capture operation."""

    success: bool = False
    path: str = ""
    frame: int = 0
    byte_size: int = 0
    api: str = ""
    local: bool = True
    ident: int = 0
    pid: int = 0
    error: str = ""


def build_capture_options(opts: dict[str, Any]) -> Any:
    """Build CaptureOptions from a dict of CLI flag overrides.

    Args:
        opts: Dict mapping CLI flag names to values.

    Returns:
        A CaptureOptions instance with overrides applied on top of defaults.
    """
    rd = find_renderdoc()
    if rd is None:
        msg = "renderdoc module not available"
        raise ImportError(msg)

    cap_opts = rd.GetDefaultCaptureOptions()
    flag_map = {
        "api_validation": "apiValidation",
        "callstacks": "captureCallstacks",
        "callstacks_only_actions": "captureCallstacksOnlyActions",
        "hook_children": "hookIntoChildren",
        "ref_all_resources": "refAllResources",
        "capture_all_cmd_lists": "captureAllCmdLists",
        "allow_fullscreen": "allowFullscreen",
        "allow_vsync": "allowVSync",
        "verify_buffer_access": "verifyBufferAccess",
        "debug_output_mute": "debugOutputMute",
        "delay_for_debugger": "delayForDebugger",
        "soft_memory_limit": "softMemoryLimit",
    }
    for cli_key, api_field in flag_map.items():
        if cli_key in opts:
            setattr(cap_opts, api_field, opts[cli_key])
    return cap_opts


def terminate_process(pid: int) -> bool:
    """Send SIGTERM to a process. Returns True if signal was sent."""
    result = _platform.terminate_process(pid)
    if not result and pid > 0:
        log.debug("process %d already exited or not accessible", pid)
    return result


def _get_pid_for_ident(rd: Any, ident: int) -> int:
    """Connect briefly to retrieve the OS PID for an injected ident."""
    tc = rd.CreateTargetControl("", ident, "rdc-cli", True)
    if tc is None:
        return 0
    try:
        return tc.GetPID() if tc.Connected() else 0
    finally:
        tc.Shutdown()


def execute_and_capture(
    rd: Any,
    app: str,
    args: str = "",
    workdir: str = "",
    output: str = "",
    opts: Any = None,
    *,
    frame: int | None = None,
    trigger: bool = False,
    timeout: float = 60.0,
    wait_for_exit: bool = False,
) -> CaptureResult:
    """Execute application and capture a frame via Python API.

    Args:
        rd: The renderdoc module.
        app: Path to executable.
        args: Command-line arguments string.
        workdir: Working directory for the process.
        output: Output .rdc file path.
        opts: CaptureOptions (uses defaults if None).
        frame: Queue capture at specific frame number.
        trigger: If True, inject only without entering the message loop.
        timeout: Seconds to wait for a capture.
        wait_for_exit: If True, wait for the target process to exit.

    Returns:
        CaptureResult with success status and capture metadata.
    """
    if opts is None:
        opts = rd.GetDefaultCaptureOptions()

    result = rd.ExecuteAndInject(app, workdir or "", args, [], output, opts, wait_for_exit)
    if result.result != 0:
        return CaptureResult(error=f"inject failed (code {result.result})")
    if result.ident == 0:
        return CaptureResult(error="inject returned zero ident")

    if trigger:
        pid = _get_pid_for_ident(rd, result.ident)
        return CaptureResult(success=True, ident=result.ident, pid=pid)

    ident = result.ident
    tc = rd.CreateTargetControl("", ident, "rdc-cli", True)
    if tc is None:
        return CaptureResult(error="failed to connect to target", ident=ident)
    try:
        pid = tc.GetPID()
        cap = _run_target_control_loop(tc, frame=frame, timeout=timeout)
        cap.ident = ident
        cap.pid = pid
        return cap
    finally:
        tc.Shutdown()


def _run_target_control_loop(
    tc: Any,
    *,
    frame: int | None = None,
    timeout: float = 60.0,
) -> CaptureResult:
    """Inner message loop for target control."""
    if frame is not None:
        tc.QueueCapture(frame, 1)
    else:
        tc.TriggerCapture(1)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not tc.Connected():
            return CaptureResult(error="target disconnected")
        msg = tc.ReceiveMessage(None)
        msg_type = int(msg.type)
        # NewCapture = 4, Disconnected = 1
        if msg_type == 4 and msg.newCapture is not None:
            nc = msg.newCapture
            return CaptureResult(
                success=True,
                path=nc.path,
                frame=nc.frameNumber,
                byte_size=nc.byteSize,
                api=nc.api,
                local=nc.local,
            )
        if msg_type == 1:
            return CaptureResult(error="target disconnected")
        time.sleep(0.01)

    return CaptureResult(error="timeout waiting for capture")
