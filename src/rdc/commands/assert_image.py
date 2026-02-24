"""rdc assert-image command -- pixel-level image comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from rdc.image_compare import CompareResult, compare_images


def _json_output(result: CompareResult, threshold: float) -> str:
    """Format CompareResult as JSON string."""
    return json.dumps(
        {
            "identical": result.identical,
            "diff_pixels": result.diff_pixels,
            "total_pixels": result.total_pixels,
            "diff_ratio": result.diff_ratio,
            "diff_image": str(result.diff_image) if result.diff_image else None,
            "threshold": threshold,
        }
    )


@click.command("assert-image")
@click.argument("expected", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("actual", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--threshold", default=0.0, type=float, help="Diff ratio threshold (%).")
@click.option(
    "--diff-output",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write diff visualization PNG.",
)
@click.option("--json", "use_json", is_flag=True, help="JSON output.")
def assert_image_cmd(
    expected: Path,
    actual: Path,
    threshold: float,
    diff_output: Path | None,
    use_json: bool,
) -> None:
    """Compare two images pixel-by-pixel.

    Exit 0 if images match (within threshold), exit 1 if they differ,
    exit 2 on error (size mismatch, invalid image).
    """
    try:
        result = compare_images(expected, actual, threshold=threshold, diff_output=diff_output)
    except (ValueError, OSError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    if use_json:
        click.echo(_json_output(result, threshold))
    elif result.identical:
        click.echo("match")
    else:
        click.echo(
            f"diff: {result.diff_pixels}/{result.total_pixels} pixels ({result.diff_ratio:.2f}%)"
        )

    sys.exit(0 if result.identical else 1)
