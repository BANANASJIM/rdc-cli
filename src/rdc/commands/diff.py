"""rdc diff command -- dual-daemon capture comparison."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from rdc.services.diff_service import start_diff_session, stop_diff_session

_MODE_STUBS = {"draws", "resources", "passes", "stats", "framebuffer", "pipeline"}


@click.command("diff")
@click.argument("capture_a", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("capture_b", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--draws", "mode", flag_value="draws")
@click.option("--resources", "mode", flag_value="resources")
@click.option("--passes", "mode", flag_value="passes")
@click.option("--stats", "mode", flag_value="stats")
@click.option("--framebuffer", "mode", flag_value="framebuffer")
@click.option("--pipeline", "pipeline_marker", default=None, metavar="MARKER")
@click.option("--json", "output_json", is_flag=True)
@click.option("--format", "fmt", type=click.Choice(["tsv", "unified", "json"]), default="tsv")
@click.option("--shortstat", is_flag=True)
@click.option("--no-header", is_flag=True)
@click.option("--timeout", default=60.0, type=float)
def diff_cmd(
    capture_a: Path,
    capture_b: Path,
    mode: str | None,
    pipeline_marker: str | None,
    output_json: bool,
    fmt: str,
    shortstat: bool,
    no_header: bool,
    timeout: float,
) -> None:
    """Compare two RenderDoc captures side-by-side."""
    if pipeline_marker is not None:
        mode = "pipeline"
    if mode is None:
        mode = "summary"

    ctx, err = start_diff_session(str(capture_a), str(capture_b), timeout_s=timeout)
    if ctx is None:
        click.echo(f"error: {err}", err=True)
        sys.exit(2)

    try:
        if mode in _MODE_STUBS:
            click.echo(f"error: --{mode} not yet implemented", err=True)
            sys.exit(2)

        # summary stub: exit 0
    finally:
        stop_diff_session(ctx)
