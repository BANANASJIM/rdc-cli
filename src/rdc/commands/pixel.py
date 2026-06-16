"""rdc pixel command -- pixel history query."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands._helpers import call, complete_eid
from rdc.commands.vfs import _fmt_pixel_mod
from rdc.formatters.json_fmt import write_json
from rdc.formatters.options import list_output_options, render_list


@click.command("pixel")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.argument("eid", required=False, type=int, shell_complete=complete_eid)
@click.option("--target", default=0, type=int, help="Color target index (default 0)")
@click.option("--sample", default=0, type=int, help="MSAA sample index (default 0)")
@list_output_options
def pixel_cmd(
    x: int,
    y: int,
    eid: int | None,
    target: int,
    sample: int,
    use_json: bool,
    no_header: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """Query pixel history at (X, Y) for the current or specified event."""
    params: dict[str, Any] = {"x": x, "y": y, "target": target, "sample": sample}
    if eid is not None:
        params["eid"] = eid

    result = call("pixel_history", params)

    if use_json:
        write_json(result)
        return

    modifications = result.get("modifications", [])

    def _table() -> None:
        if not no_header:
            click.echo("EID\tFRAG\tDEPTH\tPASSED\tFLAGS")
        for m in modifications:
            click.echo(_fmt_pixel_mod(m))

    render_list(
        modifications,
        use_json=False,
        use_jsonl=use_jsonl,
        quiet=quiet,
        quiet_key="eid",
        table=_table,
    )
