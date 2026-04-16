"""Capture core service: Python API capture via renderdoc.ExecuteAndInject."""

from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import click

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
    remote_path: str = ""


_CAPTURE_RESULT_FIELDS = {f.name for f in fields(CaptureResult)}


def capture_result_from_dict(payload: Mapping[str, Any]) -> CaptureResult:
    """Construct a CaptureResult from a mapping, ignoring unknown keys."""
    filtered = {key: payload[key] for key in _CAPTURE_RESULT_FIELDS if key in payload}
    return CaptureResult(**filtered)


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


def _discover_latest_target(rd: Any, timeout: float = 5.0) -> int:
    """Poll EnumerateRemoteTargets to find a newly injected target.

    Some renderdoc builds (e.g. v1.41 MSBuild .pyd on Windows) return
    ``ident=0`` from ``ExecuteAndInject`` even on success.  The injected
    target *is* reachable — it just isn't reported in the return value.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        latest = 0
        ident = rd.EnumerateRemoteTargets("localhost", 0)
        while ident != 0:
            latest = ident
            ident = rd.EnumerateRemoteTargets("localhost", ident)
        if latest != 0:
            return latest
        time.sleep(0.25)
    return 0


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

    app_path = Path(app)
    if app_path.parts == (app,):
        # Bare executable name — try PATH lookup, keep original if not found
        found = shutil.which(app)
        if found:
            app = found
    else:
        if not app_path.is_absolute() and workdir:
            app_path = Path(workdir) / app_path
        app = str(app_path.resolve())

    result = rd.ExecuteAndInject(app, workdir or "", args, [], output, opts, wait_for_exit)
    if result.result != 0:
        return CaptureResult(error=f"inject failed (code {result.result})")

    ident = result.ident
    if ident == 0:
        # Some renderdoc builds return ident=0 even on success; discover via enumeration.
        ident = _discover_latest_target(rd, timeout=5.0)
        if ident == 0:
            return CaptureResult(error="inject returned zero ident")
        log.debug("discovered target ident %d via enumeration", ident)

    if trigger:
        pid = _get_pid_for_ident(rd, ident)
        return CaptureResult(success=True, ident=ident, pid=pid)

    tc = rd.CreateTargetControl("", ident, "rdc-cli", True)
    if tc is None:
        return CaptureResult(error="failed to connect to target", ident=ident)
    try:
        pid = tc.GetPID()
        cap = run_target_control_loop(tc, frame=frame, timeout=timeout)
        cap.ident = ident
        cap.pid = pid
        return cap
    finally:
        tc.Shutdown()


def _drain_pending_messages(tc: Any) -> None:
    """Drain initial target control messages (RegisterAPI, CapturableWindowCount).

    RenderDoc sends RegisterAPI (type 6) and CapturableWindowCount (type 9)
    asynchronously after connection. These must be consumed before triggering
    capture, otherwise the NewCapture response can be lost.
    """
    for _ in range(20):
        msg = tc.ReceiveMessage(None)
        msg_type = int(msg.type)
        if msg_type == 3:  # Noop — no more pending messages
            break
        if msg_type == 1:  # Disconnected
            log.debug("target disconnected during drain")
            break
        log.debug("drained pending message: type=%d", msg_type)


def run_target_control_loop(
    tc: Any,
    *,
    frame: int | None = None,
    timeout: float = 60.0,
) -> CaptureResult:
    """Inner message loop for target control."""
    _drain_pending_messages(tc)

    if frame is not None:
        tc.QueueCapture(frame, 1)
    else:
        tc.TriggerCapture(1)

    start = time.monotonic()
    deadline = start + timeout
    last_echo = start
    while time.monotonic() < deadline:
        if not tc.Connected():
            return CaptureResult(error="target disconnected")
        msg = tc.ReceiveMessage(None)
        msg_type = int(msg.type)
        log.debug("target control message: type=%d", msg_type)
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
        now = time.monotonic()
        if now - last_echo >= 5.0:
            click.echo(f"waiting for capture... ({int(now - start):d}s)", err=True)
            last_echo = now
        time.sleep(0.01)

    return CaptureResult(error="timeout waiting for capture")
