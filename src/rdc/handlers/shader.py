"""Shader handlers: targets, reflect, constants, source, disasm, all, list_info, list_disasm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rdc.handlers._helpers import (
    STAGE_MAP,
    _build_shader_cache,
    _error_response,
    _flatten_shader_var,
    _result_response,
    get_default_disasm_target,
    get_pipeline_for_stage,
    require_pipe,
)
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _handle_shader_targets(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    controller = state.adapter.controller
    if hasattr(controller, "GetDisassemblyTargets"):
        targets = controller.GetDisassemblyTargets(True)
        target_list = [str(t) for t in targets]
    else:
        target_list = ["DXIL", "DX", "SPIR-V", "GLSL"]
    return _result_response(request_id, {"targets": target_list}), True


def _handle_shader_reflect(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    stage = str(params.get("stage", "ps")).lower()
    if stage not in STAGE_MAP:
        return _error_response(request_id, -32602, "invalid stage"), True
    result = require_pipe(params, state, request_id)
    if isinstance(result[1], bool):
        return result  # type: ignore[return-value]
    eid, pipe_state = cast(tuple[int, Any], result)
    stage_val = STAGE_MAP[stage]
    refl = pipe_state.GetShaderReflection(stage_val)

    if refl is None:
        return _error_response(request_id, -32001, "no reflection available"), True

    input_sig = []
    output_sig = []
    constant_blocks = []

    for sig in getattr(refl, "inputSignature", []):
        input_sig.append(
            {
                "name": getattr(sig, "varName", ""),
                "semantic": getattr(sig, "semanticName", ""),
                "location": getattr(sig, "regIndex", 0),
                "component": getattr(sig, "compCount", 0),
                "type": str(getattr(sig, "compType", "")),
            }
        )

    for sig in getattr(refl, "outputSignature", []):
        output_sig.append(
            {
                "name": getattr(sig, "varName", ""),
                "semantic": getattr(sig, "semanticName", ""),
                "location": getattr(sig, "regIndex", 0),
                "component": getattr(sig, "compCount", 0),
                "type": str(getattr(sig, "compType", "")),
            }
        )

    for cb in getattr(refl, "constantBlocks", []):
        constant_blocks.append(
            {
                "name": cb.name,
                "bind_point": getattr(cb, "fixedBindNumber", getattr(cb, "bindPoint", 0)),
                "size": getattr(cb, "byteSize", 0),
                "variables": len(getattr(cb, "variables", [])),
            }
        )

    return _result_response(
        request_id,
        {
            "eid": eid,
            "stage": stage,
            "input_sig": input_sig,
            "output_sig": output_sig,
            "constant_blocks": constant_blocks,
        },
    ), True


def _handle_shader_constants(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    stage = str(params.get("stage", "ps")).lower()
    if stage not in STAGE_MAP:
        return _error_response(request_id, -32602, "invalid stage"), True
    result = require_pipe(params, state, request_id)
    if isinstance(result[1], bool):
        return result  # type: ignore[return-value]
    eid, pipe_state = cast(tuple[int, Any], result)
    stage_val = STAGE_MAP[stage]
    refl = pipe_state.GetShaderReflection(stage_val)

    if refl is None:
        return _error_response(request_id, -32001, "no reflection available"), True

    controller = state.adapter.controller  # type: ignore[union-attr]
    pipe = get_pipeline_for_stage(pipe_state, stage_val)
    shader_id = pipe_state.GetShader(stage_val)
    entry = pipe_state.GetShaderEntryPoint(stage_val)
    constants: list[dict[str, Any]] = []

    for idx, cb_def in enumerate(getattr(refl, "constantBlocks", [])):
        bind_point = getattr(cb_def, "fixedBindNumber", getattr(cb_def, "bindPoint", 0))
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
        constants.append(
            {
                "name": cb_def.name,
                "bind_point": bind_point,
                "variables": variables,
            }
        )

    return _result_response(
        request_id,
        {"eid": eid, "stage": stage, "constants": constants},
    ), True


def _handle_shader_source(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    stage = str(params.get("stage", "ps")).lower()
    if stage not in STAGE_MAP:
        return _error_response(request_id, -32602, "invalid stage"), True
    result = require_pipe(params, state, request_id)
    if isinstance(result[1], bool):
        return result  # type: ignore[return-value]
    eid, pipe_state = cast(tuple[int, Any], result)
    stage_val = STAGE_MAP[stage]
    controller = state.adapter.controller  # type: ignore[union-attr]
    refl = pipe_state.GetShaderReflection(stage_val)

    source = ""
    files: list[dict[str, str]] = []
    has_debug_info = False

    if refl is not None:
        debug_files = getattr(getattr(refl, "debugInfo", None), "files", [])
        if debug_files:
            has_debug_info = True
            files = [{"filename": f.filename, "source": f.contents} for f in debug_files]
        else:
            pipeline = get_pipeline_for_stage(pipe_state, stage_val)
            tgt = get_default_disasm_target(controller)
            source = controller.DisassembleShader(pipeline, refl, tgt)

    return _result_response(
        request_id,
        {
            "eid": eid,
            "stage": stage,
            "has_debug_info": has_debug_info,
            "files": files,
            "source": source,
        },
    ), True


def _handle_shader_disasm(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    stage = str(params.get("stage", "ps")).lower()
    target = str(params.get("target", ""))
    if stage not in STAGE_MAP:
        return _error_response(request_id, -32602, "invalid stage"), True
    result = require_pipe(params, state, request_id)
    if isinstance(result[1], bool):
        return result  # type: ignore[return-value]
    eid, pipe_state = cast(tuple[int, Any], result)
    stage_val = STAGE_MAP[stage]
    controller = state.adapter.controller  # type: ignore[union-attr]
    refl = pipe_state.GetShaderReflection(stage_val)

    disasm = ""
    used_target = target
    if refl is not None:
        pipeline = get_pipeline_for_stage(pipe_state, stage_val)
        if not used_target:
            used_target = get_default_disasm_target(controller)
        disasm = controller.DisassembleShader(pipeline, refl, used_target)

    return _result_response(
        request_id,
        {"eid": eid, "stage": stage, "target": used_target, "disasm": disasm},
    ), True


def _handle_shader_all(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    result = require_pipe(params, state, request_id)
    if isinstance(result[1], bool):
        return result  # type: ignore[return-value]
    eid, pipe_state = cast(tuple[int, Any], result)
    result_stages = []
    for stage, stage_val in STAGE_MAP.items():
        sid = pipe_state.GetShader(stage_val)
        sidv = int(sid)
        if sidv == 0:
            continue

        refl = pipe_state.GetShaderReflection(stage_val)
        entry = pipe_state.GetShaderEntryPoint(stage_val)

        result_stages.append(
            {
                "stage": stage,
                "shader": sidv,
                "entry": entry,
                "ro": len(getattr(refl, "readOnlyResources", [])) if refl else 0,
                "rw": len(getattr(refl, "readWriteResources", [])) if refl else 0,
                "cbuffers": len(getattr(refl, "constantBlocks", [])) if refl else 0,
            }
        )

    return _result_response(request_id, {"eid": eid, "stages": result_stages}), True


def _handle_shader_list_info(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    _build_shader_cache(state)
    sid = int(params.get("id", 0))
    info_meta = state.shader_meta.get(sid)
    if info_meta is None:
        return _error_response(request_id, -32001, f"shader {sid} not found"), True
    return _result_response(request_id, {"id": sid, **info_meta}), True


def _handle_shader_list_disasm(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    _build_shader_cache(state)
    sid = int(params.get("id", 0))
    if sid not in state.disasm_cache:
        return _error_response(request_id, -32001, f"shader {sid} not found"), True
    return _result_response(request_id, {"id": sid, "disasm": state.disasm_cache[sid]}), True


HANDLERS: dict[str, Handler] = {
    "shader_targets": _handle_shader_targets,
    "shader_reflect": _handle_shader_reflect,
    "shader_constants": _handle_shader_constants,
    "shader_source": _handle_shader_source,
    "shader_disasm": _handle_shader_disasm,
    "shader_all": _handle_shader_all,
    "shader_list_info": _handle_shader_list_info,
    "shader_list_disasm": _handle_shader_list_disasm,
}
