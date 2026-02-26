from __future__ import annotations

import os
from pathlib import Path

import click
from click.shell_completion import CompletionItem

from rdc.commands._helpers import complete_eid
from rdc.services.session_service import (
    close_session,
    connect_session,
    goto_session,
    listen_open_session,
    open_session,
    status_session,
)
from rdc.session_state import session_path


def _complete_capture_path(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Shell completion callback for local capture paths."""
    del ctx, param
    if "/" in incomplete:
        dir_part, prefix = incomplete.rsplit("/", 1)
        dir_path = Path(os.path.expanduser(dir_part or "/"))
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
        if child.is_dir():
            items.append(CompletionItem(f"{base}{child.name}/"))
        elif child.suffix.lower() == ".rdc":
            items.append(CompletionItem(f"{base}{child.name}"))
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
    metavar="HOST[:PORT]",
    help="Proxy host[:port] for remote replay.",
)
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
def open_cmd(
    capture: str | None,
    preload: bool,
    proxy_url: str | None,
    remote_url_deprecated: str | None,
    listen: str | None,
    connect: str | None,
    connect_token: str | None,
) -> None:
    """Create local default session and start daemon skeleton."""
    # Handle --remote deprecation
    if remote_url_deprecated is not None:
        click.echo("warning: --remote is deprecated, use --proxy", err=True)
        if proxy_url is None:
            proxy_url = remote_url_deprecated

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
            ok, result = listen_open_session(capture, listen, remote_url=proxy_url)
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
        click.echo(f"session: {session_path()}")
        return

    # Default: normal open
    if proxy_url is None and not Path(capture).exists():
        click.echo(f"error: file not found: {capture}", err=True)
        raise SystemExit(1)
    ok, message = open_session(capture, remote_url=proxy_url)
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
@click.argument("eid", type=int)
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
