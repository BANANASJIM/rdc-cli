"""TargetControl commands: attach, capture-trigger, capture-list, capture-copy.

These commands bypass the daemon and call CreateTargetControl directly.
"""

from __future__ import annotations

import time
from typing import Any

import click

from rdc.discover import find_renderdoc
from rdc.target_state import (
    TargetControlState,
    load_latest_target_state,
    save_target_state,
)


def _require_renderdoc() -> Any:
    """Find and return the renderdoc module, or exit with error."""
    rd = find_renderdoc()
    if rd is None:
        click.echo("error: renderdoc module not found", err=True)
        raise SystemExit(1)
    return rd


def _resolve_ident(ident: int | None) -> int:
    """Resolve ident from option or saved state."""
    if ident is not None:
        return ident
    state = load_latest_target_state()
    if state is None:
        click.echo("error: no active target (run 'rdc attach' first)", err=True)
        raise SystemExit(1)
    return state.ident


def _connect(rd: Any, host: str, ident: int) -> Any:
    """Create a TargetControl connection, exit on failure."""
    tc = rd.CreateTargetControl(host, ident, "rdc-cli", True)
    if tc is None:
        click.echo(f"error: failed to connect to target ident={ident}", err=True)
        raise SystemExit(1)
    if not tc.Connected():
        tc.Shutdown()
        click.echo(f"error: failed to connect to target ident={ident}", err=True)
        raise SystemExit(1)
    return tc


@click.command("attach")
@click.argument("ident", type=int)
@click.option("--host", default="localhost", help="Target host.")
def attach_cmd(ident: int, host: str) -> None:
    """Attach to a running RenderDoc target by ident."""
    rd = _require_renderdoc()
    tc = _connect(rd, host, ident)
    try:
        target = tc.GetTarget()
        pid = tc.GetPID()
        api = tc.GetAPI()
        save_target_state(
            TargetControlState(
                ident=ident,
                target_name=target,
                pid=pid,
                api=api,
                connected_at=time.time(),
            )
        )
        click.echo(f"attached: ident={ident} target={target} pid={pid} api={api}")
    finally:
        tc.Shutdown()


@click.command("capture-trigger")
@click.option("--ident", type=int, default=None, help="Target ident (default: most recent).")
@click.option("--host", default="localhost", help="Target host.")
@click.option("--num-frames", type=int, default=1, help="Number of frames to capture.")
def capture_trigger_cmd(ident: int | None, host: str, num_frames: int) -> None:
    """Trigger a capture on the attached target."""
    resolved = _resolve_ident(ident)
    rd = _require_renderdoc()
    tc = _connect(rd, host, resolved)
    try:
        tc.TriggerCapture(num_frames)
        click.echo(f"triggered: ident={resolved} frames={num_frames}")
    finally:
        tc.Shutdown()


@click.command("capture-list")
@click.option("--ident", type=int, default=None, help="Target ident (default: most recent).")
@click.option("--host", default="localhost", help="Target host.")
@click.option("--timeout", type=float, default=5.0, help="Timeout in seconds.")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
def capture_list_cmd(ident: int | None, host: str, timeout: float, use_json: bool) -> None:
    """List captures from the attached target."""
    import json as json_mod

    resolved = _resolve_ident(ident)
    rd = _require_renderdoc()
    tc = _connect(rd, host, resolved)
    captures: list[dict[str, Any]] = []
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not tc.Connected():
                break
            msg = tc.ReceiveMessage(None)
            msg_type = int(msg.type)
            if msg_type == 4 and msg.newCapture is not None:
                nc = msg.newCapture
                captures.append(
                    {
                        "captureId": nc.captureId,
                        "path": nc.path,
                        "frameNumber": nc.frameNumber,
                        "byteSize": nc.byteSize,
                        "api": nc.api,
                    }
                )
            elif msg_type == 1:
                break
            time.sleep(0.01)
    finally:
        tc.Shutdown()

    if use_json:
        click.echo(json_mod.dumps({"captures": captures}))
    else:
        if not captures:
            click.echo("no captures received")
        for c in captures:
            click.echo(
                f"[{c['captureId']}] {c['path']}  frame={c['frameNumber']}  "
                f"size={c['byteSize']}  api={c['api']}"
            )


@click.command("capture-copy")
@click.argument("capture_id", type=int)
@click.argument("dest", type=str)
@click.option("--ident", type=int, default=None, help="Target ident (default: most recent).")
@click.option("--host", default="localhost", help="Target host.")
@click.option("--timeout", type=float, default=30.0, help="Timeout in seconds.")
def capture_copy_cmd(
    capture_id: int, dest: str, ident: int | None, host: str, timeout: float
) -> None:
    """Copy a capture from the target to a local path."""
    resolved = _resolve_ident(ident)
    rd = _require_renderdoc()
    tc = _connect(rd, host, resolved)
    try:
        tc.CopyCapture(capture_id, dest)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not tc.Connected():
                click.echo("error: disconnected while waiting for copy", err=True)
                raise SystemExit(1)
            msg = tc.ReceiveMessage(None)
            msg_type = int(msg.type)
            if msg_type == 5:  # CaptureCopied
                click.echo(f"copied: capture {capture_id} -> {dest}")
                return
            if msg_type == 1:  # Disconnected
                click.echo("error: disconnected while waiting for copy", err=True)
                raise SystemExit(1)
            time.sleep(0.01)
        click.echo("error: timeout waiting for capture copy", err=True)
        raise SystemExit(1)
    finally:
        tc.Shutdown()
