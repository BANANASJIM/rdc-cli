"""CaptureFile CLI commands: thumbnail, gpus, sections, section, callstacks."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import click

from rdc.commands._helpers import call


@click.command("thumbnail")
@click.option("--maxsize", type=int, default=0, help="Max thumbnail dimension.")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Write image to file.")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def thumbnail_cmd(maxsize: int, output: Path | None, use_json: bool) -> None:
    """Export capture thumbnail."""
    result = call("capture_thumbnail", {"maxsize": maxsize})
    if output:
        output.write_bytes(base64.b64decode(result["data"]))
        click.echo(f"thumbnail saved: {output}", file=sys.stderr)
    elif use_json:
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
@click.option(
    "--write",
    "write_file",
    type=click.Path(path_type=Path),
    default=None,
    help="Write file contents as this section (use '-' for stdin).",
)
def section_cmd(name: str, use_json: bool, write_file: Path | None) -> None:
    """Extract or write named section contents."""
    if write_file is not None:
        if str(write_file) == "-":
            data = click.get_binary_stream("stdin").read()
        else:
            try:
                data = write_file.read_bytes()
            except OSError as exc:
                click.echo(f"error: {exc}", err=True)
                raise SystemExit(1) from exc
        encoded = base64.b64encode(data).decode()
        result = call("section_write", {"name": name, "data": encoded})
        click.echo(f"section '{name}' written ({result['bytes']} bytes)", err=True)
        if use_json:
            click.echo(json.dumps(result))
        return
    result = call("capture_section_content", {"name": name})
    if use_json:
        click.echo(json.dumps(result))
    else:
        click.echo(result["contents"])


@click.command("callstacks")
@click.option("--eid", type=int, default=None, help="Event ID (defaults to current).")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def callstacks_cmd(eid: int | None, use_json: bool) -> None:
    """Resolve CPU callstack for an event."""
    params: dict[str, int] = {}
    if eid is not None:
        params["eid"] = eid
    result = call("callstack_resolve", params, timeout=60.0)
    frames = result.get("frames", [])
    if use_json:
        click.echo(json.dumps(result))
    elif not frames:
        click.echo(f"no frames at eid {result.get('eid', '?')}")
    else:
        click.echo("function\tfile\tline")
        for f in frames:
            click.echo(f"{f['function']}\t{f['file']}\t{f['line']}")
