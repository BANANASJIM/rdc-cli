from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import click


def _find_renderdoccmd() -> str | None:
    in_path = shutil.which("renderdoccmd")
    if in_path:
        return in_path

    common_paths = [
        Path("/opt/renderdoc/bin/renderdoccmd"),
        Path("/usr/local/bin/renderdoccmd"),
    ]
    for path in common_paths:
        if path.exists() and path.is_file():
            return str(path)
    return None


@click.command(
    "capture",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("--api", "api_name", type=str, help="Capture API (maps to --opt-api).")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output capture file path.")
@click.pass_context
def capture_cmd(ctx: click.Context, api_name: str | None, output: Path | None) -> None:
    """Thin wrapper around renderdoccmd capture."""
    bin_path = _find_renderdoccmd()
    if not bin_path:
        click.echo("error: renderdoccmd not found in PATH", err=True)
        raise SystemExit(1)

    argv: list[str] = [bin_path, "capture"]
    if api_name:
        argv.extend(["--opt-api", api_name])
    if output:
        argv.extend(["--capture-file", str(output)])
    argv.extend(ctx.args)

    result = subprocess.run(argv, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    if output:
        click.echo(f"capture saved: {output}", err=True)
        click.echo(f"next: rdc open {output}", err=True)
