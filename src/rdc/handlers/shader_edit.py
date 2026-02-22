"""Shader edit-replay handlers: encodings, build, replace, restore, restore_all."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    STAGE_MAP,
    _error_response,
    _result_response,
    _set_frame_event,
)

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState

_ENCODING_NAMES: dict[int, str] = {
    0: "Unknown",
    1: "DXBC",
    2: "GLSL",
    3: "SPIRV",
    4: "SPIRVAsm",
    5: "HLSL",
    6: "DXIL",
    7: "OpenGLSPIRV",
    8: "OpenGLSPIRVAsm",
    9: "Slang",
}
_ENCODING_VALUES: dict[str, int] = {v.upper(): k for k, v in _ENCODING_NAMES.items()}


def _handle_shader_encodings(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    controller = state.adapter.controller
    raw = controller.GetTargetShaderEncodings()
    encodings = sorted(
        [{"value": v, "name": _ENCODING_NAMES.get(v, "Unknown")} for v in raw],
        key=lambda e: e["value"],
    )
    return _result_response(request_id, {"encodings": encodings}), True


def _handle_shader_build(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    if "source" not in params:
        return _error_response(request_id, -32602, "missing required param: source"), True
    stage = str(params.get("stage", "")).lower()
    if stage not in STAGE_MAP:
        return _error_response(request_id, -32602, "invalid stage"), True

    enc_name = str(params.get("encoding", "GLSL")).upper()
    encoding = _ENCODING_VALUES.get(enc_name)
    if encoding is None:
        return _error_response(request_id, -32602, f"unknown encoding: {enc_name}"), True
    entry = str(params.get("entry", "main"))
    rd = state.rd
    flags = rd.ShaderCompileFlags()
    source_bytes = params["source"].encode("utf-8")

    controller = state.adapter.controller
    rid, warnings = controller.BuildTargetShader(
        entry, encoding, source_bytes, flags, rd.ShaderStage(STAGE_MAP[stage])
    )
    if int(rid) == 0:
        return _error_response(request_id, -32001, warnings or "build failed"), True
    state.built_shaders[int(rid)] = rid
    return _result_response(request_id, {"shader_id": int(rid), "warnings": warnings}), True


def _handle_shader_replace(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    for key in ("shader_id", "eid"):
        if key not in params:
            return _error_response(request_id, -32602, f"missing required param: {key}"), True
    stage = str(params.get("stage", "")).lower()
    if stage not in STAGE_MAP:
        return _error_response(request_id, -32602, "invalid stage"), True

    shader_id = int(params["shader_id"])
    if shader_id not in state.built_shaders:
        return _error_response(request_id, -32001, "unknown shader_id"), True

    replacement_rid = state.built_shaders[shader_id]
    eid = int(params["eid"])
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True

    pipe = state.adapter.get_pipeline_state()
    original_rid = pipe.GetShader(STAGE_MAP[stage])
    if int(original_rid) == 0:
        return _error_response(request_id, -32001, "no shader bound at stage"), True

    controller = state.adapter.controller
    controller.ReplaceResource(original_rid, replacement_rid)
    state.shader_replacements[int(original_rid)] = original_rid
    state._eid_cache = -1
    return _result_response(request_id, {"ok": True, "original_id": int(original_rid)}), True


def _handle_shader_restore(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    if "eid" not in params:
        return _error_response(request_id, -32602, "missing required param: eid"), True
    stage = str(params.get("stage", "")).lower()
    if stage not in STAGE_MAP:
        return _error_response(request_id, -32602, "invalid stage"), True

    eid = int(params["eid"])
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True

    pipe = state.adapter.get_pipeline_state()
    original_rid = pipe.GetShader(STAGE_MAP[stage])
    if int(original_rid) not in state.shader_replacements:
        return _error_response(request_id, -32001, "no replacement active for stage"), True

    controller = state.adapter.controller
    controller.RemoveReplacement(original_rid)
    del state.shader_replacements[int(original_rid)]
    state._eid_cache = -1
    return _result_response(request_id, {"ok": True}), True


def _handle_shader_restore_all(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True

    controller = state.adapter.controller
    restored_count = len(state.shader_replacements)
    freed_count = len(state.built_shaders)

    for rid_obj in state.shader_replacements.values():
        controller.RemoveReplacement(rid_obj)
    for rid_obj in state.built_shaders.values():
        controller.FreeTargetResource(rid_obj)

    state.shader_replacements.clear()
    state.built_shaders.clear()
    state._eid_cache = -1
    return _result_response(
        request_id, {"ok": True, "restored": restored_count, "freed": freed_count}
    ), True


HANDLERS: dict[str, Any] = {
    "shader_encodings": _handle_shader_encodings,
    "shader_build": _handle_shader_build,
    "shader_replace": _handle_shader_replace,
    "shader_restore": _handle_shader_restore,
    "shader_restore_all": _handle_shader_restore_all,
}
