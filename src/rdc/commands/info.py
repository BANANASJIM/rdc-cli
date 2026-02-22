"""Commands: rdc info, rdc stats, rdc log."""

from __future__ import annotations

import sys
from typing import Any

import click

from rdc.commands._helpers import call
from rdc.formatters.json_fmt import write_json
from rdc.formatters.tsv import write_tsv


def _daemon_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Backward-compatible wrapper around call() for other command modules."""
    return call(method, params or {})


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
    result = call("info", {})
    if use_json:
        write_json(result)
        return
    _format_kv(result)


@click.command("stats")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--no-header", is_flag=True, help="Omit TSV header")
def stats_cmd(use_json: bool, no_header: bool) -> None:
    """Show per-pass breakdown, top draws, largest resources."""
    result = call("stats", {})
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


@click.command("log")
@click.option(
    "--level",
    default=None,
    type=click.Choice(["HIGH", "MEDIUM", "LOW", "INFO", "UNKNOWN"], case_sensitive=False),
    help="Filter by severity.",
)
@click.option("--eid", default=None, type=int, help="Filter by event ID.")
@click.option("--no-header", is_flag=True, help="Omit TSV header")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def log_cmd(level: str | None, eid: int | None, no_header: bool, use_json: bool) -> None:
    """Show debug/validation messages from the capture."""
    rpc_params: dict[str, Any] = {}
    if level is not None:
        rpc_params["level"] = level
    if eid is not None:
        rpc_params["eid"] = eid
    result = call("log", rpc_params)
    messages = result.get("messages", [])
    if use_json:
        write_json(messages)
        return

    def _sanitize(text: str) -> str:
        return text.replace("\t", " ").replace("\n", " ")

    rows = [
        [m.get("level", "-"), m.get("eid", 0), _sanitize(str(m.get("message", "-")))]
        for m in messages
    ]
    write_tsv(rows, header=["LEVEL", "EID", "MESSAGE"], no_header=no_header)
