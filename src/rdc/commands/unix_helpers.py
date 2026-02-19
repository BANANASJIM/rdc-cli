"""Unix-tool-friendly helper commands: rdc count, rdc shader-map."""

from __future__ import annotations

from typing import Any

import click

from rdc.daemon_client import send_request
from rdc.formatters.tsv import format_row
from rdc.protocol import _request
from rdc.session_state import load_session

_COUNT_TARGETS = ["draws", "events", "resources", "triangles", "passes", "dispatches", "clears"]
_SHADER_MAP_HEADER = ["EID", "VS", "HS", "DS", "GS", "PS", "CS"]
_SHADER_MAP_COLS = ["eid", "vs", "hs", "ds", "gs", "ps", "cs"]


def _require_session() -> tuple[str, int, str]:
    """Load active session or exit with error.

    Returns:
        Tuple of (host, port, token).
    """
    session = load_session()
    if session is None:
        click.echo("error: no active session (run 'rdc open' first)", err=True)
        raise SystemExit(1)
    return session.host, session.port, session.token


def _get_count_value(what: str, pass_name: str | None = None) -> int:
    """Get count value from daemon."""
    host, port, token = _require_session()
    params: dict[str, Any] = {"_token": token, "what": what}
    if pass_name is not None:
        params["pass"] = pass_name
    payload = _request("count", 1, params).to_dict()
    response = send_request(host, port, payload)
    if "error" in response:
        click.echo(f"error: {response['error']['message']}", err=True)
        raise SystemExit(1)
    value: int = response["result"]["value"]
    return value


def _get_shader_map_rows() -> list[dict[str, Any]]:
    """Get shader-map rows from daemon."""
    host, port, token = _require_session()
    payload = _request("shader_map", 1, {"_token": token}).to_dict()
    response = send_request(host, port, payload)
    if "error" in response:
        click.echo(f"error: {response['error']['message']}", err=True)
        raise SystemExit(1)
    rows: list[dict[str, Any]] = response["result"]["rows"]
    return rows


@click.command("count")
@click.argument("what", type=click.Choice(_COUNT_TARGETS, case_sensitive=False))
@click.option("--pass", "pass_name", default=None, help="Filter by render pass name.")
def count_cmd(what: str, pass_name: str | None) -> None:
    """Output a single integer count to stdout.

    Targets: draws, events, resources, triangles, passes, dispatches, clears.
    """
    value = _get_count_value(what, pass_name)
    click.echo(value)


@click.command("shader-map")
@click.option("--no-header", is_flag=True, default=False, help="Omit TSV header row.")
def shader_map_cmd(no_header: bool) -> None:
    """Output EID-to-shader mapping as TSV."""
    rows = _get_shader_map_rows()
    if not no_header:
        click.echo(format_row(_SHADER_MAP_HEADER))
    for row in rows:
        click.echo(format_row([row[c] for c in _SHADER_MAP_COLS]))
