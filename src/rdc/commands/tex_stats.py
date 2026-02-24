"""rdc tex-stats command -- texture min/max and histogram."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands._helpers import call
from rdc.formatters.json_fmt import write_json
from rdc.formatters.tsv import write_tsv


@click.command("tex-stats")
@click.argument("resource_id", type=int)
@click.argument("eid", required=False, type=int)
@click.option("--mip", default=0, type=int, help="Mip level (default 0)")
@click.option("--slice", "array_slice", default=0, type=int, help="Array slice (default 0)")
@click.option("--histogram", is_flag=True, help="Show 256-bucket histogram")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def tex_stats_cmd(
    resource_id: int,
    eid: int | None,
    mip: int,
    array_slice: int,
    histogram: bool,
    use_json: bool,
) -> None:
    """Show texture min/max statistics and optional histogram."""
    params: dict[str, Any] = {"id": resource_id, "mip": mip, "slice": array_slice}
    if histogram:
        params["histogram"] = True
    if eid is not None:
        params["eid"] = eid
    result = call("tex_stats", params)
    if use_json:
        write_json(result)
        return
    mn, mx = result["min"], result["max"]
    header = ["CHANNEL", "MIN", "MAX"]
    rows = [
        ["R", f"{mn['r']:.4f}", f"{mx['r']:.4f}"],
        ["G", f"{mn['g']:.4f}", f"{mx['g']:.4f}"],
        ["B", f"{mn['b']:.4f}", f"{mx['b']:.4f}"],
        ["A", f"{mn['a']:.4f}", f"{mx['a']:.4f}"],
    ]
    write_tsv(rows, header=header)
    if "histogram" in result:
        click.echo()
        hist_header = ["BUCKET", "R", "G", "B", "A"]
        hist_rows = [[h["bucket"], h["r"], h["g"], h["b"], h["a"]] for h in result["histogram"]]
        write_tsv(hist_rows, header=hist_header)
