"""Pipeline and shader inspection commands."""

from __future__ import annotations

from typing import Any, cast

import click

from rdc.daemon_client import send_request
from rdc.formatters.tsv import format_row
from rdc.protocol import _request
from rdc.session_state import load_session

_STAGE_CHOICES = ["vs", "hs", "ds", "gs", "ps", "cs"]


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


@click.command("pipeline")
@click.argument("eid", required=False, type=int)
@click.argument("section", required=False)
def pipeline_cmd(eid: int | None, section: str | None) -> None:
    """Show pipeline summary for current or specified EID."""
    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    if section is not None:
        params["section"] = section

    result = _call("pipeline", params)
    row = result.get("row", {})
    click.echo(format_row(["EID", "API", "TOPOLOGY", "GFX_PIPE", "COMP_PIPE"]))
    click.echo(
        format_row(
            [
                row.get("eid", "-"),
                row.get("api", "-"),
                row.get("topology", "-"),
                row.get("graphics_pipeline", "-"),
                row.get("compute_pipeline", "-"),
            ]
        )
    )


@click.command("bindings")
@click.argument("eid", required=False, type=int)
def bindings_cmd(eid: int | None) -> None:
    """Show bound resources per shader stage."""
    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    result = _call("bindings", params)
    rows: list[dict[str, Any]] = result.get("rows", [])

    click.echo(format_row(["EID", "STAGE", "KIND", "SLOT", "NAME"]))
    for row in rows:
        click.echo(
            format_row(
                [
                    row.get("eid", "-"),
                    row.get("stage", "-"),
                    row.get("kind", "-"),
                    row.get("slot", "-"),
                    row.get("name", "-"),
                ]
            )
        )


@click.command("shader")
@click.argument("eid", required=False, type=int)
@click.argument("stage", required=False, type=click.Choice(_STAGE_CHOICES, case_sensitive=False))
def shader_cmd(eid: int | None, stage: str | None) -> None:
    """Show shader metadata for a stage at EID."""
    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    if stage is not None:
        params["stage"] = stage

    result = _call("shader", params)
    row = result.get("row", {})
    click.echo(format_row(["EID", "STAGE", "SHADER", "ENTRY", "RO", "RW", "CBUFFERS"]))
    click.echo(
        format_row(
            [
                row.get("eid", "-"),
                row.get("stage", "-"),
                row.get("shader", "-"),
                row.get("entry", "-"),
                row.get("ro", 0),
                row.get("rw", 0),
                row.get("cbuffers", 0),
            ]
        )
    )


@click.command("shaders")
def shaders_cmd() -> None:
    """List unique shaders in capture."""
    result = _call("shaders", {})
    rows: list[dict[str, Any]] = result.get("rows", [])
    click.echo(format_row(["SHADER", "STAGES", "USES"]))
    for row in rows:
        click.echo(format_row([row.get("shader", "-"), row.get("stages", "-"), row.get("uses", 0)]))
