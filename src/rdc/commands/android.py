"""Android device remote debug commands."""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import click

from rdc.capture_core import run_target_control_loop
from rdc.discover import find_renderdoc
from rdc.remote_core import connect_remote_server
from rdc.remote_state import (
    RemoteServerState,
    delete_remote_state,
    save_remote_state,
)

log = logging.getLogger(__name__)

_MALI_PLATFORMS = {"kirin", "exynos", "orlando", "hi36", "mt6", "mt8"}
_RENDERDOC_REMOTE_PORT = 39920
_TARGET_CONTROL_PORT = 38920
_RENDERDOC_LAYER_VK = "VK_LAYER_RENDERDOC_Capture"
_RENDERDOC_LAYER_GLES = "libVkLayer_GLES_RenderDoc.so"
_RENDERDOC_CMD_PKG = "org.renderdoc.renderdoccmd.arm64"
_GPU_DEBUG_SETTINGS = (
    ("enable_gpu_debug_layers", "1"),
    ("gpu_debug_layer_app", _RENDERDOC_CMD_PKG),
    ("gpu_debug_layers", _RENDERDOC_LAYER_VK),
    ("gpu_debug_layers_gles", _RENDERDOC_LAYER_GLES),
)


def _get_forwarded_port(serial: str | None, url: str) -> int | None:
    """Query adb forward list for the RenderDoc remote server port.

    After StartRemoteServer sets up adb port forwarding, this parses
    ``adb forward --list`` to find the local TCP port mapped to the
    device's remoteserver port.

    Args:
        serial: Device serial or None.
        url: The adb:// URL for the device.

    Returns:
        Local TCP port number, or None if not found.
    """
    if shutil.which("adb") is None:
        return None
    s = serial or url.removeprefix("adb://")
    try:
        proc = subprocess.run(
            ["adb", "-s", s, "forward", "--list"],
            timeout=3,
            capture_output=True,
            text=True,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    for line in proc.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == f"localabstract:renderdoc_{_RENDERDOC_REMOTE_PORT}":
            local = parts[1].removeprefix("tcp:")
            try:
                return int(local)
            except ValueError:
                continue
    return None


def _is_mali_device(ctrl: Any, url: str, serial: str | None) -> bool:
    """Return True if the device likely has a Mali GPU."""
    try:
        if "mali" in ctrl.GetFriendlyName(url).lower():
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        if shutil.which("adb") is None:
            return False
        s = serial or url.removeprefix("adb://")
        proc = subprocess.run(
            ["adb", "-s", s, "shell", "getprop", "ro.board.platform"],
            timeout=3,
            capture_output=True,
            text=True,
        )
        prop = proc.stdout.strip().lower()
        return any(prop.startswith(p) for p in _MALI_PLATFORMS)
    except Exception:  # noqa: BLE001
        return False


def _is_arm_renderdoc(rd: Any) -> bool:
    """Return True if rd is the ARM Performance Studio fork (version like 2025.x)."""
    return bool(re.match(r"^\d{4}\.", rd.GetVersionString()))


def _adb(serial: str, *args: str, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    """Run an adb command targeting a specific device serial.

    Args:
        serial: Device serial string.
        *args: Additional adb arguments.
        timeout: Command timeout in seconds.

    Returns:
        CompletedProcess result.

    Raises:
        RuntimeError: If adb is not found or command fails.
    """
    if shutil.which("adb") is None:
        msg = "adb not found in PATH"
        raise RuntimeError(msg)
    cmd = ["adb", "-s", serial, *args]
    log.debug("adb: %s", " ".join(cmd))
    try:
        return subprocess.run(cmd, timeout=timeout, capture_output=True, text=True)
    except subprocess.TimeoutExpired as exc:
        msg = f"adb command timed out: {' '.join(cmd)}"
        raise RuntimeError(msg) from exc


def _cleanup_device(serial: str) -> None:
    """Kill stale RenderDoc processes and remove old adb forwards on device."""
    _adb(serial, "shell", "pkill", "-f", "renderdoccmd", timeout=3)
    _adb(serial, "forward", "--remove-all", timeout=3)


def _set_gpu_debug_layers(serial: str, package: str) -> None:
    """Configure GPU debug layer settings for a package.

    On EMUI, ``am force-stop`` clears these settings, so this must be
    called right before every app launch.

    Args:
        serial: Device serial string.
        package: Android package name to debug.
    """
    _adb(serial, "shell", "settings", "put", "global", "gpu_debug_app", package)
    for key, value in _GPU_DEBUG_SETTINGS:
        _adb(serial, "shell", "settings", "put", "global", key, value)


def _clear_gpu_debug_layers(serial: str) -> None:
    """Remove GPU debug layer settings from device."""
    for key, _ in _GPU_DEBUG_SETTINGS:
        _adb(serial, "shell", "settings", "delete", "global", key)
    _adb(serial, "shell", "settings", "delete", "global", "gpu_debug_app")


def _get_app_pid(serial: str, package: str, timeout: float = 10.0) -> int:
    """Poll for the PID of a running package.

    Args:
        serial: Device serial string.
        package: Package name to find.
        timeout: Seconds to wait.

    Returns:
        The PID, or 0 if not found within timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        proc = _adb(serial, "shell", "pidof", package, timeout=3)
        pid_str = proc.stdout.strip()
        if pid_str:
            try:
                return int(pid_str.split()[0])
            except ValueError:
                pass
        time.sleep(0.5)
    return 0


def _wait_for_renderdoc_init(serial: str, pid: int, timeout: float = 15.0) -> bool:
    """Wait for RenderDoc to report ready in logcat.

    Polls ``adb logcat`` for the target control listener message from
    the injected RenderDoc layer.

    Args:
        serial: Device serial string.
        pid: App PID to filter logcat.
        timeout: Seconds to wait.

    Returns:
        True if RenderDoc initialization was detected.
    """
    deadline = time.monotonic() + timeout
    markers = ("Listening for target control", "Adding OpenGLES frame capturer")
    while time.monotonic() < deadline:
        proc = _adb(serial, "logcat", "-d", "--pid", str(pid), timeout=5)
        if any(m in proc.stdout for m in markers):
            return True
        time.sleep(1.0)
    return False


def _forward_target_control(serial: str, port: int = _TARGET_CONTROL_PORT) -> int:
    """Set up adb forward for the RenderDoc target control abstract socket.

    Args:
        serial: Device serial string.
        port: Local TCP port to forward.

    Returns:
        The local port used for forwarding.
    """
    _adb(serial, "forward", f"tcp:{port}", f"localabstract:renderdoc_{port}")
    return port


def _resolve_serial(serial: str | None) -> str:
    """Resolve a single device serial from adb, or use the given one.

    Args:
        serial: Explicit serial, or None for auto-detect.

    Returns:
        Device serial string.

    Raises:
        SystemExit: If no device or multiple devices and no serial given.
    """
    if serial:
        return serial
    if shutil.which("adb") is None:
        click.echo("error: adb not found in PATH", err=True)
        raise SystemExit(1)
    proc = subprocess.run(
        ["adb", "devices"],
        timeout=5,
        capture_output=True,
        text=True,
    )
    serials = []
    for line in proc.stdout.strip().splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    if not serials:
        click.echo("error: no Android devices found (check adb devices)", err=True)
        raise SystemExit(1)
    if len(serials) > 1:
        click.echo("error: multiple devices connected; use --serial to select one", err=True)
        for s in serials:
            click.echo(f"  {s}", err=True)
        raise SystemExit(1)
    return serials[0]


def _resolve_device(ctrl: Any, devices: list[str], serial: str | None) -> str:
    """Select a device URL from the enumerated list.

    Args:
        ctrl: DeviceProtocolController for friendly name lookup.
        devices: List of device URLs (e.g. ["adb://SERIAL"]).
        serial: Optional serial to match, or None for auto-select.

    Returns:
        The selected device URL string.

    Raises:
        SystemExit: If no device matches or disambiguation is needed.
    """
    if not devices:
        click.echo("error: no Android devices found (check adb devices)", err=True)
        raise SystemExit(1)
    if serial:
        target = f"adb://{serial}"
        if target in devices:
            return target
        click.echo(f"error: device {serial!r} not found", err=True)
        click.echo("available devices:", err=True)
        for d in devices:
            name = ctrl.GetFriendlyName(d)
            click.echo(f"  {d}  ({name})", err=True)
        raise SystemExit(1)
    if len(devices) == 1:
        return devices[0]
    click.echo("error: multiple devices connected; use --serial to select one", err=True)
    for d in devices:
        name = ctrl.GetFriendlyName(d)
        click.echo(f"  {d}  ({name})", err=True)
    raise SystemExit(1)


@click.group("android")
def android_group() -> None:
    """Android device remote debug commands."""


@android_group.command("setup")
@click.option("--serial", default=None, help="Target device serial.")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def android_setup_cmd(serial: str | None, use_json: bool) -> None:
    """Start RenderDoc remote server on an Android device."""
    rd = find_renderdoc()
    if rd is None:
        click.echo("error: renderdoc module not found (run 'rdc setup-renderdoc')", err=True)
        raise SystemExit(1)

    ctrl = rd.GetDeviceProtocolController("adb")
    devices: list[str] = list(ctrl.GetDevices())
    url = _resolve_device(ctrl, devices, serial)

    if not ctrl.IsSupported(url):
        click.echo(f"error: device {url} is not supported", err=True)
        raise SystemExit(1)

    if _is_mali_device(ctrl, url, serial) and not _is_arm_renderdoc(rd):
        click.echo(
            "hint: Mali GPU detected with upstream RenderDoc. "
            "For better compatibility, use ARM Performance Studio version: "
            "rdc setup-renderdoc --android --arm-studio <path>",
            err=True,
        )

    result = ctrl.StartRemoteServer(url)
    if not result.OK():
        click.echo(f"error: failed to start server: {result.Message()}", err=True)
        raise SystemExit(1)

    # Determine the actual connection URL: prefer forwarded TCP port over adb:// URL
    # because adb:// internal port mapping may not match the actual forwarded port.
    conn_url = url
    forwarded_port = _get_forwarded_port(serial, url)
    if forwarded_port is not None:
        conn_url = f"localhost:{forwarded_port}"

    try:
        remote = connect_remote_server(rd, conn_url)
    except RuntimeError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None

    try:
        remote.Ping()
    except Exception as exc:  # noqa: BLE001
        click.echo(f"error: connection verification failed: {exc}", err=True)
        raise SystemExit(1) from None
    finally:
        remote.ShutdownConnection()

    save_remote_state(RemoteServerState(host=url, port=0, connected_at=time.time()))

    friendly = ctrl.GetFriendlyName(url)
    if use_json:
        click.echo(json.dumps({"device": friendly, "url": url, "connected": True}))
    else:
        click.echo(f"device: {friendly} ({url})")
        click.echo("server: started")
        click.echo("next: rdc remote list", err=True)


@android_group.command("stop")
@click.option("--serial", default=None, help="Target device serial.")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def android_stop_cmd(serial: str | None, use_json: bool) -> None:
    """Stop RenderDoc remote server on an Android device."""
    rd = find_renderdoc()
    if rd is None:
        click.echo("error: renderdoc module not found (run 'rdc setup-renderdoc')", err=True)
        raise SystemExit(1)

    ctrl = rd.GetDeviceProtocolController("adb")
    devices: list[str] = list(ctrl.GetDevices())
    url = _resolve_device(ctrl, devices, serial)

    stop_fn = getattr(ctrl, "StopRemoteServer", None)
    if stop_fn is not None:
        stop_fn(url)
    else:
        click.echo("warning: StopRemoteServer not available in this build", err=True)

    delete_remote_state(url, 0)

    friendly = ctrl.GetFriendlyName(url)
    if use_json:
        click.echo(json.dumps({"device": friendly, "url": url, "stopped": True}))
    else:
        click.echo(f"device: {friendly} ({url})")
        click.echo("server: stopped")


@android_group.command("capture")
@click.argument("activity")
@click.option("--serial", default=None, help="Target device serial.")
@click.option(
    "-o",
    "--output",
    default=None,
    type=click.Path(path_type=Path),
    help="Local output path (default: <package>.rdc).",
)
@click.option("--timeout", type=float, default=30.0, help="Capture timeout in seconds.")
@click.option("--port", type=int, default=_TARGET_CONTROL_PORT, help="Target control port.")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def android_capture_cmd(
    activity: str,
    serial: str | None,
    output: Path | None,
    timeout: float,
    port: int,
    use_json: bool,
) -> None:
    """Capture a frame from an Android app using GPU debug layers.

    ACTIVITY is the package/activity to launch (e.g. com.app/.MainActivity).
    This uses the Android GPU debug layer mechanism (Android 10+) which is
    more reliable than the remote server approach on many devices.
    """
    rd = find_renderdoc()
    if rd is None:
        click.echo("error: renderdoc module not found (run 'rdc setup-renderdoc')", err=True)
        raise SystemExit(1)

    device_serial = _resolve_serial(serial)
    package = activity.split("/")[0]
    if output is None:
        output = Path(f"{package}.rdc")

    # Clean up stale RenderDoc processes and forwards
    _cleanup_device(device_serial)

    # Set GPU debug layer settings (re-applied before launch for EMUI compat)
    _set_gpu_debug_layers(device_serial, package)

    # Force-stop then re-apply settings (EMUI clears them on force-stop)
    _adb(device_serial, "shell", "am", "force-stop", package)
    _set_gpu_debug_layers(device_serial, package)

    # Launch app
    _adb(device_serial, "shell", "am", "start", "-S", "-n", activity)

    # Wait for app to start
    pid = _get_app_pid(device_serial, package)
    if pid == 0:
        click.echo(f"error: {package} did not start", err=True)
        _clear_gpu_debug_layers(device_serial)
        raise SystemExit(1)
    log.debug("app pid: %d", pid)

    # Wait for RenderDoc layer initialization
    if not _wait_for_renderdoc_init(device_serial, pid, timeout=15.0):
        click.echo("error: RenderDoc layer did not initialize (check logcat)", err=True)
        _clear_gpu_debug_layers(device_serial)
        raise SystemExit(1)

    # Forward target control abstract socket
    local_port = _forward_target_control(device_serial, port)

    # Connect via target control
    tc = rd.CreateTargetControl("localhost", local_port, "rdc-cli", True)
    if tc is None:
        click.echo("error: failed to connect to target control", err=True)
        _clear_gpu_debug_layers(device_serial)
        _adb(device_serial, "forward", "--remove-all", timeout=3)
        raise SystemExit(1)

    try:
        result = run_target_control_loop(tc, timeout=timeout)
    finally:
        tc.Shutdown()

    # Copy capture from device if needed
    if result.success and not result.local and result.path:
        try:
            proc = _adb(device_serial, "pull", result.path, str(output), timeout=60)
            if proc.returncode != 0:
                result.success = False
                result.error = f"adb pull failed: {proc.stderr.strip() or 'unknown error'}"
            else:
                result.path = str(output)
                result.local = True
        except RuntimeError as exc:
            result.success = False
            result.error = f"capture succeeded but transfer failed: {exc}"

    # Cleanup
    _adb(device_serial, "shell", "am", "force-stop", package, timeout=5)
    _clear_gpu_debug_layers(device_serial)
    _adb(device_serial, "forward", "--remove-all", timeout=3)

    if use_json:
        click.echo(json.dumps(dataclasses.asdict(result)))
        if not result.success:
            raise SystemExit(1)
        return

    if not result.success:
        click.echo(f"error: {result.error}", err=True)
        raise SystemExit(1)

    click.echo(result.path)
    click.echo(f"next: rdc open {result.path}", err=True)
