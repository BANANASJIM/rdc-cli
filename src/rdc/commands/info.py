"""Commands: rdc info, rdc stats."""

from __future__ import annotations

import sys
from typing import Any

import click

from rdc.daemon_client import send_request
from rdc.formatters.json_fmt import write_json
from rdc.formatters.tsv import write_tsv
from rdc.session_state import load_session


def _daemon_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    state = load_session()
    if state is None:
        click.echo("error: no active session", err=True)
        raise SystemExit(1)
    rpc_params: dict[str, Any] = {"_token": state.token}
    if params:
        rpc_params.update(params)
    try:
        resp = send_request(
            state.host,
            state.port,
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": rpc_params},
        )
    except Exception as exc:
        click.echo(f"error: daemon unreachable: {exc}", err=True)
        raise SystemExit(1) from exc
    if "error" in resp:
        click.echo("error: " + resp["error"]["message"], err=True)
        raise SystemExit(1)
    result: dict[str, Any] = resp["result"]
    return result


def _format_kv(data: dict[str, Any], out: Any = None) -> None:
    dest = out or sys.stdout
    max_key = max((len(str(k)) for k in data), default=0)
    for key, value in data.items():
        if value is None or value == "":
            value = "-"
        label = str(key) + ":"
        dest.write(f"{label:<{max_key + 2}}{value}" + chr(10))


@click.command("info")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def info_cmd(use_json: bool) -> None:
    """Show capture metadata."""
    result = _daemon_call("info")
    if use_json:
        write_json(result)
        return
    _format_kv(result)


@click.command("stats")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--no-header", is_flag=True, help="Omit TSV header")
def stats_cmd(use_json: bool, no_header: bool) -> None:
    """Show per-pass breakdown, top draws, largest resources."""
    result = _daemon_call("stats")
    if use_json:
        write_json(result)
        return
    per_pass = result.get("per_pass", [])
    if per_pass:
        sys.stderr.write("Per-Pass Breakdown:" + chr(10))
        header = ["PASS", "DRAWS", "DISPATCHES", "TRIANGLES", "RT_W", "RT_H", "ATTACHMENTS"]
        rows = [
            [
                p["name"],
                p["draws"],
                p["dispatches"],
                p["triangles"],
                p.get("rt_w") or "-",
                p.get("rt_h") or "-",
                p.get("attachments", 0),
            ]
            for p in per_pass
        ]
        write_tsv(rows, header=header, no_header=no_header)
    top_draws = result.get("top_draws", [])
    if top_draws:
        sys.stderr.write(chr(10) + "Top Draws by Triangle Count:" + chr(10))
        header_d = ["EID", "MARKER", "TRIANGLES"]
        rows_d = [[d["eid"], d.get("marker", "-"), d["triangles"]] for d in top_draws]
        write_tsv(rows_d, header=header_d, no_header=no_header)
