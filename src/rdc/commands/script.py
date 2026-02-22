"""rdc script command -- execute a Python script inside the daemon."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from rdc.commands._helpers import call


def _parse_args(raw: tuple[str, ...]) -> dict[str, str]:
    """Parse KEY=VALUE pairs into a dict.

    Raises:
        click.BadParameter: If any value is missing '='.
    """
    result: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise click.BadParameter(
                f"invalid format {item!r}, expected KEY=VALUE", param_hint="'--arg'"
            )
        k, v = item.split("=", 1)
        result[k] = v
    return result


@click.command("script")
@click.argument(
    "script_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--arg", "args", multiple=True, metavar="KEY=VALUE", help="Script argument.")
@click.option("--json", "output_json", is_flag=True, help="Raw JSON output.")
def script_cmd(script_file: Path, args: tuple[str, ...], output_json: bool) -> None:
    """Execute a Python script inside the daemon process.

    The script has access to the live ReplayController, renderdoc module,
    and all daemon state. Assign to `result` to return structured data.
    """
    args_dict = _parse_args(args)
    params: dict[str, Any] = {
        "path": str(script_file.resolve()),
        "args": args_dict,
    }

    result = call("script", params)

    if output_json:
        click.echo(json.dumps(result))
        return

    stdout_text = result.get("stdout", "")
    if stdout_text:
        click.echo(stdout_text, nl=False)

    stderr_text = result.get("stderr", "")
    if stderr_text:
        click.echo(stderr_text, err=True, nl=False)

    elapsed = result.get("elapsed_ms", 0)
    click.echo(f"# elapsed: {elapsed} ms", err=True)

    return_value = result.get("return_value")
    if return_value is not None:
        click.echo(f"# result: {return_value}", err=True)
