from __future__ import annotations

import argparse
import json
import secrets
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdc._transport import recv_line as _recv_line
from rdc.adapter import RenderDocAdapter
from rdc.handlers._helpers import (
    _build_shader_cache,
    _collect_pipe_states,
    _enum_name,
    _error_response,
    _max_eid,
    _result_response,
    _sanitize_size,
    _set_frame_event,
)
from rdc.handlers._helpers import (
    _get_flat_actions as _get_flat_actions,
)
from rdc.handlers.buffer import HANDLERS as _BUFFER_HANDLERS
from rdc.handlers.core import HANDLERS as _CORE_HANDLERS
from rdc.handlers.descriptor import HANDLERS as _DESCRIPTOR_HANDLERS
from rdc.handlers.pipe_state import HANDLERS as _PIPE_STATE_HANDLERS
from rdc.handlers.query import HANDLERS as _QUERY_HANDLERS
from rdc.handlers.shader import HANDLERS as _SHADER_HANDLERS
from rdc.handlers.texture import HANDLERS as _TEXTURE_HANDLERS
from rdc.handlers.vfs import HANDLERS as _VFS_HANDLERS

# re-export helpers for backward compat with test imports
__all__ = [
    "DaemonState",
    "_build_shader_cache",
    "_collect_pipe_states",
    "_enum_name",
    "_error_response",
    "_handle_request",
    "_load_replay",
    "_max_eid",
    "_result_response",
    "_sanitize_size",
    "_set_frame_event",
    "main",
    "run_server",
]

_DISPATCH: dict[str, Any] = {
    **_CORE_HANDLERS,
    **_QUERY_HANDLERS,
    **_SHADER_HANDLERS,
    **_TEXTURE_HANDLERS,
    **_BUFFER_HANDLERS,
    **_PIPE_STATE_HANDLERS,
    **_DESCRIPTOR_HANDLERS,
    **_VFS_HANDLERS,
}


@dataclass
class DaemonState:
    capture: str
    current_eid: int
    token: str
    adapter: RenderDocAdapter | None = None
    cap: Any = None
    structured_file: Any = None
    api_name: str = ""
    max_eid: int = 0
    vfs_tree: Any = field(default=None, repr=False)
    _eid_cache: int = field(default=-1, repr=False)
    temp_dir: Path | None = None
    tex_map: dict[int, Any] = field(default_factory=dict)
    buf_map: dict[int, Any] = field(default_factory=dict)
    res_names: dict[int, str] = field(default_factory=dict)
    res_types: dict[int, str] = field(default_factory=dict)
    res_rid_map: dict[int, Any] = field(default_factory=dict)
    rd: Any = None
    disasm_cache: dict[int, str] = field(default_factory=dict)
    shader_meta: dict[int, dict[str, Any]] = field(default_factory=dict)
    _shader_cache_built: bool = field(default=False, repr=False)


def _detect_version(rd: Any) -> tuple[int, int]:
    """Detect RenderDoc version from module."""
    from rdc.adapter import parse_version_tuple

    try:
        return parse_version_tuple(rd.GetVersionString())
    except (AttributeError, TypeError):
        return (0, 0)


def _load_replay(state: DaemonState) -> str | None:
    """Load renderdoc module and open capture. Returns error string or None."""
    from rdc.discover import find_renderdoc

    rd = find_renderdoc()
    if rd is None:
        return "failed to import renderdoc module"

    try:
        rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    except Exception as exc:  # noqa: BLE001
        return f"InitialiseReplay failed: {exc}"

    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(state.capture, "", None)
    if result != rd.ResultCode.Succeeded:
        cap.Shutdown()
        return f"OpenFile failed: {result}"

    if cap.LocalReplaySupport() != rd.ReplaySupport.Supported:
        cap.Shutdown()
        return "local replay not supported on this platform"

    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    if result != rd.ResultCode.Succeeded:
        cap.Shutdown()
        return f"OpenCapture failed: {result}"

    state.cap = cap
    state.rd = rd
    version = _detect_version(rd)
    state.adapter = RenderDocAdapter(controller=controller, version=version)
    state.structured_file = cap.GetStructuredData()

    api_props = state.adapter.get_api_properties()
    pt = getattr(api_props, "pipelineType", "Unknown")
    state.api_name = _enum_name(pt)

    root_actions = state.adapter.get_root_actions()
    state.max_eid = _max_eid(root_actions)

    from rdc.vfs.tree_cache import build_vfs_skeleton

    resources = state.adapter.get_resources()
    textures = state.adapter.get_textures()
    buffers = state.adapter.get_buffers()

    state.tex_map = {int(t.resourceId): t for t in textures}
    state.buf_map = {int(b.resourceId): b for b in buffers}
    state.res_names = {int(r.resourceId): r.name for r in resources}
    state.res_types = {
        int(r.resourceId): getattr(getattr(r, "type", None), "name", str(getattr(r, "type", "")))
        for r in resources
    }
    state.res_rid_map = {int(r.resourceId): r.resourceId for r in resources}

    state.vfs_tree = build_vfs_skeleton(
        root_actions, resources, textures, buffers, state.structured_file
    )

    import tempfile

    state.temp_dir = Path(tempfile.mkdtemp(prefix=f"rdc-{state.token[:8]}-"))

    return None


def _handle_request(request: dict[str, Any], state: DaemonState) -> tuple[dict[str, Any], bool]:
    request_id = request.get("id", 0)
    params = request.get("params") or {}
    token = params.get("_token")
    if token is None or not secrets.compare_digest(token, state.token):
        return _error_response(request_id, -32600, "invalid token"), True

    method = request.get("method", "")
    handler = _DISPATCH.get(method)
    if handler is None:
        return _error_response(request_id, -32601, "method not found"), True
    result: tuple[dict[str, Any], bool] = handler(request_id, params, state)
    return result


def run_server(  # pragma: no cover
    host: str,
    port: int,
    state: DaemonState,
    idle_timeout_s: int = 1800,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(32)
        server.settimeout(1.0)

        running = True
        last_activity = time.time()
        while running:
            if time.time() - last_activity > idle_timeout_s:
                break

            try:
                conn, _addr = server.accept()
            except TimeoutError:
                continue

            with conn:
                line = _recv_line(conn)
                if not line:
                    continue
                try:
                    request = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    error_resp = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "parse error"},
                        "id": None,
                    }
                    conn.sendall((json.dumps(error_resp) + "\n").encode("utf-8"))
                    continue
                try:
                    response, running = _handle_request(request, state)
                except Exception:  # noqa: BLE001
                    response = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32603, "message": "internal error"},
                        "id": request.get("id"),
                    }
                    running = True
                conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
                last_activity = time.time()


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--idle-timeout", type=int, default=1800)
    parser.add_argument("--no-replay", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    state = DaemonState(capture=args.capture, current_eid=0, token=args.token)

    if not args.no_replay:
        err = _load_replay(state)
        if err:
            sys.stderr.write(f"error: {err}\n")
            sys.exit(1)

    run_server(
        host=args.host,
        port=args.port,
        state=state,
        idle_timeout_s=args.idle_timeout,
    )


if __name__ == "__main__":
    main()
