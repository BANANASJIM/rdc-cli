"""Pipeline and shader inspection commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import click

from rdc.daemon_client import send_request
from rdc.formatters.json_fmt import write_json
from rdc.formatters.tsv import format_row
from rdc.protocol import _request
from rdc.session_state import load_session

_STAGE_CHOICES = ["vs", "hs", "ds", "gs", "ps", "cs"]
_SORT_CHOICES = ["name", "stage", "uses"]


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
@click.option("--json", "as_json", is_flag=True, default=False, help="Output JSON.")
def pipeline_cmd(eid: int | None, section: str | None, as_json: bool) -> None:
    """Show pipeline summary for current or specified EID.

    EID is the event ID. SECTION is optional (e.g., 'vs', 'ps').
    """
    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    if section is not None:
        params["section"] = section

    result = _call("pipeline", params)
    row = result.get("row", {})
    if as_json:
        write_json(row)
        return
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
    section_detail = row.get("section_detail")
    if isinstance(section_detail, dict):
        click.echo()
        click.echo(format_row(["SECTION", "SHADER", "ENTRY", "RO", "RW", "CBUFFERS"]))
        click.echo(
            format_row(
                [
                    section_detail.get("stage", "-"),
                    section_detail.get("shader", "-"),
                    section_detail.get("entry", "-"),
                    section_detail.get("ro", 0),
                    section_detail.get("rw", 0),
                    section_detail.get("cbuffers", 0),
                ]
            )
        )


@click.command("bindings")
@click.argument("eid", required=False, type=int)
@click.option("--set", "descriptor_set", type=int, help="Filter by descriptor set number.")
@click.option("--binding", "binding_index", type=int, help="Filter by binding index.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output JSON.")
def bindings_cmd(
    eid: int | None, descriptor_set: int | None, binding_index: int | None, as_json: bool
) -> None:
    """Show bound resources per shader stage.

    EID is the event ID.
    Use --set to filter by descriptor set.
    Use --binding to filter by binding index.
    """
    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    if descriptor_set is not None:
        params["set"] = descriptor_set
    if binding_index is not None:
        params["binding"] = binding_index

    result = _call("bindings", params)
    rows: list[dict[str, Any]] = result.get("rows", [])
    if as_json:
        write_json(rows)
        return

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
@click.option(
    "--reflect",
    "get_reflect",
    is_flag=True,
    help="Include reflection data (inputs/outputs/cbuffers).",
)
@click.option("--constants", "get_constants", is_flag=True, help="Include constant buffer values.")
@click.option("--source", "get_source", is_flag=True, help="Include debug source code.")
@click.option(
    "--target",
    "target",
    type=str,
    help="Disassembly target format (e.g., 'dxil', 'spirv', 'glsl').",
)
@click.option("--targets", "list_targets", is_flag=True, help="List available disassembly targets.")
@click.option(
    "-o", "--output", "output_path", type=click.Path(path_type=Path), help="Output file path."
)
@click.option("--all", "get_all", is_flag=True, help="Get all shader data for all stages.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output JSON.")
def shader_cmd(
    eid: int | None,
    stage: str | None,
    get_reflect: bool,
    get_constants: bool,
    get_source: bool,
    target: str | None,
    list_targets: bool,
    output_path: Path | None,
    get_all: bool,
    as_json: bool,
) -> None:
    """Show shader metadata for a stage at EID.

    EID is the event ID. STAGE is the shader stage (vs, hs, ds, gs, ps, cs).
    Use --all to get data for all stages.
    """
    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    if stage is not None:
        params["stage"] = stage
    if get_reflect:
        params["reflect"] = True
    if get_constants:
        params["constants"] = True
    if get_source:
        params["source"] = True
    if target is not None:
        params["target"] = target
    if list_targets:
        params["list_targets"] = True
    if output_path is not None:
        params["output"] = str(output_path)
    if get_all:
        params["all"] = True

    # Handle list_targets specially - just show available targets and return
    if list_targets:
        result = _call("shader_targets", {})
        targets_list: list[dict[str, Any]] = result.get("targets", [])
        if as_json:
            write_json(targets_list)
            return
        click.echo(format_row(["TARGET", "DESCRIPTION"]))
        for t in targets_list:
            click.echo(format_row([t.get("name", "-"), t.get("description", "-")]))
        return

    # Handle --all - get all shaders
    if get_all:
        result = _call("shader_all", params)
        rows: list[dict[str, Any]] = result.get("rows", [])
        if as_json:
            write_json(rows)
            return
        click.echo(format_row(["EID", "STAGE", "SHADER", "ENTRY", "RO", "RW", "CBUFFERS"]))
        for row in rows:
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
        return

    # Single shader query
    result = _call("shader", params)
    row = result.get("row", {})
    if as_json:
        write_json(row)
        return

    # Handle output file for source/disassembly
    if get_source or target:
        output_file = output_path if output_path else None
        if output_file:
            content = row.get("content", "")
            output_file.write_text(content)
            click.echo(f"Written to {output_file}", err=True)
            return

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

    # Show reflection data if requested
    if get_reflect:
        reflect = row.get("reflection", {})
        if reflect:
            click.echo()
            click.echo("=== INPUTS ===")
            inputs = reflect.get("inputs", [])
            for inp in inputs:
                click.echo(
                    format_row(
                        [inp.get("name", "-"), inp.get("type", "-"), inp.get("location", "-")]
                    )
                )
            click.echo("=== OUTPUTS ===")
            outputs = reflect.get("outputs", [])
            for out in outputs:
                click.echo(
                    format_row(
                        [out.get("name", "-"), out.get("type", "-"), out.get("location", "-")]
                    )
                )
            click.echo("=== CBUFFERS ===")
            cbuffers = reflect.get("cbuffers", [])
            for cb in cbuffers:
                click.echo(
                    format_row([cb.get("name", "-"), cb.get("slot", "-"), cb.get("vars", 0)])
                )

    # Show constants if requested
    if get_constants:
        constants = row.get("constants", {})
        if constants:
            click.echo()
            click.echo("=== CONSTANTS ===")
            cbuffers = constants.get("cbuffers", [])
            for cb in cbuffers:
                click.echo(format_row(["CBUFFER", cb.get("name", "-"), cb.get("slot", "-")]))
                vars_list = cb.get("vars", [])
                for v in vars_list:
                    click.echo(
                        format_row(
                            ["  ", v.get("name", "-"), v.get("type", "-"), v.get("value", "-")]
                        )
                    )


@click.command("shaders")
@click.option(
    "--stage",
    "stage_filter",
    type=click.Choice(_STAGE_CHOICES, case_sensitive=False),
    help="Filter by shader stage.",
)
@click.option(
    "--sort",
    "sort_by",
    type=click.Choice(_SORT_CHOICES, case_sensitive=False),
    default="name",
    help="Sort order.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output JSON.")
def shaders_cmd(stage_filter: str | None, sort_by: str, as_json: bool) -> None:
    """List unique shaders in capture.

    Use --stage to filter by stage, --sort to change sort order.
    """
    params: dict[str, Any] = {}
    if stage_filter is not None:
        params["stage"] = stage_filter
    if sort_by is not None:
        params["sort"] = sort_by

    result = _call("shaders", params)
    rows: list[dict[str, Any]] = result.get("rows", [])
    if as_json:
        write_json(rows)
        return
    click.echo(format_row(["SHADER", "STAGES", "USES"]))
    for row in rows:
        click.echo(format_row([row.get("shader", "-"), row.get("stages", "-"), row.get("uses", 0)]))
