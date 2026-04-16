from __future__ import annotations

import json
import os
from pathlib import Path

import click
from click.shell_completion import CompletionItem

from rdc import _platform
from rdc.commands._helpers import complete_eid
from rdc.remote_state import RemoteServerState
from rdc.services.session_service import (
    close_session,
    connect_session,
    goto_session,
    listen_open_session,
    open_session,
    status_session,
)
from rdc.session_state import session_path


def _is_android_state(state: RemoteServerState) -> bool:
    """Check if a RemoteServerState is from an Android device."""
    if state.host.startswith("adb://"):
        return True
    # Bare serial from adb fallback: port=0 and no colon (not host:port)
    return state.port == 0 and ":" not in state.host and "." not in state.host


def _android_serial(state: RemoteServerState) -> str:
    """Extract bare serial from state host."""
    return state.host.removeprefix("adb://")


def _adb_forwarded_port(serial: str) -> int | None:
    """Look up the adb-forwarded TCP port for a device serial."""
    import subprocess  # noqa: PLC0415

    try:
        proc = subprocess.run(
            ["adb", "forward", "--list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    for line in proc.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == serial and parts[1].startswith("tcp:"):
            try:
                return int(parts[1].removeprefix("tcp:"))
            except ValueError:
                continue
    return None


def _resolve_android_url(serial: str | None) -> str:
    """Resolve a proxy URL for an Android device from saved state + adb forward."""
    remote_dir = _platform.data_dir() / "remote"
    if not remote_dir.is_dir():
        raise click.UsageError("no saved Android device state; run: rdc android setup")

    best: RemoteServerState | None = None
    for f in remote_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            state = RemoteServerState(
                host=data["host"],
                port=int(data["port"]),
                connected_at=float(data["connected_at"]),
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            continue
        if not _is_android_state(state):
            continue
        if serial is not None:
            if _android_serial(state) == serial:
                best = state
                break
        elif best is None or state.connected_at > best.connected_at:
            best = state

    if best is None:
        if serial is not None:
            raise click.UsageError(
                f"no saved state for device {serial}; run: rdc android setup --serial {serial}"
            )
        raise click.UsageError("no saved Android device state; run: rdc android setup")

    # Resolve to localhost:PORT via adb forward (adb:// URLs crash RenderDoc daemon)
    dev_serial = _android_serial(best)
    port = _adb_forwarded_port(dev_serial)
    if port is not None:
        return f"localhost:{port}"
    # Fallback to adb:// URL if no forward found
    return f"adb://{dev_serial}"


def _complete_capture_path(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Shell completion callback for local capture paths."""
    del ctx, param
    if "/" in incomplete:
        dir_part, prefix = incomplete.rsplit("/", 1)
        dir_path = Path(dir_part or "/").expanduser()
        base = f"{dir_part}/"
    else:
        dir_path = Path(".")
        prefix = incomplete
        base = ""

    try:
        children = sorted(dir_path.iterdir(), key=lambda p: p.name)
    except OSError:
        return []

    items: list[CompletionItem] = []
    for child in children:
        if not child.name.startswith(prefix):
            continue
        try:
            if child.is_dir():
                items.append(CompletionItem(f"{base}{child.name}/"))
            elif child.suffix.lower() == ".rdc":
                items.append(CompletionItem(f"{base}{child.name}"))
        except OSError:
            continue
    return items


@click.command("open")
@click.argument(
    "capture",
    type=str,
    required=False,
    default=None,
    shell_complete=_complete_capture_path,
)
@click.option("--preload", is_flag=True, default=False, help="Preload shader cache after open.")
@click.option(
    "--proxy",
    "proxy_url",
    default=None,
    metavar="HOST[:PORT]|adb://SERIAL",
    help="Proxy host[:port] or adb://SERIAL for remote replay.",
)
@click.option(
    "--android",
    is_flag=True,
    default=False,
    help="Use saved Android device for remote replay.",
)
@click.option("--serial", default=None, type=str, help="Android device serial (with --android).")
@click.option(
    "--remote",
    "remote_url_deprecated",
    default=None,
    metavar="HOST[:PORT]",
    hidden=True,
)
@click.option(
    "--listen",
    default=None,
    metavar="[ADDR]:PORT",
    help="Listen on [ADDR]:PORT. Use :0 for auto-port on all interfaces.",
)
@click.option(
    "--connect",
    default=None,
    metavar="HOST:PORT",
    help="Connect to an already-running external daemon.",
)
@click.option(
    "--token",
    "connect_token",
    default=None,
    help="Authentication token (required with --connect).",
)
@click.option(
    "--timeout",
    type=float,
    default=None,
    help="Daemon startup timeout in seconds.",
)
def open_cmd(
    capture: str | None,
    preload: bool,
    proxy_url: str | None,
    android: bool,
    serial: str | None,
    remote_url_deprecated: str | None,
    listen: str | None,
    connect: str | None,
    connect_token: str | None,
    timeout: float | None,
) -> None:
    """Create local default session and start daemon skeleton."""
    # Handle --remote deprecation
    if remote_url_deprecated is not None:
        click.echo("warning: --remote is deprecated, use --proxy", err=True)
        if proxy_url is None:
            proxy_url = remote_url_deprecated

    # --serial without --android is meaningless
    if serial is not None and not android:
        click.echo("warning: --serial is ignored without --android", err=True)

    # --android mutual exclusion
    if android:
        if proxy_url is not None:
            raise click.UsageError("--android is mutually exclusive with --proxy")
        if connect is not None:
            raise click.UsageError("--android is mutually exclusive with --connect")
        if listen is not None:
            raise click.UsageError("--android is mutually exclusive with --listen")
        proxy_url = _resolve_android_url(serial)

    # Validation: --connect is mutually exclusive with capture/--proxy/--listen
    if connect is not None:
        if capture is not None:
            click.echo("error: --connect is mutually exclusive with CAPTURE argument", err=True)
            raise SystemExit(1)
        if proxy_url is not None:
            click.echo("error: --connect is mutually exclusive with --proxy", err=True)
            raise SystemExit(1)
        if listen is not None:
            click.echo("error: --connect is mutually exclusive with --listen", err=True)
            raise SystemExit(1)
        if connect_token is None:
            click.echo("error: --connect requires --token", err=True)
            raise SystemExit(1)

    # Without --connect, capture is required
    if connect is None and capture is None:
        click.echo("error: CAPTURE argument is required (unless using --connect)", err=True)
        raise SystemExit(1)

    if connect is None and connect_token is not None:
        click.echo("warning: --token is ignored without --connect", err=True)

    # Dispatch: --connect
    if connect is not None:
        assert connect_token is not None
        if ":" not in connect:
            click.echo("error: --connect requires HOST:PORT format", err=True)
            raise SystemExit(1)
        host_part, port_str = connect.rsplit(":", 1)
        if not host_part:
            click.echo("error: invalid --connect: HOST is required in HOST:PORT", err=True)
            raise SystemExit(1)
        try:
            port = int(port_str)
        except ValueError:
            click.echo(f"error: invalid port: {port_str}", err=True)
            raise SystemExit(1) from None
        if not 1 <= port <= 65535:
            click.echo(f"error: port out of range: {port} (must be 1-65535)", err=True)
            raise SystemExit(1)
        ok, message = connect_session(host_part, port, connect_token)
        if not ok:
            click.echo(message, err=True)
            raise SystemExit(1)
        click.echo(message)
        click.echo(f"session: {session_path()}")
        return

    assert capture is not None

    # Dispatch: --listen
    if listen is not None:
        if proxy_url is None and not Path(capture).exists():
            click.echo(f"error: file not found: {capture}", err=True)
            raise SystemExit(1)
        try:
            ok, result = listen_open_session(capture, listen, remote_url=proxy_url, timeout=timeout)
        except ValueError as exc:
            click.echo(f"error: {exc}", err=True)
            raise SystemExit(1) from None
        if not ok:
            click.echo(str(result), err=True)
            raise SystemExit(1)
        assert isinstance(result, dict)
        click.echo(f"opened: {capture} (listening)")
        click.echo(f"host: {result['host']}")
        click.echo(f"port: {result['port']}")
        click.echo(f"token: {result['token']}")
        click.echo(
            f"connect with: rdc open --connect"
            f" {result['host']}:{result['port']}"
            f" --token {result['token']}"
        )
        click.echo(f"session: {session_path()}")
        return

    # Default: normal open
    if proxy_url is None and not Path(capture).exists():
        click.echo(f"error: file not found: {capture}", err=True)
        raise SystemExit(1)
    ok, message = open_session(capture, remote_url=proxy_url, timeout=timeout)
    if not ok:
        click.echo(message, err=True)
        raise SystemExit(1)
    click.echo(message)
    if "no-replay mode" in message:
        click.echo("warning: queries requiring replay will fail", err=True)
    click.echo(f"session: {session_path()}")
    if preload:
        from rdc.commands._helpers import call

        result = call("shaders_preload", {})
        click.echo(f"preloaded {result['shaders']} shader(s)")


@click.command("status")
def status_cmd() -> None:
    """Show current daemon-backed session status."""
    ok, result = status_session()
    if not ok:
        click.echo(str(result), err=True)
        raise SystemExit(1)

    payload = result
    assert isinstance(payload, dict)
    click.echo(f"session: {os.environ.get('RDC_SESSION') or 'default'}")
    click.echo(f"capture: {payload['capture']}")
    click.echo(f"current_eid: {payload['current_eid']}")
    click.echo(f"opened_at: {payload['opened_at']}")
    click.echo(f"daemon: {payload['daemon']}")
    if "remote" in payload:
        click.echo(f"remote: {payload['remote']}")


@click.command("goto")
@click.argument("eid", type=int, shell_complete=complete_eid)
def goto_cmd(eid: int) -> None:
    """Update current event id via daemon."""
    ok, message = goto_session(eid)
    if not ok:
        click.echo(message, err=True)
        raise SystemExit(1)
    click.echo(message)


@click.command("close")
@click.option("--shutdown", is_flag=True, default=False, help="Send shutdown RPC to daemon.")
def close_cmd(shutdown: bool) -> None:
    """Close daemon-backed session."""
    ok, message = close_session(force_shutdown=shutdown)
    if not ok:
        click.echo(message, err=True)
        raise SystemExit(1)
    click.echo(message)
