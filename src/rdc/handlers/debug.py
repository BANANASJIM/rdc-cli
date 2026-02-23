"""Shader debug handlers: debug_pixel, debug_vertex, debug_thread."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    _STAGE_NAMES,
    _error_response,
    _get_flat_actions,
    _result_response,
    _set_frame_event,
)
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState

_log = logging.getLogger("rdc.handlers.debug")
_MAX_STEPS = 50_000


def _format_var_value(var: Any) -> list[float | int]:
    """Extract variable value as flat list from ShaderVariable."""
    rows = max(var.rows, 1)
    cols = max(var.columns, 1)
    count = rows * cols
    val = var.value
    if val is None:
        return [0.0] * count
    var_type = str(getattr(var, "type", "float")).lower()
    if "uint" in var_type or "u32" in var_type:
        return list(val.u32v[:count])
    if "int" in var_type or "s32" in var_type or "sint" in var_type:
        return list(val.s32v[:count])
    return list(val.f32v[:count])


def _format_var_type(var: Any) -> str:
    """Return a human-readable type string for a ShaderVariable."""
    t = str(getattr(var, "type", "float")).lower()
    if "uint" in t or "u32" in t:
        return "uint"
    if "int" in t or "s32" in t or "sint" in t:
        return "int"
    return "float"


def _format_step(state_obj: Any, trace: Any) -> dict[str, Any]:
    """Convert a ShaderDebugState into a step dict."""
    inst = state_obj.nextInstruction
    file_name = ""
    line_num = -1
    inst_info = getattr(trace, "instInfo", None)
    source_files = getattr(trace, "sourceFiles", None)
    if inst_info and inst < len(inst_info):
        info = inst_info[inst]
        li = info.lineInfo
        line_num = li.lineStart
        fi = li.fileIndex
        if source_files and 0 <= fi < len(source_files):
            file_name = source_files[fi].filename

    changes: list[dict[str, Any]] = []
    for ch in state_obj.changes:
        after = ch.after
        changes.append(
            {
                "name": after.name,
                "type": _format_var_type(after),
                "rows": max(after.rows, 1),
                "cols": max(after.columns, 1),
                "before": _format_var_value(ch.before),
                "after": _format_var_value(ch.after),
            }
        )

    return {
        "step": state_obj.stepIndex,
        "instruction": inst,
        "file": file_name,
        "line": line_num,
        "changes": changes,
    }


def _run_debug_loop(controller: Any, trace: Any) -> tuple[list[dict[str, Any]], str | None]:
    """Step through debug trace to completion, return (steps, error_msg)."""
    steps: list[dict[str, Any]] = []
    try:
        while True:
            try:
                states = controller.ContinueDebug(trace.debugger)
            except Exception as exc:
                _log.warning("ContinueDebug raised: %s", exc)
                return steps, f"debug loop error: {type(exc).__name__}: {exc}"
            if not states:
                break
            for s in states:
                try:
                    steps.append(_format_step(s, trace))
                except Exception as exc:
                    _log.warning("_format_step raised: %s", exc)
                    return steps, f"debug loop error: {type(exc).__name__}: {exc}"
                if len(steps) > _MAX_STEPS:
                    return steps, None
    finally:
        controller.FreeTrace(trace)
    return steps, None


def _extract_inputs_outputs(
    steps: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract input changes (step 0) and output changes (last step)."""
    inputs = steps[0]["changes"] if steps else []
    outputs = steps[-1]["changes"] if steps else []
    return inputs, outputs


def _handle_debug_pixel(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Handle debug_pixel JSON-RPC request."""
    assert state.adapter is not None
    for key in ("eid", "x", "y"):
        if key not in params:
            return _error_response(request_id, -32602, f"missing required param: {key}"), True

    eid = int(params["eid"])
    x = int(params["x"])
    y = int(params["y"])

    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True

    rd = state.rd
    inputs = rd.DebugPixelInputs()
    inputs.sample = int(params.get("sample", 0xFFFFFFFF))
    inputs.primitive = int(params.get("primitive", 0xFFFFFFFF))

    controller = state.adapter.controller
    try:
        trace = controller.DebugPixel(x, y, inputs)
    except Exception as exc:
        return _error_response(request_id, -32603, f"DebugPixel failed: {exc}"), True

    if trace is None or trace.debugger is None:
        return _error_response(request_id, -32007, "no fragment at pixel"), True

    stage_name = _STAGE_NAMES.get(int(trace.stage), "ps")
    steps, loop_err = _run_debug_loop(controller, trace)
    if loop_err:
        return _error_response(request_id, -32603, loop_err), True
    inp, out = _extract_inputs_outputs(steps)

    return _result_response(
        request_id,
        {
            "eid": eid,
            "stage": stage_name,
            "total_steps": len(steps),
            "inputs": inp,
            "outputs": out,
            "trace": steps,
        },
    ), True


def _handle_debug_vertex(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Handle debug_vertex JSON-RPC request."""
    assert state.adapter is not None
    for key in ("eid", "vtx_id"):
        if key not in params:
            return _error_response(request_id, -32602, f"missing required param: {key}"), True

    eid = int(params["eid"])
    vtx_id = int(params["vtx_id"])
    instance = int(params.get("instance", 0))
    idx = int(params.get("idx", 0))
    view = int(params.get("view", 0))

    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True

    controller = state.adapter.controller
    try:
        trace = controller.DebugVertex(vtx_id, instance, idx, view)
    except Exception as exc:
        return _error_response(request_id, -32603, f"DebugVertex failed: {exc}"), True

    if trace is None or trace.debugger is None:
        return _error_response(request_id, -32007, "vertex debug not available"), True

    stage_name = _STAGE_NAMES.get(int(trace.stage), "vs")
    steps, loop_err = _run_debug_loop(controller, trace)
    if loop_err:
        return _error_response(request_id, -32603, loop_err), True
    inp, out = _extract_inputs_outputs(steps)

    return _result_response(
        request_id,
        {
            "eid": eid,
            "stage": stage_name,
            "total_steps": len(steps),
            "inputs": inp,
            "outputs": out,
            "trace": steps,
        },
    ), True


def _handle_debug_thread(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Handle debug_thread JSON-RPC request."""
    assert state.adapter is not None
    for key in ("eid", "gx", "gy", "gz", "tx", "ty", "tz"):
        if key not in params:
            return _error_response(request_id, -32602, f"missing required param: {key}"), True

    eid = int(params["eid"])
    gx, gy, gz = int(params["gx"]), int(params["gy"]), int(params["gz"])
    tx, ty, tz = int(params["tx"]), int(params["ty"]), int(params["tz"])

    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True

    from rdc.services.query_service import _DISPATCH

    actions = _get_flat_actions(state)
    action = next((a for a in actions if a.eid == eid), None)
    if action is None or not (int(action.flags) & _DISPATCH):
        return _error_response(request_id, -32602, "event is not a Dispatch"), True

    controller = state.adapter.controller
    try:
        trace = controller.DebugThread((gx, gy, gz), (tx, ty, tz))
    except Exception as exc:
        return _error_response(request_id, -32603, f"DebugThread failed: {exc}"), True

    if trace is None or trace.debugger is None:
        return _error_response(request_id, -32007, "thread debug not available"), True

    stage_name = _STAGE_NAMES.get(int(trace.stage), "cs")
    steps, loop_err = _run_debug_loop(controller, trace)
    if loop_err:
        return _error_response(request_id, -32603, loop_err), True
    inp, out = _extract_inputs_outputs(steps)

    return _result_response(
        request_id,
        {
            "eid": eid,
            "stage": stage_name,
            "total_steps": len(steps),
            "inputs": inp,
            "outputs": out,
            "trace": steps,
        },
    ), True


HANDLERS: dict[str, Handler] = {
    "debug_pixel": _handle_debug_pixel,
    "debug_vertex": _handle_debug_vertex,
    "debug_thread": _handle_debug_thread,
}
