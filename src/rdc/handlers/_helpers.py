"""Shared helpers for handler modules.

Handler modules import from here (not from daemon_server) to avoid
circular imports. daemon_server re-exports these for backward compat.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from rdc.services.query_service import STAGE_MAP as STAGE_MAP

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState

_UINT_MAX_SENTINEL = (1 << 64) - 1
_STAGE_NAMES: dict[int, str] = {v: k for k, v in STAGE_MAP.items()}
_SHADER_STAGES: frozenset[str] = frozenset(STAGE_MAP)

_SECTION_MAP: dict[str, str] = {
    "topology": "pipe_topology",
    "viewport": "pipe_viewport",
    "scissor": "pipe_scissor",
    "blend": "pipe_blend",
    "stencil": "pipe_stencil",
    "rasterizer": "pipe_rasterizer",
    "depth-stencil": "pipe_depth_stencil",
    "msaa": "pipe_msaa",
    "vbuffers": "pipe_vbuffers",
    "ibuffer": "pipe_ibuffer",
    "samplers": "pipe_samplers",
    "push-constants": "pipe_push_constants",
    "vinputs": "pipe_vinputs",
}

_LOG_SEVERITY_MAP: dict[int, str] = {0: "HIGH", 1: "MEDIUM", 2: "LOW", 3: "INFO"}
_VALID_LOG_LEVELS: set[str] = {*_LOG_SEVERITY_MAP.values(), "UNKNOWN"}

_SHADER_PATH_RE = re.compile(r"^/draws/(\d+)/(?:shader|targets|bindings|cbuffer)(?:/|$)")


def _result_response(request_id: int, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: int, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _enum_name(v: Any) -> Any:
    """Return .name for enum-like values, pass through others."""
    return v.name if hasattr(v, "name") else v


def _sanitize_size(v: int) -> int | str:
    """Return '-' for UINT_MAX sentinel values."""
    return "-" if v < 0 or v >= _UINT_MAX_SENTINEL else v


def _max_eid(actions: list[Any]) -> int:
    """Return the maximum eventId in the action tree."""
    result = 0
    for a in actions:
        result = max(result, a.eventId)
        if a.children:
            result = max(result, _max_eid(a.children))
    return result


def _set_frame_event(state: DaemonState, eid: int) -> str | None:
    """Set frame event with caching. Returns error string or None."""
    if eid < 0:
        return "eid must be >= 0"
    if state.max_eid > 0 and eid > state.max_eid:
        return f"eid {eid} out of range (max: {state.max_eid})"
    if state.adapter is not None:
        if state._eid_cache != eid:
            state.adapter.set_frame_event(eid)
            state._eid_cache = eid
    state.current_eid = eid
    return None


def _get_flat_actions(state: DaemonState) -> list[Any]:
    if state.adapter is None:
        return []
    from rdc.services.query_service import walk_actions

    return walk_actions(state.adapter.get_root_actions(), state.structured_file)


def _action_type_str(flags: int) -> str:
    from rdc.services.query_service import (
        _BEGIN_PASS,
        _CLEAR,
        _COPY,
        _DISPATCH,
        _DRAWCALL,
        _END_PASS,
        _INDEXED,
        _MESHDRAW,
    )

    if flags & (_DRAWCALL | _MESHDRAW):
        return "DrawIndexed" if flags & _INDEXED else "Draw"
    if flags & _DISPATCH:
        return "Dispatch"
    if flags & _CLEAR:
        return "Clear"
    if flags & _COPY:
        return "Copy"
    if flags & _BEGIN_PASS:
        return "BeginPass"
    if flags & _END_PASS:
        return "EndPass"
    return "Other"


def _build_shader_cache(state: DaemonState) -> None:
    """Single-pass shader cache: collect pipe states, disassembly, and metadata.

    Populates state.disasm_cache, state.shader_meta, and
    state._pipe_states_cache in one recursive walk. No-op if already built.
    Also populates the /shaders/ VFS subtree as a side effect.
    """
    if state._shader_cache_built or state.adapter is None:
        return

    from rdc.services.query_service import _DISPATCH as _QS_DISPATCH
    from rdc.services.query_service import _DRAWCALL, _MESHDRAW

    controller = state.adapter.controller
    target = get_default_disasm_target(controller)

    shader_stages: dict[int, list[str]] = {}
    shader_eids: dict[int, list[int]] = {}
    shader_reflections: dict[int, Any] = {}
    seen: set[int] = set()

    def _walk(actions: list[Any]) -> None:
        assert state.adapter is not None
        for a in actions:
            flags = int(a.flags)
            if (flags & (_DRAWCALL | _MESHDRAW)) or (flags & _QS_DISPATCH):
                _set_frame_event(state, a.eventId)
                pipe = state.adapter.get_pipeline_state()
                # Snapshot shader IDs (pipe is a mutable reference)
                stage_snap: dict[int, int] = {}
                for sv in range(6):
                    stage_snap[sv] = int(pipe.GetShader(sv))
                state._pipe_states_cache[a.eventId] = stage_snap

                for stage_val, stage_name in _STAGE_NAMES.items():
                    sid = int(pipe.GetShader(stage_val))
                    if sid == 0:
                        continue
                    if sid not in shader_stages:
                        shader_stages[sid] = []
                        shader_eids[sid] = []
                    if stage_name not in shader_stages[sid]:
                        shader_stages[sid].append(stage_name)
                    shader_eids[sid].append(a.eventId)

                    if sid not in seen:
                        seen.add(sid)
                        refl = pipe.GetShaderReflection(stage_val)
                        shader_reflections[sid] = refl
                        if refl is None:
                            state.disasm_cache[sid] = ""
                        else:
                            pipeline = get_pipeline_for_stage(pipe, stage_val)
                            disasm = (
                                controller.DisassembleShader(pipeline, refl, target)
                                if hasattr(controller, "DisassembleShader")
                                else ""
                            )
                            state.disasm_cache[sid] = disasm
            if a.children:
                _walk(a.children)

    _walk(state.adapter.get_root_actions())

    for sid in seen:
        refl = shader_reflections.get(sid)
        state.shader_meta[sid] = {
            "stages": shader_stages[sid],
            "uses": len(shader_eids[sid]),
            "first_eid": shader_eids[sid][0],
            "entry": getattr(refl, "entryPoint", "main") if refl else "main",
            "inputs": len(getattr(refl, "readOnlyResources", [])) if refl else 0,
            "outputs": len(getattr(refl, "readWriteResources", [])) if refl else 0,
        }

    state._shader_cache_built = True

    if state.vfs_tree is not None:
        from rdc.vfs.tree_cache import populate_shaders_subtree

        populate_shaders_subtree(state.vfs_tree, state.shader_meta)


def _make_texsave(rd: Any, resource_id: Any, mip: int = 0) -> Any:
    """Create a TextureSave object using the renderdoc module."""
    ts = rd.TextureSave()
    ts.resourceId = resource_id
    ts.mip = mip
    ts.slice = rd.TextureSliceMapping()
    ts.destType = rd.FileType.PNG
    return ts


def _make_subresource(rd: Any, mip: int = 0) -> Any:
    """Create a Subresource object using the renderdoc module."""
    sub = rd.Subresource()
    sub.mip = mip
    sub.slice = 0
    sub.sample = 0
    return sub


def require_pipe(
    params: dict[str, Any], state: DaemonState, request_id: int
) -> tuple[int, Any] | tuple[dict[str, Any], bool]:
    """Validate adapter, set eid, return pipe_state or error response.

    Returns:
        (eid, pipe_state) on success, or (error_dict, True) on failure.
    """
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        return _error_response(request_id, -32002, err), True
    pipe_state = state.adapter.get_pipeline_state()
    return eid, pipe_state


def get_pipeline_for_stage(pipe_state: Any, stage_val: int) -> Any:
    """Return the correct pipeline object for a shader stage."""
    return (
        pipe_state.GetComputePipelineObject()
        if stage_val == 5
        else pipe_state.GetGraphicsPipelineObject()
    )


def get_default_disasm_target(controller: Any) -> str:
    """Return the first available disassembly target, or 'SPIR-V'."""
    targets = (
        controller.GetDisassemblyTargets(True)
        if hasattr(controller, "GetDisassemblyTargets")
        else ["SPIR-V"]
    )
    return str(targets[0]) if targets else "SPIR-V"


def _resolve_vfs_path(path: str, state: DaemonState) -> tuple[str, str | None]:
    """Normalize VFS path: strip trailing slash, resolve /current alias."""
    path = path.rstrip("/") or "/"
    if path.startswith("/current"):
        if state.current_eid == 0:
            return path, "no current eid set"
        path = f"/draws/{state.current_eid}" + path[len("/current") :]
    return path, None


def _ensure_shader_populated(
    request_id: int, path: str, state: DaemonState
) -> dict[str, Any] | None:
    """Trigger dynamic shader subtree population if needed."""
    m = _SHADER_PATH_RE.match(path)
    if (
        m
        and state.vfs_tree is not None
        and state.vfs_tree.get_draw_subtree(int(m.group(1))) is None
    ):
        from rdc.vfs.tree_cache import populate_draw_subtree

        eid = int(m.group(1))
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err)
        pipe = state.adapter.get_pipeline_state()  # type: ignore[union-attr]
        assert state.vfs_tree is not None
        populate_draw_subtree(state.vfs_tree, eid, pipe)
    return None
