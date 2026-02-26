"""rdc debug commands -- shader execution trace (pixel, vertex, thread)."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands._helpers import call, complete_eid
from rdc.formatters.json_fmt import write_json


def _check_debug_result(result: dict[str, Any]) -> None:
    """Exit rc=1 if debug result is missing required fields."""
    required = ("stage", "eid", "total_steps")
    missing = [k for k in required if k not in result]
    if missing:
        click.echo(f"error: incomplete debug result (missing {missing})", err=True)
        raise SystemExit(1)


@click.group("debug")
def debug_group() -> None:
    """Debug shader execution (pixel, vertex, or compute thread trace)."""


def _format_value_str(values: list[float | int]) -> str:
    """Format a flat value list as space-separated string."""
    return " ".join(str(v) for v in values)


def _print_summary(result: dict[str, Any]) -> None:
    """Print default summary output."""
    click.echo(f"stage:   {result['stage']}")
    click.echo(f"eid:     {result['eid']}")
    click.echo(f"steps:   {result['total_steps']}")
    for inp in result.get("inputs", []):
        click.echo(f"inputs:  {inp['name']} = [{_format_value_str(inp['after'])}]")
    for out in result.get("outputs", []):
        click.echo(f"outputs: {out['name']} = [{_format_value_str(out['after'])}]")


def _print_trace(result: dict[str, Any], no_header: bool) -> None:
    """Print --trace TSV output."""
    if not no_header:
        click.echo("STEP\tINSTR\tFILE\tLINE\tVAR\tTYPE\tVALUE")
    for step in result.get("trace", []):
        for ch in step.get("changes", []):
            click.echo(
                f"{step['step']}\t{step['instruction']}\t"
                f"{step['file'] or '-'}\t{step['line']}\t"
                f"{ch['name']}\t{ch['type']}\t"
                f"{_format_value_str(ch['after'])}"
            )


def _print_dump_at(result: dict[str, Any], target_line: int, no_header: bool) -> None:
    """Print --dump-at LINE variable snapshot."""
    var_snapshot: dict[str, tuple[str, str]] = {}
    for step in result.get("trace", []):
        for ch in step.get("changes", []):
            var_snapshot[ch["name"]] = (ch["type"], _format_value_str(ch["after"]))
        if step.get("line", -1) >= target_line:
            break

    if not no_header:
        click.echo("VAR\tTYPE\tVALUE")
    for name, (vtype, vstr) in var_snapshot.items():
        click.echo(f"{name}\t{vtype}\t{vstr}")


@debug_group.command("pixel")
@click.argument("eid", type=int, shell_complete=complete_eid)
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.option("--trace", "show_trace", is_flag=True, help="Full execution trace (TSV)")
@click.option("--dump-at", "dump_at", type=int, default=None, help="Var snapshot at LINE")
@click.option("--sample", type=int, default=None, help="MSAA sample index")
@click.option("--primitive", type=int, default=None, help="Primitive ID override")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--no-header", is_flag=True, help="Suppress TSV header row")
def pixel_cmd(
    eid: int,
    x: int,
    y: int,
    show_trace: bool,
    dump_at: int | None,
    sample: int | None,
    primitive: int | None,
    use_json: bool,
    no_header: bool,
) -> None:
    """Debug pixel shader at (X, Y) for event EID."""
    params: dict[str, Any] = {"eid": eid, "x": x, "y": y}
    if sample is not None:
        params["sample"] = sample
    if primitive is not None:
        params["primitive"] = primitive

    result = call("debug_pixel", params)
    _check_debug_result(result)

    if use_json:
        write_json(result)
        return

    if dump_at is not None:
        _print_dump_at(result, dump_at, no_header)
        return

    if show_trace:
        _print_trace(result, no_header)
        return

    _print_summary(result)


@debug_group.command("thread")
@click.argument("eid", type=int, shell_complete=complete_eid)
@click.argument("gx", type=int)
@click.argument("gy", type=int)
@click.argument("gz", type=int)
@click.argument("tx", type=int)
@click.argument("ty", type=int)
@click.argument("tz", type=int)
@click.option("--trace", "show_trace", is_flag=True, help="Full execution trace (TSV)")
@click.option("--dump-at", "dump_at", type=int, default=None, help="Var snapshot at LINE")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--no-header", is_flag=True, help="Suppress TSV header row")
def thread_cmd(
    eid: int,
    gx: int,
    gy: int,
    gz: int,
    tx: int,
    ty: int,
    tz: int,
    show_trace: bool,
    dump_at: int | None,
    use_json: bool,
    no_header: bool,
) -> None:
    """Debug compute shader thread at workgroup (GX,GY,GZ) thread (TX,TY,TZ)."""
    params: dict[str, Any] = {
        "eid": eid,
        "gx": gx,
        "gy": gy,
        "gz": gz,
        "tx": tx,
        "ty": ty,
        "tz": tz,
    }
    result = call("debug_thread", params)
    _check_debug_result(result)

    if use_json:
        write_json(result)
        return

    if dump_at is not None:
        _print_dump_at(result, dump_at, no_header)
        return

    if show_trace:
        _print_trace(result, no_header)
        return

    _print_summary(result)


@debug_group.command("vertex")
@click.argument("eid", type=int, shell_complete=complete_eid)
@click.argument("vtx_id", type=int)
@click.option("--trace", "show_trace", is_flag=True, help="Full execution trace (TSV)")
@click.option("--dump-at", "dump_at", type=int, default=None, help="Var snapshot at LINE")
@click.option("--instance", type=int, default=0, help="Instance index (default 0)")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--no-header", is_flag=True, help="Suppress TSV header row")
def vertex_cmd(
    eid: int,
    vtx_id: int,
    show_trace: bool,
    dump_at: int | None,
    instance: int,
    use_json: bool,
    no_header: bool,
) -> None:
    """Debug vertex shader for vertex VTX_ID at event EID."""
    params: dict[str, Any] = {"eid": eid, "vtx_id": vtx_id, "instance": instance}

    result = call("debug_vertex", params)
    _check_debug_result(result)

    if use_json:
        write_json(result)
        return

    if dump_at is not None:
        _print_dump_at(result, dump_at, no_header)
        return

    if show_trace:
        _print_trace(result, no_header)
        return

    _print_summary(result)
