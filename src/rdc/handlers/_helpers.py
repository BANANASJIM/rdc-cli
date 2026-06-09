"""Shared helpers for handler modules.

Handler modules import from here (not from daemon_server) to avoid
circular imports. daemon_server re-exports these for backward compat.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from rdc.services.query_service import STAGE_MAP as STAGE_MAP

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState

_log = logging.getLogger(__name__)


class PipeError(Exception):
    """Raised by require_pipe when pipeline state cannot be obtained."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        super().__init__()


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
_PASS_ATTACH_RE = re.compile(r"^/passes/([^/]+)/attachments(?:/|$)")


def _result_response(request_id: int, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: int, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _enum_name(v: Any) -> Any:
    """Return .name for enum-like values, str() for non-serializable others."""
    if hasattr(v, "name"):
        return v.name
    if isinstance(v, (str, int, float)) or v is None:
        return v
    _log.debug("_enum_name: unexpected type %s, coercing to str", type(v).__name__)
    return str(v)


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


def _seek_replay(state: DaemonState, eid: int) -> str | None:
    """Move replay head without changing user's current_eid."""
    if eid < 0:
        return "eid must be >= 0"
    if state.max_eid > 0 and eid > state.max_eid:
        return f"eid {eid} out of range (max: {state.max_eid})"
    if state.adapter is not None and state._eid_cache != eid:
        state.adapter.set_frame_event(eid)
        state._eid_cache = eid
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
                _seek_replay(state, a.eventId)
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

    # Restore replay head to user's position
    if state.current_eid != 0:
        _seek_replay(state, state.current_eid)

    for sid in seen:
        refl = shader_reflections.get(sid)
        state.shader_meta[sid] = {
            "stages": shader_stages[sid],
            "uses": len(shader_eids[sid]),
            "first_eid": shader_eids[sid][0],
            "eids": shader_eids[sid],
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


def _srgb_encode(linear: Any) -> Any:
    """Apply the sRGB OETF to a clipped [0, 1] float array."""
    import numpy as np

    lo = linear <= 0.0031308
    return np.where(lo, linear * 12.92, 1.055 * np.power(linear, 1.0 / 2.4) - 0.055)


def _decode_dtype(rd: Any, comp_type: int, comp_byte_width: int) -> str | None:
    """numpy dtype name for a (CompType, compByteWidth) pair, or None to reject.

    Pairs absent from this map have no unambiguous 8-bit display mapping
    (Typeless, SInt, UScaled, SScaled, exotic widths) and are rejected rather
    than guessed. Float covers half/single; packed floats (R11G11B10, R9G9B9E5)
    are non-Regular and never reach here.
    """
    ct = rd.CompType
    table: dict[tuple[int, int], str] = {
        (int(ct.Float), 2): "float16",
        (int(ct.Float), 4): "float32",
        (int(ct.UNorm), 1): "uint8",
        (int(ct.UNorm), 2): "uint16",
        (int(ct.UNormSRGB), 1): "uint8",
        (int(ct.SNorm), 1): "int8",
        (int(ct.SNorm), 2): "int16",
        (int(ct.UInt), 1): "uint8",
        (int(ct.UInt), 2): "uint16",
        (int(ct.Depth), 1): "uint8",
        (int(ct.Depth), 2): "uint16",
        (int(ct.Depth), 4): "float32",
    }
    return table.get((comp_type, comp_byte_width))


def _decode_texture_png(rd: Any, tex: Any, raw: bytes, mip: int, *, is_depth: bool) -> bytes | None:
    """Decode tightly packed GetTextureData bytes into PNG bytes.

    Handles the full ``ResourceFormatType.Regular`` space deliberately: every
    (CompType, compByteWidth) pair we can display is mapped to a numpy dtype and
    an explicit 8-bit conversion. Any pair not in the table (Typeless, SInt,
    UScaled, SScaled, exotic widths), every non-Regular format (block-compressed,
    packed, combined depth-stencil), MSAA, length mismatches, and empty data all
    return ``None`` so the caller emits a clean error rather than a wrong image.

    Args:
        rd: The renderdoc module.
        tex: TextureDescription for the resource.
        raw: Tightly packed pixel bytes for one subresource (top-down).
        mip: Mip level the bytes correspond to.
        is_depth: Whether to render the data as a single grayscale depth channel.

    For 3D textures (``depth > 1``) ``GetTextureData`` returns the whole
    width*height*depth mip. Every depth slice is tiled vertically into a single
    ``(depth*height, width)`` image so no slice is silently dropped; all slices
    share the same channel/sRGB/BGRA/expand processing. ``depth == 1`` is
    byte-for-byte identical to the 2D path.

    Returns:
        PNG-encoded bytes, or ``None`` if the format cannot be decoded.
    """
    import io

    import numpy as np
    from PIL import Image

    if not raw:
        return None

    fmt = tex.format
    if fmt.type != rd.ResourceFormatType.Regular:
        return None
    if getattr(tex, "msSamp", 1) > 1:
        return None

    width = max(1, tex.width >> mip)
    height = max(1, tex.height >> mip)
    depth_lvl = max(1, getattr(tex, "depth", 1) >> mip)
    cc = fmt.compCount
    cbw = fmt.compByteWidth
    if cc <= 0 or len(raw) != width * height * depth_lvl * cc * cbw:
        return None

    ct = int(fmt.compType)
    dtype_name = _decode_dtype(rd, ct, cbw)
    if dtype_name is None:
        return None
    # Tile depth slices vertically: (depth*height, width, cc).
    arr = np.frombuffer(raw, dtype=np.dtype(dtype_name)).reshape((depth_lvl * height, width, cc))
    height = depth_lvl * height

    if is_depth:
        d = arr[:, :, 0].astype(np.float32)
        d_min, d_max = float(d.min()), float(d.max())
        norm = (d - d_min) / (d_max - d_min) if d_max > d_min else np.zeros_like(d)
        gray = (norm * 255.0).round().astype(np.uint8)
        buf = io.BytesIO()
        Image.fromarray(gray, mode="L").save(buf, format="PNG")
        return buf.getvalue()

    if ct == int(rd.CompType.Float):
        sanitized = np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=1.0, neginf=0.0)
        f = np.clip(sanitized, 0.0, 1.0)
        rgba8 = (_srgb_encode(f) * 255.0).round().astype(np.uint8)
    elif ct == int(rd.CompType.SNorm):
        # [-1, 1] -> [0, 1]; divisor is the signed-int max for the width.
        denom = float(np.iinfo(np.dtype(dtype_name)).max)
        f = np.clip(arr.astype(np.float32) / denom, -1.0, 1.0) * 0.5 + 0.5
        rgba8 = (f * 255.0).round().astype(np.uint8)
    elif dtype_name == "uint16":
        rgba8 = (arr / 257.0).round().astype(np.uint8)
    else:
        rgba8 = arr.astype(np.uint8)

    if fmt.BGRAOrder() and cc >= 3:
        rgba8 = rgba8[:, :, [2, 1, 0] + list(range(3, cc))]

    if cc == 1:
        rgb = np.repeat(rgba8, 3, axis=2)
        out = np.dstack([rgb, np.full((height, width, 1), 255, np.uint8)])
    elif cc == 2:
        zero = np.zeros((height, width, 1), np.uint8)
        alpha = np.full((height, width, 1), 255, np.uint8)
        out = np.concatenate([rgba8, zero, alpha], axis=2)
    elif cc == 3:
        alpha = np.full((height, width, 1), 255, np.uint8)
        out = np.concatenate([rgba8, alpha], axis=2)
    else:
        out = rgba8

    buf = io.BytesIO()
    Image.fromarray(out, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def require_pipe(params: dict[str, Any], state: DaemonState, request_id: int) -> tuple[int, Any]:
    """Validate adapter, set eid, return pipe_state.

    Raises:
        PipeError: When adapter is not loaded or eid is invalid.
    """
    if state.adapter is None:
        raise PipeError(_error_response(request_id, -32002, "no replay loaded"))
    eid = int(params.get("eid", state.current_eid))
    err = _set_frame_event(state, eid)
    if err:
        raise PipeError(_error_response(request_id, -32002, err))
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


def _flatten_shader_var(var: Any) -> dict[str, Any]:
    """Recursively convert a ShaderVariable to a dict."""
    members = getattr(var, "members", [])
    if members:
        return {
            "name": var.name,
            "type": str(getattr(var, "type", "")),
            "rows": getattr(var, "rows", 0),
            "columns": getattr(var, "columns", 0),
            "value": None,
            "members": [_flatten_shader_var(m) for m in members],
        }

    rows = getattr(var, "rows", 0)
    columns = getattr(var, "columns", 0)
    count = max(rows * columns, 1)

    val = getattr(var, "value", None)
    if val is None:
        values: list[Any] = []
    else:
        type_str = str(getattr(var, "type", "")).lower()
        if "uint" in type_str:
            values = list(getattr(val, "u32v", [0.0] * 16)[:count])
        elif "int" in type_str or "sint" in type_str:
            values = list(getattr(val, "s32v", [0] * 16)[:count])
        else:
            values = list(getattr(val, "f32v", [0.0] * 16)[:count])

    return {
        "name": var.name,
        "type": str(getattr(var, "type", "")),
        "rows": rows,
        "columns": columns,
        "value": values,
    }


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
        err = _seek_replay(state, eid)
        if err:
            return _error_response(request_id, -32002, err)
        pipe = state.adapter.get_pipeline_state()  # type: ignore[union-attr]
        assert state.vfs_tree is not None
        populate_draw_subtree(state.vfs_tree, eid, pipe)
    return None


def _ensure_pass_attachments_populated(
    request_id: int, path: str, state: DaemonState
) -> dict[str, Any] | None:
    """Trigger dynamic pass attachment subtree population if needed."""
    m = _PASS_ATTACH_RE.match(path)
    if m is None or state.vfs_tree is None:
        return None
    pass_name = m.group(1)
    attach_path = f"/passes/{pass_name}/attachments"
    node = state.vfs_tree.static.get(attach_path)
    if node is None or node.children:
        return None

    safe_map = state.vfs_tree.pass_name_map
    orig_name = safe_map.get(pass_name, pass_name)
    pass_info = next((p for p in state.vfs_tree.pass_list if p["name"] == orig_name), None)
    if pass_info is None:
        return None

    begin_eid = pass_info.get("begin_eid", 0)
    err = _seek_replay(state, begin_eid)
    if err:
        return _error_response(request_id, -32002, err)
    pipe = state.adapter.get_pipeline_state()  # type: ignore[union-attr]
    from rdc.vfs.tree_cache import populate_pass_attachments

    populate_pass_attachments(state.vfs_tree, pass_name, pipe)
    return None
