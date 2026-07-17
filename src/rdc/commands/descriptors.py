"""Used-descriptor inspection command."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands._helpers import call, complete_eid
from rdc.formatters.options import list_output_options, render_list
from rdc.formatters.tsv import write_tsv

_STAGE_CHOICES = ["vs", "hs", "ds", "gs", "ps", "cs"]


@click.command("descriptors")
@click.argument("eid", required=False, type=int, shell_complete=complete_eid)
@click.option(
    "--stage",
    "stage_filter",
    type=click.Choice(_STAGE_CHOICES, case_sensitive=False),
    help="Filter by shader stage.",
)
@click.option("--type", "type_filter", help="Filter by descriptor type (case-insensitive).")
@click.option("--binding", "binding_filter", help="Filter by binding name or number.")
@list_output_options
def descriptors_cmd(  # noqa: PLR0913
    eid: int | None,
    stage_filter: str | None,
    type_filter: str | None,
    binding_filter: str | None,
    no_header: bool,
    use_json: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """Show the descriptors a draw actually used, resolved to resources.

    Each array element a shader read is listed with its resolved binding name
    (e.g. g_textures), resource, and texture dimensions -- the per-draw view
    that maps a bindless index to its concrete texture.
    """
    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    if stage_filter is not None:
        params["stage"] = stage_filter
    if type_filter is not None:
        params["type"] = type_filter
    if binding_filter is not None:
        params["binding"] = binding_filter

    result = call("descriptors", params)
    rows: list[dict[str, Any]] = result.get("descriptors", [])
    row_eid = result.get("eid", "-")

    def _table() -> None:
        tsv_rows = [
            [
                row_eid,
                r.get("stage", "-"),
                r.get("binding", "-"),
                r.get("type", "-"),
                r.get("set", "-"),
                r.get("array_element", "-"),
                r.get("resource_id", "-"),
                r.get("resource_name", "-"),
                r.get("format", "-"),
                r.get("width", "-"),
                r.get("height", "-"),
                r.get("depth", "-"),
            ]
            for r in rows
        ]
        write_tsv(
            tsv_rows,
            header=[
                "EID",
                "STAGE",
                "BINDING",
                "TYPE",
                "SET",
                "ARRAY_EL",
                "RESOURCE",
                "RES_NAME",
                "FORMAT",
                "WIDTH",
                "HEIGHT",
                "DEPTH",
            ],
            no_header=no_header,
        )

    render_list(
        rows,
        use_json=use_json,
        use_jsonl=use_jsonl,
        quiet=quiet,
        quiet_key="resource_id",
        table=_table,
    )
