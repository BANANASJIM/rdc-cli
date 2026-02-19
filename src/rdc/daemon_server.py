from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from rdc.adapter import RenderDocAdapter


@dataclass
class DaemonState:
    capture: str
    current_eid: int
    token: str
    adapter: RenderDocAdapter | None = None
    cap: Any = None
    structured_file: Any = None
    api_name: str = ""
    event_count: int = 0
    _eid_cache: int = field(default=-1, repr=False)


def _detect_version(rd: Any) -> tuple[int, int]:
    """Detect RenderDoc version from module."""
    from rdc.adapter import parse_version_tuple

    try:
        return parse_version_tuple(rd.GetVersionString())
    except (AttributeError, TypeError):
        return (0, 0)


def _load_replay(state: DaemonState) -> str | None:
    """Load renderdoc module and open capture. Returns error string or None."""
    try:
        import renderdoc as rd  # noqa: F811
    except ImportError:
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
    version = _detect_version(rd)
    state.adapter = RenderDocAdapter(controller=controller, version=version)
    state.structured_file = cap.GetStructuredData()

    api_props = state.adapter.get_api_properties()
    state.api_name = str(getattr(api_props, "pipelineType", "Unknown"))

    root_actions = state.adapter.get_root_actions()
    state.event_count = _count_events(root_actions)

    return None


def _count_events(actions: list[Any]) -> int:
    """Count total events in action tree."""
    count = 0
    for a in actions:
        count += 1
        if a.children:
            count += _count_events(a.children)
    return count


def _set_frame_event(state: DaemonState, eid: int) -> str | None:
    """Set frame event with caching. Returns error string or None."""
    if eid < 0:
        return "eid must be >= 0"
    if state.event_count > 0 and eid > state.event_count:
        return f"eid {eid} out of range (max: {state.event_count})"
    if state.adapter is not None:
        if state._eid_cache != eid:
            state.adapter.set_frame_event(eid)
            state._eid_cache = eid
    state.current_eid = eid
    return None


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
                request = json.loads(line)
                response, running = _handle_request(request, state)
                conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
                last_activity = time.time()


def _recv_line(conn: socket.socket) -> str:
    chunks: list[bytes] = []
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    if not chunks:
        return ""
    return b"".join(chunks).split(b"\n", 1)[0].decode("utf-8")


def _handle_request(request: dict[str, Any], state: DaemonState) -> tuple[dict[str, Any], bool]:
    request_id = request.get("id", 0)
    params = request.get("params") or {}
    token = params.get("_token")
    if token != state.token:
        return _error_response(request_id, -32600, "invalid token"), True

    method = request.get("method")
    if method == "ping":
        return _result_response(request_id, {"ok": True}), True
    if method == "status":
        return _result_response(
            request_id,
            {
                "capture": state.capture,
                "current_eid": state.current_eid,
                "api": state.api_name,
                "event_count": state.event_count,
            },
        ), True
    if method == "goto":
        eid = int(params.get("eid", 0))
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err), True
        return _result_response(request_id, {"current_eid": state.current_eid}), True
    if method == "shutdown":
        if state.adapter is not None:
            state.adapter.shutdown()
        if state.cap is not None:
            state.cap.Shutdown()
        return _result_response(request_id, {"ok": True}), False

    return _error_response(request_id, -32601, "method not found"), True


def _result_response(request_id: int, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: int, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


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
