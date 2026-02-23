"""Texture handlers: tex_info, tex_export, tex_raw, rt_export, rt_depth, rt_overlay, tex_stats."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    _error_response,
    _make_subresource,
    _make_texsave,
    _result_response,
    _set_frame_event,
)
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState

_OVERLAY_MAP: dict[str, int] = {
    "wireframe": 2,
    "depth": 3,
    "stencil": 4,
    "backface": 5,
    "viewport": 6,
    "nan": 7,
    "clipping": 8,
    "overdraw": 12,
    "triangle-size": 14,
}


def _handle_tex_info(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    res_id = int(params.get("id", 0))
    tex = state.tex_map.get(res_id)
    if tex is None:
        return _error_response(request_id, -32001, f"texture {res_id} not found"), True
    fmt = getattr(tex, "format", None)
    fmt_name = fmt.Name() if fmt and hasattr(fmt, "Name") else getattr(fmt, "name", "")
    return _result_response(
        request_id,
        {
            "id": res_id,
            "name": state.res_names.get(res_id, ""),
            "type": str(getattr(tex, "type", "")),
            "dimension": getattr(tex, "dimension", 0),
            "width": tex.width,
            "height": tex.height,
            "depth": getattr(tex, "depth", 1),
            "mips": tex.mips,
            "array_size": getattr(tex, "arraysize", 1),
            "format": fmt_name,
            "byte_size": getattr(tex, "byteSize", 0),
            "creation_flags": int(getattr(tex, "creationFlags", 0)),
            "cubemap": getattr(tex, "cubemap", False),
            "ms_samp": getattr(tex, "msSamp", 1),
        },
    ), True


def _handle_tex_export(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    if state.rd is None:
        return _error_response(request_id, -32002, "renderdoc module not available"), True
    if state.temp_dir is None:
        return _error_response(request_id, -32002, "temp directory not available"), True
    res_id = int(params.get("id", 0))
    mip = int(params.get("mip", 0))
    tex = state.tex_map.get(res_id)
    if tex is None:
        return _error_response(request_id, -32001, f"texture {res_id} not found"), True
    if mip < 0 or mip >= tex.mips:
        return _error_response(
            request_id, -32001, f"mip {mip} out of range (max: {tex.mips - 1})"
        ), True
    temp_path = state.temp_dir / f"tex_{res_id}_mip{mip}.png"
    controller = state.adapter.controller
    texsave = _make_texsave(state.rd, tex.resourceId, mip)
    success = controller.SaveTexture(texsave, str(temp_path))
    if not success or not temp_path.exists():
        return _error_response(request_id, -32002, "SaveTexture failed"), True
    return _result_response(
        request_id,
        {"path": str(temp_path), "size": temp_path.stat().st_size},
    ), True


def _handle_tex_raw(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    if state.rd is None:
        return _error_response(request_id, -32002, "renderdoc module not available"), True
    if state.temp_dir is None:
        return _error_response(request_id, -32002, "temp directory not available"), True
    res_id = int(params.get("id", 0))
    tex = state.tex_map.get(res_id)
    if tex is None:
        return _error_response(request_id, -32001, f"texture {res_id} not found"), True
    controller = state.adapter.controller
    sub = _make_subresource(state.rd)
    raw_data = controller.GetTextureData(tex.resourceId, sub)
    temp_path = state.temp_dir / f"tex_{res_id}.raw"
    temp_path.write_bytes(raw_data)
    return _result_response(
        request_id,
        {"path": str(temp_path), "size": len(raw_data)},
    ), True


def _handle_rt_export(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    if state.rd is None:
        return _error_response(request_id, -32002, "renderdoc module not available"), True
    if state.temp_dir is None:
        return _error_response(request_id, -32002, "temp directory not available"), True
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
    temp_path = state.temp_dir / f"rt_{eid}_color{target_idx}.png"
    texsave = _make_texsave(state.rd, match[0].resource)
    success = state.adapter.controller.SaveTexture(texsave, str(temp_path))
    if not success or not temp_path.exists():
        return _error_response(request_id, -32002, "SaveTexture failed"), True
    return _result_response(
        request_id,
        {"path": str(temp_path), "size": temp_path.stat().st_size},
    ), True


def _handle_rt_depth(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    if state.rd is None:
        return _error_response(request_id, -32002, "renderdoc module not available"), True
    if state.temp_dir is None:
        return _error_response(request_id, -32002, "temp directory not available"), True
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe = state.adapter.get_pipeline_state()
    depth = pipe.GetDepthTarget()
    if int(depth.resource) == 0:
        return _error_response(request_id, -32001, f"no depth target at eid {eid}"), True
    temp_path = state.temp_dir / f"rt_{eid}_depth.png"
    texsave = _make_texsave(state.rd, depth.resource)
    success = state.adapter.controller.SaveTexture(texsave, str(temp_path))
    if not success or not temp_path.exists():
        return _error_response(request_id, -32002, "SaveTexture failed"), True
    return _result_response(
        request_id,
        {"path": str(temp_path), "size": temp_path.stat().st_size},
    ), True


def _handle_rt_overlay(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Render a debug overlay on the color target and save as PNG."""
    assert state.adapter is not None
    if state.rd is None:
        return _error_response(request_id, -32002, "renderdoc module not available"), True
    if state.temp_dir is None:
        return _error_response(request_id, -32002, "temp directory not available"), True
    overlay_name = params.get("overlay", "")
    if overlay_name not in _OVERLAY_MAP:
        valid = ", ".join(sorted(_OVERLAY_MAP))
        return _error_response(
            request_id, -32602, f"unknown overlay '{overlay_name}'; valid: {valid}"
        ), True
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe = state.adapter.get_pipeline_state()
    targets = pipe.GetOutputTargets()
    non_null = [t for t in targets if int(t.resource) != 0]
    if not non_null:
        return _error_response(request_id, -32001, f"no color targets at eid {eid}"), True
    target_rid = non_null[0].resource
    width = int(params.get("width", 256))
    height = int(params.get("height", 256))
    if state.replay_output is not None and state.replay_output_dims != (width, height):
        state.replay_output.Shutdown()
        state.replay_output = None
        state.replay_output_dims = None
    if state.replay_output is None:
        windowing = state.rd.CreateHeadlessWindowingData(width, height)
        state.replay_output = state.adapter.controller.CreateOutput(
            windowing, state.rd.ReplayOutputType.Texture
        )
        state.replay_output_dims = (width, height)
    display = state.rd.TextureDisplay()
    display.resourceId = target_rid
    display.overlay = state.rd.DebugOverlay(_OVERLAY_MAP[overlay_name])
    state.replay_output.SetTextureDisplay(display)
    state.replay_output.Display()
    overlay_tex_id = state.replay_output.GetDebugOverlayTexID()
    if int(overlay_tex_id) == 0:
        return _error_response(request_id, -32002, "overlay texture ID is zero"), True
    temp_path = Path(state.temp_dir) / f"overlay_{overlay_name}_{eid}.png"
    texsave = _make_texsave(state.rd, overlay_tex_id)
    success = state.adapter.controller.SaveTexture(texsave, str(temp_path))
    if not success or not temp_path.exists():
        return _error_response(request_id, -32002, "SaveTexture failed"), True
    return _result_response(
        request_id,
        {
            "path": str(temp_path),
            "size": temp_path.stat().st_size,
            "overlay": overlay_name,
            "eid": eid,
        },
    ), True


def _handle_tex_stats(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    if state.rd is None:
        return _error_response(request_id, -32002, "renderdoc module not available"), True

    res_id = int(params.get("id", 0))
    tex = state.tex_map.get(res_id)
    if tex is None:
        return _error_response(request_id, -32001, f"texture {res_id} not found"), True

    if getattr(tex, "msSamp", 1) > 1:
        return _error_response(
            request_id, -32001, "MSAA textures not supported for tex-stats"
        ), True

    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True

    rd = state.rd
    mip = int(params.get("mip", 0))
    array_slice = int(params.get("slice", 0))

    if mip < 0 or mip >= tex.mips:
        return _error_response(
            request_id, -32001, f"mip {mip} out of range (max: {tex.mips - 1})"
        ), True
    if array_slice < 0 or array_slice >= tex.arraysize:
        return _error_response(
            request_id, -32001, f"slice {array_slice} out of range (max: {tex.arraysize - 1})"
        ), True

    sub = rd.Subresource()
    sub.mip = mip
    sub.slice = array_slice
    sub.sample = 0
    comp_type = rd.CompType.Typeless

    controller = state.adapter.controller
    min_val, max_val = controller.GetMinMax(tex.resourceId, sub, comp_type)

    result_data: dict[str, Any] = {
        "id": res_id,
        "eid": eid,
        "mip": mip,
        "slice": array_slice,
        "min": {
            "r": min_val.floatValue[0],
            "g": min_val.floatValue[1],
            "b": min_val.floatValue[2],
            "a": min_val.floatValue[3],
        },
        "max": {
            "r": max_val.floatValue[0],
            "g": max_val.floatValue[1],
            "b": max_val.floatValue[2],
            "a": max_val.floatValue[3],
        },
    }

    if params.get("histogram"):
        histogram: list[dict[str, Any]] = []
        for ch in range(4):
            channels = [ch == i for i in range(4)]
            min_f = min_val.floatValue[ch]
            max_f = max_val.floatValue[ch]
            if min_f == max_f:
                max_f = min_f + 1.0
            buckets = controller.GetHistogram(
                tex.resourceId, sub, comp_type, min_f, max_f, channels
            )
            ch_name = ["r", "g", "b", "a"][ch]
            for b_idx, count in enumerate(buckets):
                if ch == 0:
                    histogram.append({"bucket": b_idx, "r": int(count), "g": 0, "b": 0, "a": 0})
                else:
                    histogram[b_idx][ch_name] = int(count)
        result_data["histogram"] = histogram

    return _result_response(request_id, result_data), True


HANDLERS: dict[str, Handler] = {
    "tex_info": _handle_tex_info,
    "tex_export": _handle_tex_export,
    "tex_raw": _handle_tex_raw,
    "rt_export": _handle_rt_export,
    "rt_depth": _handle_rt_depth,
    "rt_overlay": _handle_rt_overlay,
    "tex_stats": _handle_tex_stats,
}
