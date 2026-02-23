"""CaptureFile CLI commands: thumbnail, gpus, sections, section."""

from __future__ import annotations

import json

import click

from rdc.commands._helpers import call


@click.command("thumbnail")
@click.option("--maxsize", type=int, default=0, help="Max thumbnail dimension.")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def thumbnail_cmd(maxsize: int, use_json: bool) -> None:
    """Export capture thumbnail."""
    result = call("capture_thumbnail", {"maxsize": maxsize})
    if use_json:
        click.echo(json.dumps(result))
    else:
        click.echo(f"thumbnail: {result['width']}x{result['height']}")


@click.command("gpus")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def gpus_cmd(use_json: bool) -> None:
    """List GPUs available at capture time."""
    result = call("capture_gpus", {})
    if use_json:
        click.echo(json.dumps(result))
    else:
        for gpu in result["gpus"]:
            click.echo(f"{gpu['name']}  (vendor={gpu['vendor']}  driver={gpu['driver']})")
        if not result["gpus"]:
            click.echo("no GPUs found")


@click.command("sections")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def sections_cmd(use_json: bool) -> None:
    """List all embedded sections."""
    result = call("capture_sections", {})
    if use_json:
        click.echo(json.dumps(result))
    else:
        for s in result["sections"]:
            click.echo(
                f"[{s['index']}] {s['name']}  (type={s['type']}, {s['uncompressedSize']} bytes)"
            )
        if not result["sections"]:
            click.echo("no sections")


@click.command("section")
@click.argument("name")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def section_cmd(name: str, use_json: bool) -> None:
    """Extract named section contents."""
    result = call("capture_section_content", {"name": name})
    if use_json:
        click.echo(json.dumps(result))
    else:
        click.echo(result["contents"])
