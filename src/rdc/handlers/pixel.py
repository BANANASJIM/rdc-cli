"""Pixel handlers: pixel_history, pick_pixel."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    _error_response,
    _result_response,
    _set_frame_event,
)

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState

_FLAG_ATTRS = [
    "directShaderWrite",
    "unboundPS",
    "sampleMasked",
    "backfaceCulled",
    "depthClipped",
    "scissorClipped",
    "shaderDiscarded",
    "depthTestFailed",
    "stencilTestFailed",
    "depthBoundsFailed",
    "predicationSkipped",
    "viewClipped",
]


def _safe_depth(d: float) -> float | None:
    """Return None for sentinel / non-finite depth values."""
    if d == -1.0 or not math.isfinite(d):
        return None
    return d


def _rgba(col: Any) -> dict[str, float]:
    v = col.floatValue
    return {"r": v[0], "g": v[1], "b": v[2], "a": v[3]}


def _collect_flags(mod: Any) -> list[str]:
    return [name for name in _FLAG_ATTRS if getattr(mod, name, False)]


def _mod_to_dict(mod: Any) -> dict[str, Any]:
    return {
        "eid": mod.eventId,
        "fragment": mod.fragIndex,
        "primitive": mod.primitiveID,
        "shader_out": _rgba(mod.shaderOut.col),
        "post_mod": _rgba(mod.postMod.col),
        "depth": _safe_depth(mod.postMod.depth),
        "passed": mod.Passed(),
        "flags": _collect_flags(mod),
    }


def _handle_pixel_history(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Handle pixel_history JSON-RPC request.

    Args:
        request_id: JSON-RPC request id.
        params: Request parameters (x, y, eid, target, sample).
        state: Daemon state with adapter and tex_map.

    Returns:
        Tuple of (response dict, keep_running bool).
    """
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    for key in ("x", "y"):
        if key not in params:
            return _error_response(request_id, -32602, f"missing required param: {key}"), True

    x = int(params["x"])
    y = int(params["y"])
    eid = int(params.get("eid", state.current_eid))
    target_idx = int(params.get("target", 0))
    sample = int(params.get("sample", 0))

    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True

    pipe = state.adapter.get_pipeline_state()
    targets = pipe.GetOutputTargets()
    non_null = [(i, t) for i, t in enumerate(targets) if int(t.resource) != 0]

    if not non_null:
        return _error_response(request_id, -32001, f"no color targets at eid {eid}"), True

    match = [t for i, t in non_null if i == target_idx]
    if not match:
        return _error_response(request_id, -32001, f"target index {target_idx} out of range"), True

    rt_rid = match[0].resource
    tex = state.tex_map.get(int(rt_rid))
    if tex is not None and getattr(tex, "msSamp", 1) > 1:
        return _error_response(request_id, -32001, "MSAA pixel history not supported"), True

    rd = state.rd
    sub = rd.Subresource() if rd else type("Sub", (), {"sample": 0})()
    sub.sample = sample
    comp_type = rd.CompType.Typeless if rd else 0

    controller = state.adapter.controller
    mods = controller.PixelHistory(rt_rid, x, y, sub, comp_type)

    return _result_response(
        request_id,
        {
            "x": x,
            "y": y,
            "eid": eid,
            "target": {"index": target_idx, "id": int(rt_rid)},
            "modifications": [_mod_to_dict(m) for m in mods],
        },
    ), True


def _handle_pick_pixel(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Handle pick_pixel JSON-RPC request.

    Args:
        request_id: JSON-RPC request id.
        params: Request parameters (x, y, eid, target).
        state: Daemon state with adapter and tex_map.

    Returns:
        Tuple of (response dict, keep_running bool).
    """
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    for key in ("x", "y"):
        if key not in params:
            return _error_response(request_id, -32602, f"missing required param: {key}"), True

    x = int(params["x"])
    y = int(params["y"])
    eid = int(params.get("eid", state.current_eid))
    target_idx = int(params.get("target", 0))

    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True

    pipe = state.adapter.get_pipeline_state()
    targets = pipe.GetOutputTargets()
    non_null = [(i, t) for i, t in enumerate(targets) if int(t.resource) != 0]

    if not non_null:
        return _error_response(request_id, -32001, f"no color targets at eid {eid}"), True

    match = [t for i, t in non_null if i == target_idx]
    if not match:
        return _error_response(request_id, -32001, f"target index {target_idx} out of range"), True

    rt_rid = match[0].resource
    tex = state.tex_map.get(int(rt_rid))
    if tex is not None and getattr(tex, "msSamp", 1) > 1:
        return _error_response(request_id, -32001, "MSAA pick-pixel not supported"), True

    rd = state.rd
    sub = rd.Subresource() if rd else type("Sub", (), {"sample": 0})()
    sub.sample = 0
    comp_type = rd.CompType.Typeless if rd else 0

    controller = state.adapter.controller
    pv = controller.PickPixel(rt_rid, x, y, sub, comp_type)

    fv = pv.floatValue
    return _result_response(
        request_id,
        {
            "x": x,
            "y": y,
            "eid": eid,
            "target": {"index": target_idx, "id": int(rt_rid)},
            "color": {"r": fv[0], "g": fv[1], "b": fv[2], "a": fv[3]},
        },
    ), True


HANDLERS: dict[str, Any] = {
    "pixel_history": _handle_pixel_history,
    "pick_pixel": _handle_pick_pixel,
}
