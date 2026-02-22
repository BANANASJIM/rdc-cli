"""rdc diff command -- dual-daemon capture comparison."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from rdc.diff.framebuffer import FramebufferDiffResult, compare_framebuffers
from rdc.services.diff_service import start_diff_session, stop_diff_session

_MODE_STUBS = {"draws", "resources", "passes", "stats", "pipeline"}


def _render_framebuffer(
    result: FramebufferDiffResult,
    *,
    output_json: bool,
    threshold: float,
) -> None:
    """Render framebuffer diff result to stdout."""
    if output_json:
        data = asdict(result)
        data["diff_image"] = str(result.diff_image) if result.diff_image else None
        data["threshold"] = threshold
        click.echo(json.dumps(data, indent=2))
        return

    if result.identical:
        click.echo("identical")
    else:
        click.echo(
            f"diff: {result.diff_pixels}/{result.total_pixels} pixels ({result.diff_ratio:.2f}%)"
        )
    click.echo(f"  eid={result.eid} target={result.target}")
    if result.diff_image is not None:
        click.echo(f"  diff image: {result.diff_image}")


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
@click.option("--target", default=0, type=int, help="Color target index (default 0)")
@click.option(
    "--threshold",
    default=0.0,
    type=float,
    help="Max diff ratio %% to count as identical",
)
@click.option("--eid", default=None, type=int, help="Compare at specific EID (default: last draw)")
@click.option(
    "--diff-output",
    default=None,
    type=click.Path(path_type=Path),
    help="Write diff PNG here",
)
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
    target: int,
    threshold: float,
    eid: int | None,
    diff_output: Path | None,
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
        if mode == "framebuffer":
            result, fb_err = compare_framebuffers(
                ctx,
                target=target,
                threshold=threshold,
                eid=eid,
                diff_output=diff_output,
                timeout_s=timeout,
            )
            if result is None:
                click.echo(f"error: {fb_err}", err=True)
                sys.exit(2)
            _render_framebuffer(result, output_json=output_json, threshold=threshold)
            sys.exit(0 if result.identical else 1)

        if mode in _MODE_STUBS:
            click.echo(f"error: --{mode} not yet implemented", err=True)
            sys.exit(2)

        # summary stub: exit 0
    finally:
        stop_diff_session(ctx)
