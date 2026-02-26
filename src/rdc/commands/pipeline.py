"""Pipeline and shader inspection commands."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click
from click.shell_completion import CompletionItem

from rdc.commands._helpers import call
from rdc.formatters.json_fmt import write_json, write_jsonl
from rdc.formatters.options import list_output_options
from rdc.formatters.tsv import format_row, write_tsv
from rdc.services.query_service import STAGE_MAP

_STAGE_CHOICES = ["vs", "hs", "ds", "gs", "ps", "cs"]
_SORT_CHOICES = ["name", "stage", "uses"]
_SHADER_STAGES_CLI: frozenset[str] = frozenset(STAGE_MAP)


@click.command("pipeline")
@click.argument("eid", required=False, type=int)
@click.argument("section", required=False)
@click.option("--json", "use_json", is_flag=True, default=False, help="Output JSON.")
def pipeline_cmd(eid: int | None, section: str | None, use_json: bool) -> None:
    """Show pipeline summary for current or specified EID.

    EID is the event ID. SECTION is optional (e.g., 'vs', 'ps', 'topology', 'blend').
    """
    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    if section is not None:
        params["section"] = section

    section_lower = section.lower() if section else None
    is_non_shader_section = section_lower is not None and section_lower not in _SHADER_STAGES_CLI

    result = call("pipeline", params)

    if is_non_shader_section:
        # Non-shader sections return the pipe_* result directly (not wrapped in "row")
        if use_json:
            write_json(result)
            return
        click.echo(format_row(["KEY", "VALUE"]))
        for k, v in result.items():
            if k != "eid":
                click.echo(format_row([k, str(v)]))
        return

    row = result.get("row", {})
    if use_json:
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
@click.option("--binding", "binding_index", type=int, help="Filter by binding index.")
@click.option("--set", "set_index", type=int, help="Filter by descriptor set index.")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output JSON.")
@list_output_options
def bindings_cmd(
    eid: int | None,
    binding_index: int | None,
    set_index: int | None,
    use_json: bool,
    no_header: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """Show bound resources per shader stage.

    EID is the event ID. Use --binding to filter by slot, --set to filter by descriptor set.
    """
    params: dict[str, Any] = {}
    if eid is not None:
        params["eid"] = eid
    if binding_index is not None:
        params["binding"] = binding_index
    if set_index is not None:
        params["set"] = set_index

    result = call("bindings", params)
    rows: list[dict[str, Any]] = result.get("rows", [])
    if use_json:
        write_json(rows)
    elif use_jsonl:
        write_jsonl(rows)
    elif quiet:
        for r in rows:
            sys.stdout.write(str(r.get("eid", "")) + "\n")
    else:
        tsv_rows = [
            [
                r.get("eid", "-"),
                r.get("stage", "-"),
                r.get("kind", "-"),
                r.get("set", 0),
                r.get("slot", "-"),
                r.get("name", "-"),
            ]
            for r in rows
        ]
        hdr = ["EID", "STAGE", "KIND", "SET", "SLOT", "NAME"]
        write_tsv(tsv_rows, header=hdr, no_header=no_header)


@click.command("shader")
@click.argument(
    "first",
    required=False,
    metavar="[EID|STAGE]",
    shell_complete=lambda _ctx, _param, incomplete: [
        CompletionItem(stage) for stage in _STAGE_CHOICES if stage.startswith(incomplete.lower())
    ],
)
@click.argument(
    "second",
    required=False,
    metavar="[STAGE]",
    shell_complete=lambda _ctx, _param, incomplete: [
        CompletionItem(stage) for stage in _STAGE_CHOICES if stage.startswith(incomplete.lower())
    ],
)
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
@click.option("--json", "use_json", is_flag=True, default=False, help="Output JSON.")
def shader_cmd(
    first: str | None,
    second: str | None,
    get_reflect: bool,
    get_constants: bool,
    get_source: bool,
    target: str | None,
    list_targets: bool,
    output_path: Path | None,
    get_all: bool,
    use_json: bool,
) -> None:
    """Show shader metadata for a stage at EID.

    Positional forms: ``shader [STAGE]`` or ``shader [EID] [STAGE]``.
    EID is the event ID. STAGE is one of ``vs/hs/ds/gs/ps/cs``.
    Use --all to get data for all stages.
    """
    eid, stage = _parse_shader_positionals(first, second)

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
        result = call("shader_targets", {})
        targets_list: list[str] = result.get("targets", [])
        if use_json:
            write_json(targets_list)
            return
        click.echo(format_row(["TARGET"]))
        for t in targets_list:
            click.echo(format_row([t]))
        return

    # Handle --all - get all shaders
    if get_all:
        result = call("shader_all", params)
        rows: list[dict[str, Any]] = result.get("stages", [])
        if use_json:
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

    # --target dispatches to shader_disasm
    if target is not None:
        disasm_params: dict[str, Any] = {"target": target}
        if eid is None and stage is None:
            disasm_params["eid"] = 0
            disasm_params["stage"] = "ps"
        else:
            if eid is not None:
                disasm_params["eid"] = eid
            if stage is not None:
                disasm_params["stage"] = stage
        disasm_result = call("shader_disasm", disasm_params)
        if use_json:
            write_json(disasm_result)
            return
        content: str = disasm_result.get("disasm", "")
        if output_path:
            output_path.write_text(content)
            click.echo(f"Written to {output_path}", err=True)
        else:
            click.echo(content)
        return

    # Single shader query
    result = call("shader", params)
    row = result.get("row", {})
    if use_json:
        write_json(row)
        return

    # Handle output file for source
    if get_source:
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


def _parse_shader_positionals(
    first: str | None, second: str | None
) -> tuple[int | None, str | None]:
    """Parse shader positional arguments as ``[eid] [stage]`` or ``[stage]``."""
    if first is None:
        return None, None

    first_lower = first.lower()
    if first_lower in _SHADER_STAGES_CLI:
        if second is not None:
            msg = "unexpected extra argument when using stage-only form"
            raise click.BadParameter(msg, param_hint="SECOND")
        return None, first_lower

    try:
        eid = int(first)
    except ValueError as exc:
        msg = f"'{first}' is not a valid EID or shader stage (vs, hs, ds, gs, ps, cs)"
        raise click.BadParameter(msg, param_hint="FIRST") from exc

    if second is None:
        return eid, None

    stage = second.lower()
    if stage not in _SHADER_STAGES_CLI:
        allowed = ", ".join(_STAGE_CHOICES)
        msg = f"'{second}' is not a valid stage (choose from {allowed})"
        raise click.BadParameter(msg, param_hint="SECOND")
    return eid, stage


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
@click.option("--json", "use_json", is_flag=True, default=False, help="Output JSON.")
@list_output_options
def shaders_cmd(
    stage_filter: str | None,
    sort_by: str,
    use_json: bool,
    no_header: bool,
    use_jsonl: bool,
    quiet: bool,
) -> None:
    """List unique shaders in capture.

    Use --stage to filter by stage, --sort to change sort order.
    """
    params: dict[str, Any] = {}
    if stage_filter is not None:
        params["stage"] = stage_filter
    if sort_by is not None:
        params["sort"] = sort_by

    result = call("shaders", params)
    rows: list[dict[str, Any]] = result.get("rows", [])
    if use_json:
        write_json(rows)
    elif use_jsonl:
        write_jsonl(rows)
    elif quiet:
        for r in rows:
            sys.stdout.write(str(r.get("shader", "")) + "\n")
    else:
        tsv_rows = [[r.get("shader", "-"), r.get("stages", "-"), r.get("uses", 0)] for r in rows]
        write_tsv(tsv_rows, header=["SHADER", "STAGES", "USES"], no_header=no_header)
