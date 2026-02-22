"""Buffer handlers: buf_info, buf_raw, postvs, mesh_data, cbuffer/vbuffer/ibuffer decode."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    STAGE_MAP,
    _enum_name,
    _error_response,
    _result_response,
    _set_frame_event,
    get_pipeline_for_stage,
)

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _handle_buf_info(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    res_id = int(params.get("id", 0))
    buf = state.buf_map.get(res_id)
    if buf is None:
        return _error_response(request_id, -32001, f"buffer {res_id} not found"), True
    return _result_response(
        request_id,
        {
            "id": res_id,
            "name": state.res_names.get(res_id, ""),
            "length": buf.length,
            "creation_flags": int(getattr(buf, "creationFlags", 0)),
            "gpu_address": getattr(buf, "gpuAddress", 0),
        },
    ), True


def _handle_buf_raw(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    if state.temp_dir is None:
        return _error_response(request_id, -32002, "temp directory not available"), True
    res_id = int(params.get("id", 0))
    buf = state.buf_map.get(res_id)
    if buf is None:
        return _error_response(request_id, -32001, f"buffer {res_id} not found"), True
    controller = state.adapter.controller
    raw_data = controller.GetBufferData(buf.resourceId, 0, 0)
    temp_path = state.temp_dir / f"buf_{res_id}.bin"
    temp_path.write_bytes(raw_data)
    return _result_response(
        request_id,
        {"path": str(temp_path), "size": len(raw_data)},
    ), True


def _handle_postvs(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    controller = state.adapter.controller
    mesh = controller.GetPostVSData(0, 0, 1)  # 1 = MeshDataStage.VSOut
    return _result_response(
        request_id,
        {
            "eid": eid,
            "vertexResourceId": int(getattr(mesh, "vertexResourceId", 0)),
            "vertexByteStride": getattr(mesh, "vertexByteStride", 0),
            "numIndices": getattr(mesh, "numIndices", 0),
            "topology": _enum_name(getattr(mesh, "topology", "")),
        },
    ), True


def _handle_cbuffer_decode(  # noqa: PLR0912
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    eid = int(params.get("eid", state.current_eid))
    cb_set = int(params.get("set", 0))
    cb_binding = int(params.get("binding", 0))
    stage_name = str(params.get("stage", "ps"))
    stage_val = STAGE_MAP.get(stage_name, 4)
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    refl = pipe_state.GetShaderReflection(stage_val)
    if refl is None:
        return _error_response(request_id, -32001, f"no reflection for stage {stage_name}"), True
    blocks = getattr(refl, "constantBlocks", [])
    target_block = None
    target_idx = 0
    for i, cb in enumerate(blocks):
        s = getattr(cb, "fixedBindSetOrSpace", 0)
        b = getattr(cb, "fixedBindNumber", 0)
        if s == cb_set and b == cb_binding:
            target_block = cb
            target_idx = i
            break
    if target_block is None:
        return _error_response(
            request_id,
            -32001,
            f"no constant block at set={cb_set} binding={cb_binding}",
        ), True
    controller = state.adapter.controller
    pipeline = get_pipeline_for_stage(pipe_state, stage_val)
    shader = pipe_state.GetShader(stage_val)
    entry = pipe_state.GetShaderEntryPoint(stage_val)
    if hasattr(pipe_state, "GetConstantBlock"):
        cb_desc = pipe_state.GetConstantBlock(stage_val, target_idx, 0)
        cb_resource = cb_desc.resource
        cb_offset = getattr(cb_desc, "byteOffset", 0)
        cb_size = getattr(cb_desc, "byteSize", 0)
    else:
        cb_resource = shader
        cb_offset = 0
        cb_size = 0
    variables = controller.GetCBufferVariableContents(
        pipeline,
        shader,
        stage_val,
        entry,
        target_idx,
        cb_resource,
        cb_offset,
        cb_size,
    )

    def _extract_value(v: Any) -> Any:
        val = getattr(v, "value", None)
        if val is None:
            return None
        f32v = getattr(val, "f32v", None)
        if f32v is not None:
            r = getattr(v, "rows", 1) or 1
            c = getattr(v, "columns", 1) or 1
            values = [f32v[ri * c + ci] for ri in range(r) for ci in range(c)]
            return values if len(values) > 1 else values[0]
        return val

    def _flatten_vars(
        vs: list[Any],
        prefix: str = "",
        depth: int = 0,
    ) -> list[dict[str, Any]]:
        if depth > 8:
            return []
        cb_rows: list[dict[str, Any]] = []
        for v in vs:
            name = f"{prefix}{getattr(v, 'name', '')}"
            members = getattr(v, "members", [])
            if members:
                cb_rows.extend(_flatten_vars(members, f"{name}.", depth + 1))
            else:
                vtype = getattr(v, "type", "")
                cb_rows.append({"name": name, "type": str(vtype), "value": _extract_value(v)})
        return cb_rows

    flat = _flatten_vars(variables)
    return _result_response(
        request_id, {"eid": eid, "set": cb_set, "binding": cb_binding, "variables": flat}
    ), True


def _handle_vbuffer_decode(  # noqa: PLR0912
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    inputs = pipe_state.GetVertexInputs()
    vbuffers = pipe_state.GetVBuffers()
    if not inputs:
        return _result_response(request_id, {"eid": eid, "columns": [], "vertices": []}), True
    controller = state.adapter.controller
    columns: list[str] = []
    col_defs: list[dict[str, Any]] = []
    for vi in inputs:
        fmt = getattr(vi, "format", None)
        comp_count = getattr(fmt, "compCount", 1) if fmt else 1
        attr_name = getattr(vi, "name", "attr")
        if comp_count == 1:
            columns.append(attr_name)
        else:
            suffixes = ["x", "y", "z", "w"][:comp_count]
            columns.extend(f"{attr_name}.{s}" for s in suffixes)
        col_defs.append(
            {
                "name": attr_name,
                "vbSlot": getattr(vi, "vertexBuffer", 0),
                "byteOffset": getattr(vi, "byteOffset", 0),
                "compCount": comp_count,
                "compByteWidth": getattr(fmt, "compByteWidth", 4) if fmt else 4,
            }
        )
    buf_data: dict[int, bytes] = {}
    for i, vb in enumerate(vbuffers):
        rid = getattr(vb, "resourceId", None)
        if rid is not None and int(rid) != 0:
            size = getattr(vb, "byteSize", 0)
            offset = getattr(vb, "byteOffset", 0)
            buf_data[i] = controller.GetBufferData(rid, offset, size)
    num_verts = int(params.get("count", 0))
    if num_verts == 0 and vbuffers:
        vb0 = vbuffers[0]
        stride = getattr(vb0, "byteStride", 0)
        if stride > 0:
            data_len = len(buf_data.get(0, b""))
            num_verts = data_len // stride
    vertices: list[list[float]] = []
    for vi_idx in range(num_verts):
        vtx_row: list[float] = []
        for cd in col_defs:
            slot = cd["vbSlot"]
            data = buf_data.get(slot, b"")
            vb = vbuffers[slot] if slot < len(vbuffers) else None
            stride = getattr(vb, "byteStride", 0) if vb else 0
            base = vi_idx * stride + cd["byteOffset"]
            for c in range(cd["compCount"]):
                off = base + c * cd["compByteWidth"]
                if off + cd["compByteWidth"] <= len(data):
                    if cd["compByteWidth"] == 4:
                        vtx_row.append(struct.unpack_from("<f", data, off)[0])
                    elif cd["compByteWidth"] == 2:
                        vtx_row.append(struct.unpack_from("<e", data, off)[0])
                    elif cd["compByteWidth"] == 1:
                        vtx_row.append(data[off] / 255.0)
                    else:
                        vtx_row.append(0.0)
                else:
                    vtx_row.append(0.0)
        vertices.append(vtx_row)
    return _result_response(
        request_id, {"eid": eid, "columns": columns, "vertices": vertices}
    ), True


_MESH_STAGE_MAP: dict[str, int] = {"vs-out": 1, "gs-out": 2}


def _handle_mesh_data(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Decode post-transform vertex data into position arrays."""
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    stage_name = str(params.get("stage", "vs-out"))
    stage_val = _MESH_STAGE_MAP.get(stage_name)
    if stage_val is None:
        return _error_response(
            request_id, -32602, f"invalid stage {stage_name!r}; use vs-out or gs-out"
        ), True
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    controller = state.adapter.controller
    mesh = controller.GetPostVSData(0, 0, stage_val)
    vrid = int(getattr(mesh, "vertexResourceId", 0))
    stride = getattr(mesh, "vertexByteStride", 0)
    if vrid == 0 or stride == 0:
        return _error_response(request_id, -32001, "no PostVS data at this event"), True
    fmt = getattr(mesh, "format", None)
    comp_width = getattr(fmt, "compByteWidth", 4) if fmt else 4
    comp_count = getattr(fmt, "compCount", 4) if fmt else 4
    v_offset = getattr(mesh, "vertexByteOffset", 0)
    v_size = getattr(mesh, "vertexByteSize", 0)
    raw = controller.GetBufferData(mesh.vertexResourceId, v_offset, v_size)
    num_verts = len(raw) // stride if stride > 0 else 0
    num_indices = getattr(mesh, "numIndices", 0)
    if num_indices > 0:
        irid = getattr(mesh, "indexResourceId", None)
        if irid is None or int(irid) == 0:
            num_verts = min(num_verts, num_indices)
    vertices: list[list[float]] = []
    for i in range(num_verts):
        base = i * stride
        comps: list[float] = []
        for c in range(comp_count):
            off = base + c * comp_width
            if off + comp_width <= len(raw):
                if comp_width == 4:
                    comps.append(struct.unpack_from("<f", raw, off)[0])
                elif comp_width == 2:
                    comps.append(struct.unpack_from("<e", raw, off)[0])
                else:
                    comps.append(0.0)
            else:
                comps.append(0.0)
        vertices.append(comps)
    # Decode index buffer
    irid = int(getattr(mesh, "indexResourceId", 0))
    indices: list[int] = []
    if irid != 0:
        i_offset = getattr(mesh, "indexByteOffset", 0)
        i_size = getattr(mesh, "indexByteSize", 0)
        i_stride = getattr(mesh, "indexByteStride", 0)
        if i_stride in (2, 4) and i_size > 0:
            iraw = controller.GetBufferData(mesh.indexResourceId, i_offset, i_size)
            fmt_str = "<H" if i_stride == 2 else "<I"
            for j in range(len(iraw) // i_stride):
                off = j * i_stride
                if off + i_stride <= len(iraw):
                    indices.append(struct.unpack_from(fmt_str, iraw, off)[0])
    topology = _enum_name(getattr(mesh, "topology", ""))
    return _result_response(
        request_id,
        {
            "eid": eid,
            "stage": stage_name,
            "topology": topology,
            "vertex_count": num_verts,
            "comp_count": comp_count,
            "stride": stride,
            "vertices": vertices,
            "index_count": len(indices),
            "indices": indices,
        },
    ), True


def _handle_ibuffer_decode(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    ib = pipe_state.GetIBuffer()
    rid = getattr(ib, "resourceId", None)
    if rid is None or int(rid) == 0:
        return _result_response(request_id, {"eid": eid, "format": "none", "indices": []}), True
    controller = state.adapter.controller
    raw_stride = getattr(ib, "byteStride", 0)
    stride = raw_stride if raw_stride in (2, 4) else 2
    offset = getattr(ib, "byteOffset", 0)
    size = getattr(ib, "byteSize", 0)
    data = controller.GetBufferData(rid, offset, size)
    fmt_str = "<H" if stride == 2 else "<I"
    count = len(data) // stride if stride > 0 else 0
    indices: list[int] = []
    for i in range(count):
        off = i * stride
        if off + stride <= len(data):
            indices.append(struct.unpack_from(fmt_str, data, off)[0])
    fmt_name = "uint16" if stride == 2 else "uint32"
    return _result_response(request_id, {"eid": eid, "format": fmt_name, "indices": indices}), True


HANDLERS: dict[str, Any] = {
    "buf_info": _handle_buf_info,
    "buf_raw": _handle_buf_raw,
    "postvs": _handle_postvs,
    "cbuffer_decode": _handle_cbuffer_decode,
    "vbuffer_decode": _handle_vbuffer_decode,
    "ibuffer_decode": _handle_ibuffer_decode,
    "mesh_data": _handle_mesh_data,
}
