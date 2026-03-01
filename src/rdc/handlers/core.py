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
    if state.replay_output is not None:
        try:
            state.replay_output.Shutdown()
        except Exception:  # noqa: BLE001
            pass
        state.replay_output = None
    if state.adapter is not None:
        controller = state.adapter.controller
        try:
            for rid_obj in state.shader_replacements.values():
                controller.RemoveReplacement(rid_obj)
            for rid_obj in state.built_shaders.values():
                controller.FreeTargetResource(rid_obj)
        except Exception:  # noqa: BLE001
            pass
        state.shader_replacements.clear()
        state.built_shaders.clear()
    if state.temp_dir is not None:
        import shutil

        shutil.rmtree(state.temp_dir, ignore_errors=True)
    if state.local_capture_is_temp and state.local_capture_path:
        import shutil
        from pathlib import Path

        shutil.rmtree(str(Path(state.local_capture_path).parent), ignore_errors=True)
        state.local_capture_is_temp = False
    if state.is_remote:
        if state._ping_stop is not None:
            state._ping_stop.set()
        if state._ping_thread is not None:
            state._ping_thread.join(timeout=5.0)
        if state.remote is not None and state.adapter is not None:
            try:
                state.remote.CloseCapture(state.adapter.controller)
            except Exception:  # noqa: BLE001
                pass
            try:
                state.remote.ShutdownConnection()
            except Exception:  # noqa: BLE001
                pass
    else:
        if state.adapter is not None:
            state.adapter.shutdown()
    if state.cap is not None:
        state.cap.Shutdown()
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


_handle_ping._no_replay = True  # type: ignore[attr-defined]
_handle_status._no_replay = True  # type: ignore[attr-defined]
_handle_goto._no_replay = True  # type: ignore[attr-defined]
_handle_shutdown._no_replay = True  # type: ignore[attr-defined]
_handle_count._no_replay = True  # type: ignore[attr-defined]
_handle_file_read._no_replay = True  # type: ignore[attr-defined]

HANDLERS: dict[str, Handler] = {
    "ping": _handle_ping,
    "status": _handle_status,
    "goto": _handle_goto,
    "count": _handle_count,
    "shutdown": _handle_shutdown,
    "file_read": _handle_file_read,
}
