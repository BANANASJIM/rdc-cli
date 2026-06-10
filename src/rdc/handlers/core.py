"""Core daemon handlers: ping, status, goto, count, shutdown, file_read."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    _error_response,
    _result_response,
    _set_frame_event,
)
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _handle_ping(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    return _result_response(request_id, {"ok": True}), True


def _handle_status(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    result: dict[str, Any] = {
        "capture": state.capture,
        "current_eid": state.current_eid,
        "api": state.api_name,
        "event_count": state.max_eid,
    }
    if state.is_remote:
        result["remote"] = state.remote_url
        result["remote_connected"] = state.remote is not None
    return _result_response(request_id, result), True


def _handle_goto(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    eid = int(params.get("eid", 0))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    return _result_response(request_id, {"current_eid": state.current_eid}), True


def _handle_count(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    what = params.get("what", "")
    pass_name = params.get("pass")
    if what == "resources":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import count_resources

        resources = state.adapter.get_resources()
        value = count_resources(resources)
        return _result_response(request_id, {"value": value}), True
    if what == "shaders":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.handlers._helpers import _build_shader_cache

        _build_shader_cache(state)
        return _result_response(request_id, {"value": len(state.shader_meta)}), True
    try:
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import count_from_actions

        actions = state.adapter.get_root_actions()
        value = count_from_actions(actions, what, pass_name=pass_name)
        return _result_response(request_id, {"value": value}), True
    except ValueError as exc:
        return _error_response(request_id, -32602, str(exc)), True


def _handle_shutdown(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    from rdc.daemon_server import cleanup_state  # noqa: PLC0415

    cleanup_state(state)
    return _result_response(request_id, {"ok": True}), False


def _handle_file_read(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.temp_dir is None:
        return _error_response(request_id, -32002, "no temp directory available"), True
    raw_path = params.get("path", "")
    if not isinstance(raw_path, str) or not raw_path:
        return _error_response(request_id, -32602, "missing or empty path"), True
    try:
        resolved = Path(raw_path).resolve()
        temp_root = state.temp_dir.resolve()
    except (OSError, TypeError, ValueError) as exc:
        return _error_response(request_id, -32602, f"invalid path: {exc}"), True
    if temp_root not in resolved.parents and resolved != temp_root:
        return _error_response(request_id, -32602, "path outside temp directory"), True
    if not resolved.is_file():
        return _error_response(request_id, -32602, f"file not found: {resolved}"), True
    size = resolved.stat().st_size
    return _result_response(
        request_id,
        {"size": size, "_binary_size": size, "_binary_path": str(resolved)},
    ), True


HANDLERS: dict[str, Handler] = {
    "ping": _handle_ping,
    "status": _handle_status,
    "goto": _handle_goto,
    "count": _handle_count,
    "shutdown": _handle_shutdown,
    "file_read": _handle_file_read,
}
