"""Resources inspection commands."""

from __future__ import annotations

from typing import Any, cast

import click

from rdc.daemon_client import send_request
from rdc.formatters.json_fmt import write_json
from rdc.formatters.tsv import format_row
from rdc.protocol import _request
from rdc.session_state import load_session


def _require_session() -> tuple[str, int, str]:
    session = load_session()
    if session is None:
        click.echo("error: no active session (run 'rdc open' first)", err=True)
        raise SystemExit(1)
    return session.host, session.port, session.token


def _call(method: str, params: dict[str, Any]) -> dict[str, Any]:
    host, port, token = _require_session()
    payload = _request(method, 1, {"_token": token, **params}).to_dict()
    response = send_request(host, port, payload)
    if "error" in response:
        click.echo(f"error: {response['error']['message']}", err=True)
        raise SystemExit(1)
    return cast(dict[str, Any], response["result"])


@click.command("resources")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output JSON.")
def resources_cmd(as_json: bool) -> None:
    """List all resources."""
    result = _call("resources", {})
    rows: list[dict[str, Any]] = result.get("rows", [])
    if as_json:
        write_json(rows)
        return

    click.echo(format_row(["ID", "TYPE", "NAME", "WIDTH", "HEIGHT", "DEPTH", "FORMAT"]))
    for row in rows:
        click.echo(
            format_row(
                [
                    row.get("id", "-"),
                    row.get("type", "-"),
                    row.get("name", "-"),
                    row.get("width", 0),
                    row.get("height", 0),
                    row.get("depth", 0),
                    row.get("format", "-"),
                ]
            )
        )


@click.command("resource")
@click.argument("resid", type=int)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output JSON.")
def resource_cmd(resid: int, as_json: bool) -> None:
    """Show details of a specific resource."""
    result = _call("resource", {"id": resid})
    res = result.get("resource", {})
    if as_json:
        write_json(res)
        return

    click.echo(format_row(["PROPERTY", "VALUE"]))
    for k, v in res.items():
        click.echo(format_row([str(k).upper(), str(v)]))
