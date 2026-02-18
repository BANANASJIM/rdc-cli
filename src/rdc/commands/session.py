from __future__ import annotations

from pathlib import Path

import click

from rdc.session_state import (
    create_session,
    delete_session,
    load_session,
    save_session,
    session_path,
)


@click.command("open")
@click.argument("capture", type=click.Path(path_type=Path))
def open_cmd(capture: Path) -> None:
    """Create a local default session for a capture path."""
    state = create_session(str(capture))
    click.echo(f"opened: {state.capture}")
    click.echo(f"session: {session_path()}")


@click.command("status")
def status_cmd() -> None:
    """Show current local session status."""
    state = load_session()
    if state is None:
        click.echo("error: no active session", err=True)
        raise SystemExit(1)

    click.echo(f"capture: {state.capture}")
    click.echo(f"current_eid: {state.current_eid}")
    click.echo(f"opened_at: {state.opened_at}")


@click.command("goto")
@click.argument("eid", type=int)
def goto_cmd(eid: int) -> None:
    """Update current event id in local session."""
    if eid < 0:
        click.echo("error: eid must be >= 0", err=True)
        raise SystemExit(1)

    state = load_session()
    if state is None:
        click.echo("error: no active session", err=True)
        raise SystemExit(1)

    state.current_eid = eid
    save_session(state)
    click.echo(f"current_eid set to {eid}")


@click.command("close")
def close_cmd() -> None:
    """Close local session (remove session file)."""
    removed = delete_session()
    if not removed:
        click.echo("error: no active session", err=True)
        raise SystemExit(1)
    click.echo("session closed")
