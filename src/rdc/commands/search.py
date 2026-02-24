"""rdc search command — grep-style shader disassembly search."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands.info import _daemon_call
from rdc.formatters.json_fmt import write_json


@click.command("search")
@click.argument("pattern")
@click.option("--stage", default=None, help="Filter by stage (vs/ps/cs/...).")
@click.option("--limit", type=int, default=200, show_default=True, help="Max results.")
@click.option("-C", "--context", type=int, default=0, help="Context lines.")
@click.option("--case-sensitive", is_flag=True, help="Case-sensitive search.")
@click.option("--json", "use_json", is_flag=True, help="JSON output.")
def search_cmd(
    pattern: str,
    stage: str | None,
    limit: int,
    context: int,
    case_sensitive: bool,
    use_json: bool,
) -> None:
    """Search shader disassembly text for PATTERN (regex).

    Searches across all unique shaders in the capture. Case-insensitive by
    default; use --case-sensitive to enable exact case matching.
    """
    params: dict[str, Any] = {
        "pattern": pattern,
        "limit": limit,
        "context": context,
        "case_sensitive": case_sensitive,
    }
    if stage is not None:
        params["stage"] = stage

    result = _daemon_call("search", params)
    matches: list[dict[str, Any]] = result.get("matches", [])
    truncated: bool = result.get("truncated", False)

    if use_json:
        write_json({"matches": matches, "truncated": truncated})
        return

    if not matches:
        return

    for m in matches:
        shader_id = m.get("shader", 0)
        stages = ",".join(m.get("stages", []))
        lineno = m.get("line", 0)
        text = m.get("text", "")
        prefix = f"shader:{shader_id}[{stages}]:{lineno}"

        for ctx_line in m.get("context_before", []):
            click.echo(f"{prefix}-{ctx_line}")
        click.echo(f"{prefix}:{text}")
        for ctx_line in m.get("context_after", []):
            click.echo(f"{prefix}-{ctx_line}")

    if truncated:
        click.echo(f"(results truncated at {limit})", err=True)
