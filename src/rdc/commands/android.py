"""Android device remote debug commands."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from typing import Any

import click

from rdc.discover import find_renderdoc
from rdc.remote_core import connect_remote_server
from rdc.remote_state import (
    RemoteServerState,
    delete_remote_state,
    save_remote_state,
)

_MALI_PLATFORMS = {"kirin", "exynos", "orlando", "hi36", "mt6", "mt8"}
_RENDERDOC_REMOTE_PORT = 39920


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
        if len(parts) >= 3 and parts[2] == f"tcp:{_RENDERDOC_REMOTE_PORT}":
            # parts[1] is "tcp:LOCAL_PORT"
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
