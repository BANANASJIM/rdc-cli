"""Buffer handlers: buf_info, buf_raw, postvs, mesh_data, cbuffer/vbuffer/ibuffer decode."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    STAGE_MAP,
    PipeError,
    _enum_name,
    _error_response,
    _result_response,
    _set_frame_event,
    get_pipeline_for_stage,
    require_pipe,
)
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _decode_float_components(
    data: bytes, offset: int, comp_width: int, comp_count: int
) -> list[float]:
    """Decode comp_count float components of comp_width bytes each starting at offset."""
    result: list[float] = []
    for i in range(comp_count):
        off = offset + i * comp_width
        if comp_width == 4:
            result.append(struct.unpack_from("<f", data, off)[0])
        elif comp_width == 2:
            result.append(struct.unpack_from("<e", data, off)[0])
        else:  # comp_width == 1
            result.append(data[off] / 255.0)
    return result


def _decode_index_buffer(data: bytes, stride: int) -> list[int]:
    """Decode a flat index buffer with given per-index stride."""
    fmt = {1: "B", 2: "<H", 4: "<I"}[stride]
    item_size = struct.calcsize(fmt)
    return [struct.unpack_from(fmt, data, i)[0] for i in range(0, len(data), item_size)]


def _shader_variable_value_kind(var_type: Any) -> str:
    """Return the ShaderValue lane name for a reflected variable type."""
    if isinstance(var_type, int):
        if var_type == 4:
            return "u32v"
        if var_type == 5:
            return "s32v"
        return "f32v"

    type_name = getattr(var_type, "name", var_type)
    type_str = str(type_name).lower()
    if "uint" in type_str or type_str in {"u32", "uint32"}:
        return "u32v"
    if "sint" in type_str or "int" in type_str or type_str in {"s32", "int32"}:
        return "s32v"
    return "f32v"


def _shader_variable_values(var: Any) -> Any:
    """Extract a scalar or row-major vector/matrix value from ShaderValue."""
    val = getattr(var, "value", None)
    if val is None:
        return None
    r = getattr(var, "rows", 1) or 1
    c = getattr(var, "columns", 1) or 1
    lane = getattr(val, _shader_variable_value_kind(getattr(var, "type", "")), None)
    if lane is None:
        return val
    values = [lane[ri * c + ci] for ri in range(r) for ci in range(c)]
    return values if len(values) > 1 else values[0]


def _shader_stage_param(params: dict[str, Any], default: str = "ps") -> tuple[str, int]:
    stage_name = str(params.get("stage", default)).lower()
    if stage_name not in STAGE_MAP:
        allowed = ", ".join(STAGE_MAP)
        raise ValueError(f"invalid stage {stage_name!r}; use {allowed}")
    return stage_name, STAGE_MAP[stage_name]


def _find_action(actions: list[Any], eid: int) -> Any | None:
    for action in actions:
        if getattr(action, "eventId", None) == eid:
            return action
        found = _find_action(getattr(action, "children", []), eid)
        if found is not None:
            return found
    return None


def _handle_buf_info(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
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
    assert state.adapter is not None
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
    assert state.adapter is not None
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
    cb_set = int(params.get("set", 0))
    cb_binding = int(params.get("binding", 0))
    try:
        stage_name, stage_val = _shader_stage_param(params)
    except ValueError as exc:
        return _error_response(request_id, -32602, str(exc)), True
    try:
        eid, pipe_state = require_pipe(params, state, request_id)
    except PipeError as exc:
        return exc.response, True
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
    controller = state.adapter.controller  # type: ignore[union-attr]
    pipeline = get_pipeline_for_stage(pipe_state, stage_val)
    shader = pipe_state.GetShader(stage_val)
    entry = pipe_state.GetShaderEntryPoint(stage_val)
    if hasattr(pipe_state, "GetConstantBlock"):
        cb_used = pipe_state.GetConstantBlock(stage_val, target_idx, 0)
        cb_desc = cb_used.descriptor
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
                cb_rows.append(
                    {"name": name, "type": str(vtype), "value": _shader_variable_values(v)}
                )
        return cb_rows

    flat = _flatten_vars(variables)
    return _result_response(
        request_id, {"eid": eid, "set": cb_set, "binding": cb_binding, "variables": flat}
    ), True


def _handle_cbuffer_raw(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    cb_set = int(params.get("set", 0))
    cb_binding = int(params.get("binding", 0))
    try:
        stage_name, stage_val = _shader_stage_param(params)
    except ValueError as exc:
        return _error_response(request_id, -32602, str(exc)), True
    if state.temp_dir is None:
        return _error_response(request_id, -32002, "temp directory not available"), True
    try:
        eid, pipe_state = require_pipe(params, state, request_id)
    except PipeError as exc:
        return exc.response, True
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
    if not getattr(target_block, "bufferBacked", True):
        return _error_response(
            request_id,
            -32602,
            "cbuffer is not buffer-backed (push constant or root constant)",
        ), True
    if not hasattr(pipe_state, "GetConstantBlock"):
        return _error_response(
            request_id,
            -32601,
            "GetConstantBlock unavailable on this RenderDoc version",
        ), True
    controller = state.adapter.controller  # type: ignore[union-attr]
    cb_used = pipe_state.GetConstantBlock(stage_val, target_idx, 0)
    cb_desc = cb_used.descriptor
    cb_resource = cb_desc.resource
    cb_offset = getattr(cb_desc, "byteOffset", 0)
    cb_size = getattr(cb_desc, "byteSize", 0)
    if cb_resource is None or int(cb_resource) == 0:
        return _error_response(request_id, -32001, "cbuffer not bound at this draw"), True
    if cb_size == 0:
        cb_size = getattr(target_block, "byteSize", 0)
    if cb_size == 0:
        return _error_response(
            request_id,
            -32001,
            "cbuffer size is unknown (descriptor and reflection both report 0)",
        ), True
    raw_data = controller.GetBufferData(cb_resource, cb_offset, cb_size)
    temp_path = state.temp_dir / f"cbuffer_{eid}_{stage_name}_{cb_set}_{cb_binding}.bin"
    temp_path.write_bytes(raw_data)
    return _result_response(
        request_id,
        {"path": str(temp_path), "size": len(raw_data)},
    ), True


def _handle_vbuffer_decode(  # noqa: PLR0912
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    try:
        eid, pipe_state = require_pipe(params, state, request_id)
    except PipeError as exc:
        return exc.response, True
    inputs = pipe_state.GetVertexInputs()
    vbuffers = pipe_state.GetVBuffers()
    if not inputs:
        return _result_response(request_id, {"eid": eid, "columns": [], "vertices": []}), True
    controller = state.adapter.controller  # type: ignore[union-attr]
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
            cw = cd["compByteWidth"]
            cc = cd["compCount"]
            if base + cw * cc <= len(data) and cw in (1, 2, 4):
                vtx_row.extend(_decode_float_components(data, base, cw, cc))
            else:
                for c in range(cc):
                    off = base + c * cw
                    if off + cw <= len(data) and cw in (1, 2, 4):
                        vtx_row.extend(_decode_float_components(data, off, cw, 1))
                    else:
                        vtx_row.append(0.0)
        vertices.append(vtx_row)
    return _result_response(
        request_id, {"eid": eid, "columns": columns, "vertices": vertices}
    ), True


_MESH_STAGE_MAP: dict[str, int] = {"vs-in": 0, "vs-out": 1, "gs-out": 2}
_ACTION_INDEXED = 0x10000
_UINT64_MAX = (1 << 64) - 1


def _known_byte_size(value: Any) -> int:
    size = int(value or 0)
    return 0 if size < 0 or size >= _UINT64_MAX else size


def _mesh_data_usable(mesh: Any) -> bool:
    return (
        int(getattr(mesh, "vertexResourceId", 0)) != 0 and getattr(mesh, "vertexByteStride", 0) > 0
    )


def _same_postvs_source(a: Any, b: Any) -> bool:
    keys = (
        "vertexResourceId",
        "vertexByteStride",
        "vertexByteOffset",
        "vertexByteSize",
        "indexResourceId",
        "indexByteOffset",
        "indexByteSize",
        "indexByteStride",
    )
    return all(getattr(a, key, None) == getattr(b, key, None) for key in keys)


def _decode_mesh_postvs(controller: Any, mesh: Any) -> dict[str, Any]:
    vrid = int(getattr(mesh, "vertexResourceId", 0))
    stride = getattr(mesh, "vertexByteStride", 0)
    if vrid == 0 or stride == 0:
        raise ValueError("no PostVS data at this event")
    fmt = getattr(mesh, "format", None)
    comp_width = getattr(fmt, "compByteWidth", 4) if fmt else 4
    comp_count = getattr(fmt, "compCount", 4) if fmt else 4
    pos_offset = getattr(mesh, "vertexByteOffset", 0)
    v_size = _known_byte_size(getattr(mesh, "vertexByteSize", 0))
    if v_size == 0:
        raise ValueError("PostVS vertex buffer size is unknown")
    raw = controller.GetBufferData(mesh.vertexResourceId, 0, v_size)
    num_verts = len(raw) // stride if stride > 0 else 0
    num_indices = getattr(mesh, "numIndices", 0)
    if num_indices > 0:
        irid = getattr(mesh, "indexResourceId", None)
        if irid is None or int(irid) == 0:
            num_verts = min(num_verts, num_indices)
    vertices = _decode_position_rows(raw, num_verts, stride, pos_offset, comp_width, comp_count)

    irid = int(getattr(mesh, "indexResourceId", 0))
    base_vertex = getattr(mesh, "baseVertex", 0)
    indices: list[int] = []
    if irid != 0:
        i_offset = getattr(mesh, "indexByteOffset", 0)
        i_size = getattr(mesh, "indexByteSize", 0)
        i_stride = getattr(mesh, "indexByteStride", 0)
        if i_stride in (2, 4) and i_size > 0:
            iraw = controller.GetBufferData(mesh.indexResourceId, i_offset, i_size)
            indices = [i + base_vertex for i in _decode_index_buffer(iraw, i_stride)]
    return {
        "topology": _enum_name(getattr(mesh, "topology", "")),
        "vertex_count": num_verts,
        "comp_count": comp_count,
        "stride": stride,
        "vertices": vertices,
        "index_count": len(indices),
        "indices": indices,
    }


def _decode_position_rows(
    raw: bytes,
    num_verts: int,
    stride: int,
    pos_offset: int,
    comp_width: int,
    comp_count: int,
) -> list[list[float]]:
    vertices: list[list[float]] = []
    for i in range(num_verts):
        base = i * stride + pos_offset
        if base + comp_width * comp_count <= len(raw) and comp_width in (1, 2, 4):
            vertices.append(_decode_float_components(raw, base, comp_width, comp_count))
        else:
            comps: list[float] = []
            for c in range(comp_count):
                off = base + c * comp_width
                if off + comp_width <= len(raw) and comp_width in (1, 2, 4):
                    comps.extend(_decode_float_components(raw, off, comp_width, 1))
                else:
                    comps.append(0.0)
            vertices.append(comps)
    return vertices


def _position_input(inputs: list[Any]) -> Any | None:
    for vi in inputs:
        name = str(getattr(vi, "name", "") or getattr(vi, "semanticName", "")).lower()
        if "position" in name or name.startswith("pos"):
            return vi
    return None


def _mesh_data_from_ia(controller: Any, pipe_state: Any, action: Any | None) -> dict[str, Any]:
    if action is None:
        raise ValueError("no draw action found for eid")
    inputs = pipe_state.GetVertexInputs()
    pos_input = _position_input(inputs)
    if pos_input is None:
        raise ValueError("no vertex input POSITION at this event")
    vbuffers = pipe_state.GetVBuffers()
    slot = getattr(pos_input, "vertexBuffer", 0)
    if slot >= len(vbuffers):
        raise ValueError(f"vertex buffer slot {slot} is not bound")
    vb = vbuffers[slot]
    vrid = getattr(vb, "resourceId", None)
    stride = getattr(vb, "byteStride", 0)
    if vrid is None or int(vrid) == 0 or stride == 0:
        raise ValueError("POSITION vertex buffer is not bound")

    fmt = getattr(pos_input, "format", None)
    comp_width = getattr(fmt, "compByteWidth", 4) if fmt else 4
    comp_count = getattr(fmt, "compCount", 3) if fmt else 3
    vb_offset = getattr(vb, "byteOffset", 0)
    action_count = int(getattr(action, "numIndices", 0) or 0)

    first_vertex = 0
    local_indices: list[int] = []
    ib = pipe_state.GetIBuffer()
    irid = getattr(ib, "resourceId", None)
    i_stride = getattr(ib, "byteStride", 0)
    is_indexed = bool(int(getattr(action, "flags", 0)) & _ACTION_INDEXED)
    if action_count <= 0:
        num_verts = 0
    elif is_indexed and irid is not None and int(irid) != 0 and i_stride in (1, 2, 4):
        i_offset = getattr(ib, "byteOffset", 0)
        i_offset += int(getattr(action, "indexOffset", 0) or 0) * i_stride
        i_size = action_count * i_stride
        if i_size > 0:
            iraw = controller.GetBufferData(irid, i_offset, i_size)
            base_vertex = int(getattr(action, "baseVertex", 0) or 0)
            referenced = [i + base_vertex for i in _decode_index_buffer(iraw, i_stride)]
            if referenced:
                first_vertex = min(referenced)
                if first_vertex < 0:
                    raise ValueError("indexed draw references a negative vertex")
                local_indices = [i - first_vertex for i in referenced]
        num_verts = max(local_indices) + 1 if local_indices else 0
    elif is_indexed:
        raise ValueError("indexed draw index buffer is not bound")
    else:
        first_vertex = int(getattr(action, "vertexOffset", 0) or 0)
        num_verts = action_count

    known_vb_size = _known_byte_size(getattr(vb, "byteSize", 0))
    if known_vb_size > 0:
        remaining = max(known_vb_size - first_vertex * stride, 0)
        num_verts = min(num_verts, remaining // stride)
        if local_indices and any(i >= num_verts for i in local_indices):
            raise ValueError("indexed draw references vertices outside the bound vertex buffer")
    pos_offset = getattr(pos_input, "byteOffset", 0)
    read_size = num_verts * stride
    raw = (
        controller.GetBufferData(vrid, vb_offset + first_vertex * stride, read_size)
        if read_size
        else b""
    )
    vertices = _decode_position_rows(raw, num_verts, stride, pos_offset, comp_width, comp_count)

    return {
        "topology": _enum_name(pipe_state.GetPrimitiveTopology()),
        "vertex_count": len(vertices),
        "comp_count": comp_count,
        "stride": stride,
        "vertices": vertices,
        "index_count": len(local_indices),
        "indices": local_indices,
    }


def _handle_mesh_data(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Decode post-transform vertex data into position arrays."""
    assert state.adapter is not None
    stage_name = str(params.get("stage", "vs-out"))
    stage_val = _MESH_STAGE_MAP.get(stage_name)
    if stage_val is None:
        return _error_response(
            request_id, -32602, f"invalid stage {stage_name!r}; use vs-in, vs-out or gs-out"
        ), True
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    controller = state.adapter.controller
    mesh = controller.GetPostVSData(0, 0, stage_val)
    try:
        if stage_name == "vs-in":
            use_ia = not _mesh_data_usable(mesh)
            if not use_ia:
                vs_out = controller.GetPostVSData(0, 0, _MESH_STAGE_MAP["vs-out"])
                use_ia = _mesh_data_usable(vs_out) and _same_postvs_source(mesh, vs_out)
            if use_ia:
                pipe_state = state.adapter.get_pipeline_state()
                action = _find_action(state.adapter.get_root_actions(), eid)
                decoded = _mesh_data_from_ia(controller, pipe_state, action)
            else:
                decoded = _decode_mesh_postvs(controller, mesh)
        else:
            decoded = _decode_mesh_postvs(controller, mesh)
    except ValueError as exc:
        return _error_response(request_id, -32001, str(exc)), True
    return _result_response(
        request_id,
        {
            "eid": eid,
            "stage": stage_name,
            **decoded,
        },
    ), True


def _handle_ibuffer_decode(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    try:
        eid, pipe_state = require_pipe(params, state, request_id)
    except PipeError as exc:
        return exc.response, True
    ib = pipe_state.GetIBuffer()
    rid = getattr(ib, "resourceId", None)
    if rid is None or int(rid) == 0:
        return _result_response(request_id, {"eid": eid, "format": "none", "indices": []}), True
    controller = state.adapter.controller  # type: ignore[union-attr]
    raw_stride = getattr(ib, "byteStride", 0)
    stride = raw_stride if raw_stride in (2, 4) else 2
    offset = getattr(ib, "byteOffset", 0)
    size = getattr(ib, "byteSize", 0)
    data = controller.GetBufferData(rid, offset, size)
    indices = _decode_index_buffer(data, stride)
    fmt_name = "uint16" if stride == 2 else "uint32"
    return _result_response(request_id, {"eid": eid, "format": fmt_name, "indices": indices}), True


HANDLERS: dict[str, Handler] = {
    "buf_info": _handle_buf_info,
    "buf_raw": _handle_buf_raw,
    "postvs": _handle_postvs,
    "cbuffer_decode": _handle_cbuffer_decode,
    "cbuffer_raw": _handle_cbuffer_raw,
    "vbuffer_decode": _handle_vbuffer_decode,
    "ibuffer_decode": _handle_ibuffer_decode,
    "mesh_data": _handle_mesh_data,
}
