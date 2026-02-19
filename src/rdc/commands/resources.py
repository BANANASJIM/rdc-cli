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


@click.command("passes")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output JSON.")
def passes_cmd(as_json: bool) -> None:
    """List render passes."""
    result = _call("passes", {})
    tree: dict[str, Any] = result.get("tree", {})
    if as_json:
        write_json(tree)
        return

    passes = tree.get("passes", [])
    click.echo(format_row(["NAME", "DRAWS"]))
    for p in passes:
        click.echo(format_row([p.get("name", "-"), p.get("draws", 0)]))


@click.command("pass")
@click.argument("identifier")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output JSON.")
def pass_cmd(identifier: str, as_json: bool) -> None:
    """Show detail for a single render pass by index or name."""
    params: dict[str, Any] = {}
    try:
        params["index"] = int(identifier)
    except ValueError:
        params["name"] = identifier
    result = _call("pass", params)
    if as_json:
        write_json(result)
        return
    _format_pass_detail(result)


def _format_pass_detail(data: dict[str, Any]) -> None:
    color_ids = [str(t["id"]) for t in data.get("color_targets", [])]
    depth = data.get("depth_target")
    kv = {
        "Pass": data.get("name", "-"),
        "Begin EID": data.get("begin_eid", "-"),
        "End EID": data.get("end_eid", "-"),
        "Draw Calls": data.get("draws", 0),
        "Dispatches": data.get("dispatches", 0),
        "Triangles": data.get("triangles", 0),
        "Color Targets": ", ".join(color_ids) if color_ids else "-",
        "Depth Target": depth if depth else "-",
    }
    max_key = max(len(k) for k in kv)
    for key, value in kv.items():
        label = key + ":"
        click.echo(f"{label:<{max_key + 2}}{value}")
