"""rdc snapshot -- export a complete draw event state bundle."""

from __future__ import annotations

import datetime
import json
import shutil
from pathlib import Path
from typing import Any

import click

from rdc.commands._helpers import call, require_session
from rdc.daemon_client import send_request
from rdc.formatters.json_fmt import write_json
from rdc.protocol import _request


def _try_call(method: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Call daemon method silently, returning None on failure."""
    try:
        host, port, token = require_session()
    except SystemExit:
        return None
    payload = _request(method, 1, {"_token": token, **params}).to_dict()
    try:
        resp = send_request(host, port, payload)
    except OSError:
        return None
    if "error" in resp:
        return None
    result: dict[str, Any] = resp.get("result", {})
    return result


@click.command("snapshot")
@click.argument("eid", type=int)
@click.option("-o", "--output", required=True, type=click.Path(), help="Output directory")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def snapshot_cmd(eid: int, output: str, use_json: bool) -> None:
    """Export a complete rendering state snapshot for a draw event."""
    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    files: list[str] = []

    # Pipeline (fatal on failure)
    pipeline_data = call("pipeline", {"eid": eid})
    pipe_path = out_dir / "pipeline.json"
    pipe_path.write_text(json.dumps(pipeline_data, indent=2) + "\n")
    files.append("pipeline.json")

    # Shaders
    shader_resp = _try_call("shader_all", {"eid": eid})
    if shader_resp:
        for s in shader_resp.get("stages", []):
            stage = s["stage"]
            disasm_resp = _try_call("shader_disasm", {"eid": eid, "stage": stage})
            if disasm_resp:
                (out_dir / f"shader_{stage}.txt").write_text(disasm_resp["disasm"])
                files.append(f"shader_{stage}.txt")

    # Color targets (stop on first failure)
    for i in range(8):
        result = _try_call("rt_export", {"eid": eid, "target": i})
        if result is None:
            break
        shutil.copy2(result["path"], out_dir / f"color{i}.png")
        files.append(f"color{i}.png")

    # Depth target
    depth_result = _try_call("rt_depth", {"eid": eid})
    if depth_result:
        shutil.copy2(depth_result["path"], out_dir / "depth.png")
        files.append("depth.png")

    # Manifest
    manifest = {
        "eid": eid,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "files": files,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    if use_json:
        write_json(manifest)
    else:
        click.echo(f"snapshot: eid {eid} -> {out_dir} ({len(files)} files)")
        for f in files:
            click.echo(f"  {f}")
