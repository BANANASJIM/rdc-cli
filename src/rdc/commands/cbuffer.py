"""rdc cbuffer -- decoded or raw constant-buffer export."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands._helpers import call, complete_eid
from rdc.commands.export import _export_vfs_path
from rdc.formatters.json_fmt import write_json


@click.command("cbuffer")
@click.argument("eid", type=int, required=False, default=None, shell_complete=complete_eid)
@click.option(
    "--stage",
    type=click.Choice(["vs", "hs", "ds", "gs", "ps", "cs"]),
    default="ps",
    help="Shader stage (default: ps)",
)
@click.option("--set", "cb_set", type=int, default=0, help="Descriptor set / register space")
@click.option("--binding", type=int, default=0, help="Binding / register number")
@click.option("--json", "use_json", is_flag=True, help="JSON output (default)")
@click.option("--raw", is_flag=True, help="Export raw constant-buffer bytes")
@click.option("-o", "--output", type=click.Path(), default=None, help="Write raw bytes to file")
def cbuffer_cmd(
    eid: int | None,
    stage: str,
    cb_set: int,
    binding: int,
    use_json: bool,
    raw: bool,
    output: str | None,
) -> None:
    """Decode a constant buffer to JSON or export its raw bytes."""
    if raw:
        if output is None:
            raise click.UsageError("-o/--output is required with --raw")
        target = eid if eid is not None else 0
        _export_vfs_path(f"/draws/{target}/cbuffer/{cb_set}/{binding}/data", output, raw)
        return

    del use_json
    params: dict[str, Any] = {"stage": stage, "set": cb_set, "binding": binding}
    if eid is not None:
        params["eid"] = eid
    result = call("cbuffer_decode", params)
    write_json(result)
