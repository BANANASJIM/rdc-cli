"""Core daemon handlers: ping, status, goto, count, shutdown."""

from __future__ import annotations

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
    return _result_response(
        request_id,
        {
            "capture": state.capture,
            "current_eid": state.current_eid,
            "api": state.api_name,
            "event_count": state.max_eid,
        },
    ), True


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
        for rid_obj in state.shader_replacements.values():
            controller.RemoveReplacement(rid_obj)
        for rid_obj in state.built_shaders.values():
            controller.FreeTargetResource(rid_obj)
        state.shader_replacements.clear()
        state.built_shaders.clear()
    if state.temp_dir is not None:
        import shutil

        shutil.rmtree(state.temp_dir, ignore_errors=True)
    if state.adapter is not None:
        state.adapter.shutdown()
    if state.cap is not None:
        state.cap.Shutdown()
    return _result_response(request_id, {"ok": True}), False


_handle_ping._no_replay = True  # type: ignore[attr-defined]
_handle_status._no_replay = True  # type: ignore[attr-defined]
_handle_goto._no_replay = True  # type: ignore[attr-defined]
_handle_shutdown._no_replay = True  # type: ignore[attr-defined]
_handle_count._no_replay = True  # type: ignore[attr-defined]

HANDLERS: dict[str, Handler] = {
    "ping": _handle_ping,
    "status": _handle_status,
    "goto": _handle_goto,
    "count": _handle_count,
    "shutdown": _handle_shutdown,
}
