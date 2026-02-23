"""rdc pick-pixel command -- single-pixel color readback."""

from __future__ import annotations

from typing import Any

import click

from rdc.commands.info import _daemon_call
from rdc.formatters.json_fmt import write_json


@click.command("pick-pixel")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.argument("eid", required=False, type=int)
@click.option("--target", default=0, type=int, help="Color target index (default 0)")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def pick_pixel_cmd(x: int, y: int, eid: int | None, target: int, use_json: bool) -> None:
    """Read pixel color at (X, Y) from the current render target."""
    params: dict[str, Any] = {"x": x, "y": y, "target": target}
    if eid is not None:
        params["eid"] = eid
    result = _daemon_call("pick_pixel", params)
    if use_json:
        write_json(result)
        return
    c = result["color"]
    click.echo(f"r={c['r']:.4f}  g={c['g']:.4f}  b={c['b']:.4f}  a={c['a']:.4f}")
