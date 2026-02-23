from __future__ import annotations

import argparse
import atexit
import json
import logging
import secrets
import shutil
import signal
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdc._transport import recv_line as _recv_line
from rdc.adapter import RenderDocAdapter
from rdc.handlers._helpers import (
    _build_shader_cache,
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
from rdc.handlers.capturefile import HANDLERS as _CAPTUREFILE_HANDLERS
from rdc.handlers.core import HANDLERS as _CORE_HANDLERS
from rdc.handlers.debug import HANDLERS as _DEBUG_HANDLERS
from rdc.handlers.descriptor import HANDLERS as _DESCRIPTOR_HANDLERS
from rdc.handlers.pipe_state import HANDLERS as _PIPE_STATE_HANDLERS
from rdc.handlers.pixel import HANDLERS as _PIXEL_HANDLERS
from rdc.handlers.query import HANDLERS as _QUERY_HANDLERS
from rdc.handlers.script import HANDLERS as _SCRIPT_HANDLERS
from rdc.handlers.shader import HANDLERS as _SHADER_HANDLERS
from rdc.handlers.shader_edit import HANDLERS as _SHADER_EDIT_HANDLERS
from rdc.handlers.texture import HANDLERS as _TEXTURE_HANDLERS
from rdc.handlers.vfs import HANDLERS as _VFS_HANDLERS

if TYPE_CHECKING:
    from rdc.vfs.tree_cache import VfsTree

from rdc.handlers._types import Handler

# re-export helpers for backward compat with test imports
__all__ = [
    "DaemonState",
    "Handler",
    "_build_shader_cache",
    "_cleanup_temp",
    "_enum_name",
    "_error_response",
    "_handle_request",
    "_load_replay",
    "_max_eid",
    "_process_request",
    "_result_response",
    "_sanitize_size",
    "_set_frame_event",
    "main",
    "run_server",
]

_DISPATCH: dict[str, Handler] = {
    **_CORE_HANDLERS,
    **_QUERY_HANDLERS,
    **_SHADER_HANDLERS,
    **_TEXTURE_HANDLERS,
    **_BUFFER_HANDLERS,
    **_PIPE_STATE_HANDLERS,
    **_DESCRIPTOR_HANDLERS,
    **_SCRIPT_HANDLERS,
    **_PIXEL_HANDLERS,
    **_VFS_HANDLERS,
    **_DEBUG_HANDLERS,
    **_SHADER_EDIT_HANDLERS,
    **_CAPTUREFILE_HANDLERS,
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
    vfs_tree: VfsTree | None = field(default=None, repr=False)
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
    _pipe_states_cache: dict[int, dict[int, int]] = field(default_factory=dict)
    built_shaders: dict[int, Any] = field(default_factory=dict)
    shader_replacements: dict[int, Any] = field(default_factory=dict)
    replay_output: Any = None
    replay_output_dims: tuple[int, int] | None = None
    _shader_cache_built: bool = field(default=False, repr=False)
    _debug_messages_cache: list[Any] | None = None


def _detect_version(rd: Any) -> tuple[int, int]:
    """Detect RenderDoc version from module."""
    from rdc.adapter import parse_version_tuple

    try:
        return parse_version_tuple(rd.GetVersionString())
    except (AttributeError, TypeError):
        return (0, 0)


def _cleanup_temp(state: DaemonState) -> None:
    """Remove the daemon's temp directory if it exists."""
    if state.temp_dir is not None:
        shutil.rmtree(state.temp_dir, ignore_errors=True)


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
    atexit.register(_cleanup_temp, state)

    return None


def _handle_request(request: dict[str, Any], state: DaemonState) -> tuple[dict[str, Any], bool]:
    request_id = request.get("id", 0)
    params = request.get("params") or {}
    token = params.get("_token")
    if (
        token is None
        or not isinstance(token, str)
        or not secrets.compare_digest(token, state.token)
    ):
        return _error_response(request_id, -32600, "invalid token"), True

    method = request.get("method", "")
    handler = _DISPATCH.get(method)
    if handler is None:
        return _error_response(request_id, -32601, "method not found"), True
    if not getattr(handler, "_no_replay", False) and state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    result: tuple[dict[str, Any], bool] = handler(request_id, params, state)
    return result


_log = logging.getLogger("rdc.daemon")


def _process_request(request: dict[str, Any], state: DaemonState) -> tuple[dict[str, Any], bool]:
    """Dispatch a parsed JSON-RPC request, catching and logging handler exceptions."""
    try:
        return _handle_request(request, state)
    except Exception:  # noqa: BLE001
        _log.exception("unhandled exception in handler: %s", request.get("method", ""))
        response: dict[str, Any] = {
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": "internal error"},
            "id": request.get("id"),
        }
        running = request.get("method") != "shutdown"
        return response, running


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
            if idle_timeout_s > 0 and time.time() - last_activity > idle_timeout_s:
                break

            try:
                conn, _addr = server.accept()
            except TimeoutError:
                continue

            with conn:
                try:
                    line = _recv_line(conn)
                except ValueError:
                    continue
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
                    try:
                        conn.sendall((json.dumps(error_resp) + "\n").encode("utf-8"))
                    except OSError:
                        pass
                    continue
                response, running = _process_request(request, state)
                try:
                    conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
                except OSError:
                    pass
                last_activity = time.time()


def main() -> None:  # pragma: no cover
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

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
