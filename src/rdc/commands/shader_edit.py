"""rdc shader edit-replay commands -- build, replace, restore shaders."""

from __future__ import annotations

from pathlib import Path

import click

from rdc.commands._helpers import call, complete_eid
from rdc.formatters.json_fmt import write_json


@click.command("shader-encodings")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def shader_encodings_cmd(use_json: bool) -> None:
    """List available shader encodings for this capture."""
    result = call("shader_encodings", {})
    if use_json:
        write_json(result)
        return
    for enc in result["encodings"]:
        click.echo(enc["name"])


@click.command("shader-build")
@click.argument("source_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--stage",
    required=True,
    type=click.Choice(["vs", "hs", "ds", "gs", "ps", "cs"]),
    help="Shader stage",
)
@click.option("--entry", default="main", help="Entry point name")
@click.option("--encoding", default="GLSL", help="Encoding name (default: GLSL)")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("-q", "--quiet", is_flag=True, help="Print only shader_id")
def shader_build_cmd(
    source_file: Path, stage: str, entry: str, encoding: str, use_json: bool, quiet: bool
) -> None:
    """Build a shader from source file."""
    source = source_file.read_text("utf-8")
    result = call(
        "shader_build", {"stage": stage, "entry": entry, "encoding": encoding, "source": source}
    )
    if use_json:
        write_json(result)
        return
    if quiet:
        click.echo(result["shader_id"])
        return
    click.echo(f"shader_id\t{result['shader_id']}")
    if result.get("warnings"):
        click.echo(f"warnings\t{result['warnings']}", err=True)


@click.command("shader-replace")
@click.argument("eid", type=int, shell_complete=complete_eid)
@click.argument("stage", type=click.Choice(["vs", "hs", "ds", "gs", "ps", "cs"]))
@click.option(
    "--with", "shader_id", required=True, type=int, help="Built shader ID from shader-build"
)
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def shader_replace_cmd(eid: int, stage: str, shader_id: int, use_json: bool) -> None:
    """Replace shader at EID/STAGE with a built shader."""
    result = call("shader_replace", {"eid": eid, "stage": stage, "shader_id": shader_id})
    if use_json:
        write_json(result)
        return
    click.echo(f"replaced\t{result['original_id']}")
    click.echo("warning: replacement affects all draws using this shader", err=True)


@click.command("shader-restore")
@click.argument("eid", type=int, shell_complete=complete_eid)
@click.argument("stage", type=click.Choice(["vs", "hs", "ds", "gs", "ps", "cs"]))
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def shader_restore_cmd(eid: int, stage: str, use_json: bool) -> None:
    """Restore original shader at EID/STAGE."""
    result = call("shader_restore", {"eid": eid, "stage": stage})
    if use_json:
        write_json(result)
        return
    click.echo(f"restored\t{stage}")


@click.command("shader-restore-all")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def shader_restore_all_cmd(use_json: bool) -> None:
    """Restore all replaced shaders and free built resources."""
    result = call("shader_restore_all", {})
    if use_json:
        write_json(result)
        return
    click.echo(f"restored\t{result['restored']}")
    click.echo(f"freed\t{result['freed']}")
