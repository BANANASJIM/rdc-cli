from __future__ import annotations

import os
from pathlib import Path

import click

from rdc.services.session_service import close_session, goto_session, open_session, status_session
from rdc.session_state import session_path


@click.command("open")
@click.argument("capture", type=click.Path(path_type=Path))
@click.option("--preload", is_flag=True, default=False, help="Preload shader cache after open.")
def open_cmd(capture: Path, preload: bool) -> None:
    """Create local default session and start daemon skeleton."""
    ok, message = open_session(capture)
    if not ok:
        click.echo(message, err=True)
        raise SystemExit(1)
    click.echo(message)
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
def close_cmd() -> None:
    """Close daemon-backed session."""
    ok, message = close_session()
    if not ok:
        click.echo(message, err=True)
        raise SystemExit(1)
    click.echo(message)
