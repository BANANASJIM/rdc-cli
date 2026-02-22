"""rdc pixel command -- pixel history query."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands.info import _daemon_call
from rdc.formatters.json_fmt import write_json


@click.command("pixel")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.argument("eid", required=False, type=int)
@click.option("--target", default=0, type=int, help="Color target index (default 0)")
@click.option("--sample", default=0, type=int, help="MSAA sample index (default 0)")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--no-header", is_flag=True, help="Suppress TSV header row")
def pixel_cmd(
    x: int,
    y: int,
    eid: int | None,
    target: int,
    sample: int,
    use_json: bool,
    no_header: bool,
) -> None:
    """Query pixel history at (X, Y) for the current or specified event."""
    params: dict[str, Any] = {"x": x, "y": y, "target": target, "sample": sample}
    if eid is not None:
        params["eid"] = eid

    result = _daemon_call("pixel_history", params)

    if use_json:
        write_json(result)
        return

    if not no_header:
        click.echo("EID\tFRAG\tDEPTH\tPASSED\tFLAGS")

    for m in result.get("modifications", []):
        d = m["depth"]
        depth_s = f"{d:.4f}" if d is not None else "-"
        passed_s = "yes" if m["passed"] else "no"
        flags_s = ",".join(m["flags"]) or "-"
        click.echo(f"{m['eid']}\t{m['fragment']}\t{depth_s}\t{passed_s}\t{flags_s}")
