"""Pipeline state handlers: all pipe_* methods."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    _STAGE_NAMES,
    STAGE_MAP,
    _enum_name,
    _error_response,
    _flatten_shader_var,
    _result_response,
    _sanitize_size,
    _set_frame_event,
    get_pipeline_for_stage,
)
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _handle_pipe_topology(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    return _result_response(
        request_id, {"eid": eid, "topology": _enum_name(pipe_state.GetPrimitiveTopology())}
    ), True


def _handle_pipe_viewport(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    vp = pipe_state.GetViewport(0)
    return _result_response(
        request_id,
        {
            "eid": eid,
            "x": vp.x,
            "y": vp.y,
            "width": vp.width,
            "height": vp.height,
            "minDepth": getattr(vp, "minDepth", 0.0),
            "maxDepth": getattr(vp, "maxDepth", 1.0),
        },
    ), True


def _handle_pipe_scissor(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    sc = pipe_state.GetScissor(0)
    return _result_response(
        request_id,
        {
            "eid": eid,
            "x": sc.x,
            "y": sc.y,
            "width": sc.width,
            "height": sc.height,
            "enabled": getattr(sc, "enabled", True),
        },
    ), True


def _handle_pipe_blend(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    blends = pipe_state.GetColorBlends()
    blend_rows: list[dict[str, Any]] = []
    for i, b in enumerate(blends):
        cb = getattr(b, "colorBlend", None)
        ab = getattr(b, "alphaBlend", None)
        blend_rows.append(
            {
                "rt": i,
                "enabled": getattr(b, "enabled", False),
                "srcColor": _enum_name(getattr(cb, "source", "")) if cb else "",
                "dstColor": _enum_name(getattr(cb, "destination", "")) if cb else "",
                "colorOp": _enum_name(getattr(cb, "operation", "")) if cb else "",
                "srcAlpha": _enum_name(getattr(ab, "source", "")) if ab else "",
                "dstAlpha": _enum_name(getattr(ab, "destination", "")) if ab else "",
                "alphaOp": _enum_name(getattr(ab, "operation", "")) if ab else "",
                "writeMask": getattr(b, "writeMask", 0),
            }
        )
    return _result_response(request_id, {"eid": eid, "blends": blend_rows}), True


def _handle_pipe_stencil(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    front, back = pipe_state.GetStencilFaces()

    def _face(f: Any) -> dict[str, Any]:
        return {
            "failOperation": _enum_name(getattr(f, "failOperation", "")),
            "depthFailOperation": _enum_name(getattr(f, "depthFailOperation", "")),
            "passOperation": _enum_name(getattr(f, "passOperation", "")),
            "function": _enum_name(getattr(f, "function", "")),
            "reference": getattr(f, "reference", 0),
            "compareMask": getattr(f, "compareMask", 0),
            "writeMask": getattr(f, "writeMask", 0),
        }

    return _result_response(
        request_id, {"eid": eid, "front": _face(front), "back": _face(back)}
    ), True


def _handle_pipe_vinputs(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    inputs = pipe_state.GetVertexInputs()
    rows = []
    for vi in inputs:
        fmt = getattr(vi, "format", None)
        rows.append(
            {
                "name": getattr(vi, "name", ""),
                "vertexBuffer": getattr(vi, "vertexBuffer", 0),
                "byteOffset": getattr(vi, "byteOffset", 0),
                "perInstance": getattr(vi, "perInstance", False),
                "instanceRate": getattr(vi, "instanceRate", 0),
                "format": fmt.Name() if fmt and hasattr(fmt, "Name") else str(fmt) if fmt else "",
            }
        )
    return _result_response(request_id, {"eid": eid, "inputs": rows}), True


def _handle_pipe_samplers(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    all_samplers: list[dict[str, Any]] = []
    for stage_name, stage_val in STAGE_MAP.items():
        if hasattr(pipe_state, "GetSamplers"):
            samplers = pipe_state.GetSamplers(stage_val, True)
        else:
            samplers = []
        for i, s in enumerate(samplers):
            sd = getattr(s, "sampler", s)
            all_samplers.append(
                {
                    "stage": stage_name,
                    "slot": i,
                    "addressU": _enum_name(getattr(sd, "addressU", "")),
                    "addressV": _enum_name(getattr(sd, "addressV", "")),
                    "addressW": _enum_name(getattr(sd, "addressW", "")),
                    "filter": _enum_name(getattr(sd, "filter", "")),
                    "maxAnisotropy": getattr(sd, "maxAnisotropy", 0),
                    "minLOD": getattr(sd, "minLOD", 0.0),
                    "maxLOD": getattr(sd, "maxLOD", 0.0),
                    "mipBias": getattr(sd, "mipBias", 0.0),
                }
            )
    return _result_response(request_id, {"eid": eid, "samplers": all_samplers}), True


def _handle_pipe_vbuffers(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    vbs = pipe_state.GetVBuffers()
    rows = []
    for i, vb in enumerate(vbs):
        rows.append(
            {
                "slot": i,
                "resourceId": int(vb.resourceId),
                "byteOffset": getattr(vb, "byteOffset", 0),
                "byteSize": _sanitize_size(getattr(vb, "byteSize", 0)),
                "byteStride": getattr(vb, "byteStride", 0),
            }
        )
    return _result_response(request_id, {"eid": eid, "vbuffers": rows}), True


def _handle_pipe_ibuffer(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    ib = pipe_state.GetIBuffer()
    return _result_response(
        request_id,
        {
            "eid": eid,
            "resourceId": int(ib.resourceId),
            "byteOffset": getattr(ib, "byteOffset", 0),
            "byteSize": _sanitize_size(getattr(ib, "byteSize", 0)),
            "byteStride": getattr(ib, "byteStride", 0),
        },
    ), True


def _handle_pipe_push_constants(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    controller = state.adapter.controller
    push_constants: list[dict[str, Any]] = []
    for stage_val, stage_name in _STAGE_NAMES.items():
        shader_id = pipe_state.GetShader(stage_val)
        if int(shader_id) == 0:
            continue
        refl = pipe_state.GetShaderReflection(stage_val)
        if refl is None:
            continue
        pipe = get_pipeline_for_stage(pipe_state, stage_val)
        entry = pipe_state.GetShaderEntryPoint(stage_val)
        for idx, cb in enumerate(getattr(refl, "constantBlocks", [])):
            if getattr(cb, "bufferBacked", True):
                continue
            bound = pipe_state.GetConstantBlock(stage_val, idx, 0)
            desc = bound.descriptor
            cbuffer_vars = controller.GetCBufferVariableContents(
                pipe,
                shader_id,
                stage_val,
                entry,
                idx,
                desc.resource,
                desc.byteOffset,
                desc.byteSize,
            )
            variables = [_flatten_shader_var(v) for v in cbuffer_vars]
            push_constants.append(
                {
                    "stage": stage_name,
                    "name": cb.name,
                    "size": getattr(cb, "byteSize", 0),
                    "variables": variables,
                }
            )
    raw = getattr(pipe_state, "pushconsts", b"")
    return _result_response(
        request_id,
        {"eid": eid, "push_constants": push_constants, "raw_bytes": raw.hex()},
    ), True


def _handle_pipe_rasterizer(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    rast = getattr(pipe_state, "rasterizer", None)
    rast_data: dict[str, Any] = {"eid": eid}
    if rast is not None:
        for f in (
            "fillMode",
            "cullMode",
            "frontCCW",
            "depthBiasEnable",
            "depthBiasConstantFactor",
            "depthBiasClamp",
            "depthBiasSlopeFactor",
            "lineWidth",
        ):
            v = getattr(rast, f, None)
            if v is not None:
                rast_data[f] = _enum_name(v)
    return _result_response(request_id, rast_data), True


def _handle_pipe_depth_stencil(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    ds = getattr(pipe_state, "depthStencil", None)
    ds_data: dict[str, Any] = {"eid": eid}
    if ds is not None:
        for f in (
            "depthTestEnable",
            "depthWriteEnable",
            "depthFunction",
            "depthBoundsEnable",
            "minDepthBounds",
            "maxDepthBounds",
            "stencilTestEnable",
        ):
            v = getattr(ds, f, None)
            if v is not None:
                ds_data[f] = _enum_name(v)
    return _result_response(request_id, ds_data), True


def _handle_pipe_msaa(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    ms = getattr(pipe_state, "multisample", None)
    ms_data: dict[str, Any] = {"eid": eid}
    if ms is not None:
        for f in ("rasterSamples", "sampleShadingEnable", "minSampleShading", "sampleMask"):
            v = getattr(ms, f, None)
            if v is not None:
                ms_data[f] = v
    return _result_response(request_id, ms_data), True


HANDLERS: dict[str, Handler] = {
    "pipe_topology": _handle_pipe_topology,
    "pipe_viewport": _handle_pipe_viewport,
    "pipe_scissor": _handle_pipe_scissor,
    "pipe_blend": _handle_pipe_blend,
    "pipe_stencil": _handle_pipe_stencil,
    "pipe_vinputs": _handle_pipe_vinputs,
    "pipe_samplers": _handle_pipe_samplers,
    "pipe_vbuffers": _handle_pipe_vbuffers,
    "pipe_ibuffer": _handle_pipe_ibuffer,
    "pipe_push_constants": _handle_pipe_push_constants,
    "pipe_rasterizer": _handle_pipe_rasterizer,
    "pipe_depth_stencil": _handle_pipe_depth_stencil,
    "pipe_msaa": _handle_pipe_msaa,
}
