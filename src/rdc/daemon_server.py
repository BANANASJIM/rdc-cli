from __future__ import annotations

import argparse
import json
import re
import secrets
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdc.adapter import RenderDocAdapter

_LOG_SEVERITY_MAP: dict[int, str] = {0: "HIGH", 1: "MEDIUM", 2: "LOW", 3: "INFO"}
_VALID_LOG_LEVELS: set[str] = {*_LOG_SEVERITY_MAP.values(), "UNKNOWN"}


@dataclass
class DaemonState:
    capture: str
    current_eid: int
    token: str
    adapter: RenderDocAdapter | None = None
    cap: Any = None
    structured_file: Any = None
    api_name: str = ""
    max_eid: int = 0
    vfs_tree: Any = field(default=None, repr=False)
    _eid_cache: int = field(default=-1, repr=False)
    temp_dir: Path | None = None


def _detect_version(rd: Any) -> tuple[int, int]:
    """Detect RenderDoc version from module."""
    from rdc.adapter import parse_version_tuple

    try:
        return parse_version_tuple(rd.GetVersionString())
    except (AttributeError, TypeError):
        return (0, 0)


def _load_replay(state: DaemonState) -> str | None:
    """Load renderdoc module and open capture. Returns error string or None."""
    from rdc.discover import find_renderdoc

    rd = find_renderdoc()
    if rd is None:
        return "failed to import renderdoc module"

    try:
        rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    except Exception as exc:  # noqa: BLE001
        return f"InitialiseReplay failed: {exc}"

    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(state.capture, "", None)
    if result != rd.ResultCode.Succeeded:
        cap.Shutdown()
        return f"OpenFile failed: {result}"

    if cap.LocalReplaySupport() != rd.ReplaySupport.Supported:
        cap.Shutdown()
        return "local replay not supported on this platform"

    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    if result != rd.ResultCode.Succeeded:
        cap.Shutdown()
        return f"OpenCapture failed: {result}"

    state.cap = cap
    version = _detect_version(rd)
    state.adapter = RenderDocAdapter(controller=controller, version=version)
    state.structured_file = cap.GetStructuredData()

    api_props = state.adapter.get_api_properties()
    pt = getattr(api_props, "pipelineType", "Unknown")
    state.api_name = getattr(pt, "name", str(pt))

    root_actions = state.adapter.get_root_actions()
    state.max_eid = _max_eid(root_actions)

    from rdc.vfs.tree_cache import build_vfs_skeleton

    resources = state.adapter.get_resources()
    state.vfs_tree = build_vfs_skeleton(root_actions, resources, state.structured_file)

    import tempfile

    state.temp_dir = Path(tempfile.mkdtemp(prefix=f"rdc-{state.token[:8]}-"))

    return None


def _max_eid(actions: list[Any]) -> int:
    """Return the maximum eventId in the action tree."""
    result = 0
    for a in actions:
        result = max(result, a.eventId)
        if a.children:
            result = max(result, _max_eid(a.children))
    return result


def _count_events(actions: list[Any]) -> int:
    """Count total events in action tree (for display only)."""
    count = 0
    for a in actions:
        count += 1
        if a.children:
            count += _count_events(a.children)
    return count


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


def _find_resource_by_id(state: DaemonState, resource_id: int) -> Any | None:
    """Find a resource by its integer ID."""
    if state.adapter is None:
        return None
    for r in state.adapter.get_resources():
        if int(getattr(r, "resourceId", 0)) == resource_id:
            return r
    return None


def run_server(  # pragma: no cover
    host: str,
    port: int,
    state: DaemonState,
    idle_timeout_s: int = 1800,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(32)
        server.settimeout(1.0)

        running = True
        last_activity = time.time()
        while running:
            if time.time() - last_activity > idle_timeout_s:
                break

            try:
                conn, _addr = server.accept()
            except TimeoutError:
                continue

            with conn:
                line = _recv_line(conn)
                if not line:
                    continue
                try:
                    request = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    error_resp = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "parse error"},
                        "id": None,
                    }
                    conn.sendall((json.dumps(error_resp) + "\n").encode("utf-8"))
                    continue
                response, running = _handle_request(request, state)
                conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
                last_activity = time.time()


def _recv_line(conn: socket.socket) -> str:
    chunks: list[bytes] = []
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    if not chunks:
        return ""
    return b"".join(chunks).split(b"\n", 1)[0].decode("utf-8")


def _handle_request(request: dict[str, Any], state: DaemonState) -> tuple[dict[str, Any], bool]:
    request_id = request.get("id", 0)
    params = request.get("params") or {}
    token = params.get("_token")
    if token is None or not secrets.compare_digest(token, state.token):
        return _error_response(request_id, -32600, "invalid token"), True

    method = request.get("method")
    if method == "ping":
        return _result_response(request_id, {"ok": True}), True
    if method == "status":
        return _result_response(
            request_id,
            {
                "capture": state.capture,
                "current_eid": state.current_eid,
                "api": state.api_name,
                "event_count": state.max_eid,
            },
        ), True
    if method == "goto":
        eid = int(params.get("eid", 0))
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err), True
        return _result_response(request_id, {"current_eid": state.current_eid}), True
    if method == "count":
        what = params.get("what", "")
        pass_name = params.get("pass")
        if what == "resources":
            if state.adapter is None:
                return _error_response(request_id, -32002, "no replay loaded"), True
            from rdc.services.query_service import count_resources

            resources = state.adapter.get_resources()
            value = count_resources(resources)
            return _result_response(request_id, {"value": value}), True
        try:
            if state.adapter is None:
                return _error_response(request_id, -32002, "no replay loaded"), True
            from rdc.services.query_service import count_from_actions

            actions = state.adapter.get_root_actions()
            value = count_from_actions(actions, what, pass_name=pass_name)
            return _result_response(request_id, {"value": value}), True
        except ValueError as exc:
            return _error_response(request_id, -32602, str(exc)), True
    if method == "shader_map":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import collect_shader_map

        actions = state.adapter.get_root_actions()
        pipe_states = _collect_pipe_states(actions, state)
        rows = collect_shader_map(actions, pipe_states)
        return _result_response(request_id, {"rows": rows}), True
    if method == "pipeline":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import pipeline_row

        eid = int(params.get("eid", state.current_eid))
        section = params.get("section")
        if section is not None:
            section = str(section).lower()
            if section not in {"vs", "hs", "ds", "gs", "ps", "cs"}:
                return _error_response(request_id, -32602, "invalid section"), True
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err), True
        pipe_state = state.adapter.get_pipeline_state()
        row = pipeline_row(state.current_eid, state.api_name, pipe_state, section=section)
        return _result_response(request_id, {"row": row}), True
    if method == "bindings":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import bindings_rows

        eid = int(params.get("eid", state.current_eid))
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err), True
        pipe_state = state.adapter.get_pipeline_state()
        rows = bindings_rows(state.current_eid, pipe_state)

        # Filter by binding index (descriptor set filtering not yet implemented)
        binding_index = params.get("binding")
        if binding_index is not None:
            rows = [r for r in rows if r.get("slot") == binding_index]

        return _result_response(request_id, {"rows": rows}), True
    if method == "shader":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import shader_row

        eid = int(params.get("eid", state.current_eid))
        stage = str(params.get("stage", "ps")).lower()
        if stage not in {"vs", "hs", "ds", "gs", "ps", "cs"}:
            return _error_response(request_id, -32602, "invalid stage"), True
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err), True
        pipe_state = state.adapter.get_pipeline_state()
        row = shader_row(state.current_eid, pipe_state, stage)
        return _result_response(request_id, {"row": row}), True
    if method == "shaders":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import shader_inventory

        actions = state.adapter.get_root_actions()
        pipe_states = _collect_pipe_states(actions, state)
        rows = shader_inventory(pipe_states)
        return _result_response(request_id, {"rows": rows}), True
    if method == "resources":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import get_resources

        rows = get_resources(state.adapter)
        return _result_response(request_id, {"rows": rows}), True

    if method == "resource":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import get_resource_detail

        resid = int(params.get("id", 0))
        detail = get_resource_detail(state.adapter, resid)
        if detail is None:
            return _error_response(request_id, -32001, "resource not found"), True
        return _result_response(request_id, {"resource": detail}), True

    if method == "passes":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import get_pass_hierarchy

        actions = state.adapter.get_root_actions()
        tree = get_pass_hierarchy(actions, state.structured_file)
        return _result_response(request_id, {"tree": tree}), True

    if method == "pass":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        from rdc.services.query_service import get_pass_detail

        identifier: int | str
        if "index" in params:
            try:
                identifier = int(params["index"])
            except (TypeError, ValueError):
                return _error_response(request_id, -32602, "index must be an integer"), True
        elif "name" in params:
            name = str(params["name"])
            # Reverse VFS pass name sanitization (e.g. "Shadow_Terrain" → "Shadow/Terrain")
            if state.vfs_tree and name in state.vfs_tree.pass_name_map:
                name = state.vfs_tree.pass_name_map[name]
            identifier = name
        else:
            return _error_response(request_id, -32602, "missing index or name"), True
        actions = state.adapter.get_root_actions()
        detail = get_pass_detail(actions, state.structured_file, identifier)
        if detail is None:
            return _error_response(request_id, -32001, "pass not found"), True
        # Fetch attachment info at begin_eid
        err = _set_frame_event(state, detail["begin_eid"])
        if err is None:
            pipe = state.adapter.get_pipeline_state()
            detail["color_targets"] = [
                {"id": int(t.resource)} for t in pipe.GetOutputTargets() if int(t.resource) != 0
            ]
            depth_id = int(pipe.GetDepthTarget().resource)
            detail["depth_target"] = depth_id if depth_id != 0 else None
        else:
            detail["color_targets"] = []
            detail["depth_target"] = None
        return _result_response(request_id, detail), True
    if method == "log":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        controller = state.adapter.controller
        level_filter = params.get("level")
        if level_filter is not None:
            level_filter = str(level_filter).upper()
            if level_filter not in _VALID_LOG_LEVELS:
                return _error_response(request_id, -32602, f"invalid level: {level_filter}"), True
        eid_filter = params.get("eid")
        if eid_filter is not None:
            try:
                eid_filter = int(eid_filter)
            except (TypeError, ValueError):
                return _error_response(request_id, -32602, "eid must be an integer"), True
        msgs = controller.GetDebugMessages() if hasattr(controller, "GetDebugMessages") else []
        log_rows: list[dict[str, Any]] = []
        for m in msgs:
            lvl = _LOG_SEVERITY_MAP.get(int(m.severity), "UNKNOWN")
            if level_filter and lvl != level_filter:
                continue
            raw_eid = int(m.eventId)
            if eid_filter is not None and raw_eid != eid_filter:
                continue
            log_rows.append({"level": lvl, "eid": raw_eid, "message": m.description})
        return _result_response(request_id, {"messages": log_rows}), True

    if method == "shader_targets":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        controller = state.adapter.controller
        if hasattr(controller, "GetDisassemblyTargets"):
            targets = controller.GetDisassemblyTargets(True)
            target_list = [str(t) for t in targets]
        else:
            # Fallback for older RenderDoc versions
            target_list = ["DXIL", "DX", "SPIR-V", "GLSL"]
        return _result_response(request_id, {"targets": target_list}), True

    if method == "shader_reflect":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        eid = int(params.get("eid", state.current_eid))
        stage = str(params.get("stage", "ps")).lower()
        if stage not in {"vs", "hs", "ds", "gs", "ps", "cs"}:
            return _error_response(request_id, -32602, "invalid stage"), True
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err), True

        pipe_state = state.adapter.get_pipeline_state()
        stage_val = {"vs": 0, "hs": 1, "ds": 2, "gs": 3, "ps": 4, "cs": 5}[stage]
        refl = pipe_state.GetShaderReflection(stage_val)

        if refl is None:
            return _error_response(request_id, -32001, "no reflection available"), True

        # Extract input/output signatures and constant blocks
        input_sig = []
        output_sig = []
        constant_blocks = []

        for sig in getattr(refl, "inputSig", []):
            input_sig.append(
                {
                    "name": sig.name,
                    "semantic": getattr(sig, "semantic", ""),
                    "location": getattr(sig, "location", 0),
                    "component": getattr(sig, "component", 0),
                    "type": str(getattr(sig, "varType", "")),
                }
            )

        for sig in getattr(refl, "outputSig", []):
            output_sig.append(
                {
                    "name": sig.name,
                    "semantic": getattr(sig, "semantic", ""),
                    "location": getattr(sig, "location", 0),
                    "component": getattr(sig, "component", 0),
                    "type": str(getattr(sig, "varType", "")),
                }
            )

        for cb in getattr(refl, "constantBlocks", []):
            constant_blocks.append(
                {
                    "name": cb.name,
                    "bind_point": getattr(cb, "bindPoint", 0),
                    "size": getattr(cb, "bufferSize", 0),
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

    if method == "shader_constants":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        eid = int(params.get("eid", state.current_eid))
        stage = str(params.get("stage", "ps")).lower()
        if stage not in {"vs", "hs", "ds", "gs", "ps", "cs"}:
            return _error_response(request_id, -32602, "invalid stage"), True
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err), True

        pipe_state = state.adapter.get_pipeline_state()
        stage_val = {"vs": 0, "hs": 1, "ds": 2, "gs": 3, "ps": 4, "cs": 5}[stage]
        refl = pipe_state.GetShaderReflection(stage_val)

        if refl is None:
            return _error_response(request_id, -32001, "no reflection available"), True

        # Get constant buffer values
        controller = state.adapter.controller
        constants = []

        for cb in getattr(refl, "constantBlocks", []):
            bind_point = getattr(cb, "bindPoint", 0)
            # Get the constant buffer data
            if hasattr(controller, "GetConstantBuffer"):
                cbuf_data = controller.GetConstantBuffer(stage_val, bind_point)
                if cbuf_data:
                    data_bytes = getattr(cbuf_data, "data", b"")
                    constants.append(
                        {
                            "name": cb.name,
                            "bind_point": bind_point,
                            "size": len(data_bytes),
                            "data": data_bytes.hex() if data_bytes else "",
                        }
                    )
            else:
                # Fallback: just report metadata
                constants.append(
                    {
                        "name": cb.name,
                        "bind_point": bind_point,
                        "size": getattr(cb, "bufferSize", 0),
                        "data": "",
                    }
                )

        return _result_response(
            request_id,
            {
                "eid": eid,
                "stage": stage,
                "constants": constants,
            },
        ), True

    if method == "shader_source":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        eid = int(params.get("eid", state.current_eid))
        stage = str(params.get("stage", "ps")).lower()
        if stage not in {"vs", "hs", "ds", "gs", "ps", "cs"}:
            return _error_response(request_id, -32602, "invalid stage"), True
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err), True

        pipe_state = state.adapter.get_pipeline_state()
        stage_val = {"vs": 0, "hs": 1, "ds": 2, "gs": 3, "ps": 4, "cs": 5}[stage]
        controller = state.adapter.controller

        source = ""
        has_debug_info = False

        # Try to get debug source
        if hasattr(controller, "GetDebugSource"):
            source = controller.GetDebugSource(stage_val)
            has_debug_info = bool(source)

        # Fallback to disassembly if no debug source
        if not source:
            if hasattr(controller, "GetDisassembly"):
                source = controller.GetDisassembly(stage_val)
            elif hasattr(controller, "GetShaderDisassembly"):
                source = controller.GetShaderDisassembly(stage_val)

        return _result_response(
            request_id,
            {
                "eid": eid,
                "stage": stage,
                "source": source,
                "has_debug_info": has_debug_info,
            },
        ), True

    if method == "shader_disasm":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        eid = int(params.get("eid", state.current_eid))
        stage = str(params.get("stage", "ps")).lower()
        target = str(params.get("target", ""))
        if stage not in {"vs", "hs", "ds", "gs", "ps", "cs"}:
            return _error_response(request_id, -32602, "invalid stage"), True
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err), True

        pipe_state = state.adapter.get_pipeline_state()
        stage_val = {"vs": 0, "hs": 1, "ds": 2, "gs": 3, "ps": 4, "cs": 5}[stage]
        controller = state.adapter.controller

        disasm = ""
        if hasattr(controller, "GetDisassembly"):
            if target and hasattr(controller, "GetDisassemblyForTarget"):
                disasm = controller.GetDisassemblyForTarget(stage_val, target)
            else:
                disasm = controller.GetDisassembly(stage_val)
        elif hasattr(controller, "GetShaderDisassembly"):
            disasm = controller.GetShaderDisassembly(stage_val)

        return _result_response(
            request_id,
            {
                "eid": eid,
                "stage": stage,
                "target": target,
                "disasm": disasm,
            },
        ), True

    if method == "shader_all":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        eid = int(params.get("eid", state.current_eid))
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err), True

        pipe_state = state.adapter.get_pipeline_state()
        stages = ["vs", "hs", "ds", "gs", "ps", "cs"]
        stage_val_map = {"vs": 0, "hs": 1, "ds": 2, "gs": 3, "ps": 4, "cs": 5}

        result_stages = []
        for stage in stages:
            stage_val = stage_val_map[stage]
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

        return _result_response(
            request_id,
            {
                "eid": eid,
                "stages": result_stages,
            },
        ), True

    if method == "info":
        return _handle_info(request_id, state), True
    if method == "stats":
        return _handle_stats(request_id, state), True
    if method == "events":
        return _handle_events(request_id, params, state), True
    if method == "draws":
        return _handle_draws(request_id, params, state), True
    if method == "event":
        return _handle_event_method(request_id, params, state), True
    if method == "draw":
        return _handle_draw_method(request_id, params, state), True
    if method == "vfs_ls":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        path = str(params.get("path", "/"))
        return _handle_vfs_ls(request_id, path, state), True

    if method == "vfs_tree":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        path = str(params.get("path", "/"))
        depth = int(params.get("depth", 2))
        return _handle_vfs_tree(request_id, path, depth, state), True

    if method == "tex_info":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        res_id = int(params.get("id", 0))
        resource = _find_resource_by_id(state, res_id)
        if resource is None:
            return _error_response(request_id, -32001, f"resource {res_id} not found"), True
        return _result_response(
            request_id,
            {
                "id": res_id,
                "name": getattr(resource, "name", ""),
                "format": getattr(getattr(resource, "format", None), "name", ""),
                "width": getattr(resource, "width", 0),
                "height": getattr(resource, "height", 0),
                "depth": getattr(resource, "depth", 0),
                "mips": getattr(resource, "mips", 1),
                "array_size": getattr(resource, "arraysize", 1),
            },
        ), True

    if method == "tex_export":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        if state.temp_dir is None:
            return _error_response(request_id, -32002, "temp directory not available"), True
        res_id = int(params.get("id", 0))
        mip = int(params.get("mip", 0))
        resource = _find_resource_by_id(state, res_id)
        if resource is None:
            return _error_response(request_id, -32001, f"resource {res_id} not found"), True
        max_mip = getattr(resource, "mips", 1)
        if mip >= max_mip:
            return _error_response(
                request_id, -32001, f"mip {mip} out of range (max: {max_mip - 1})"
            ), True
        temp_path = state.temp_dir / f"tex_{res_id}_mip{mip}.png"
        controller = state.adapter.controller
        texsave = type(
            "TextureSave",
            (),
            {
                "resourceId": resource.resourceId,
                "mip": mip,
                "slice": 0,
                "destType": 0,
            },
        )()
        controller.SaveTexture(texsave, str(temp_path))
        if not temp_path.exists():
            return _error_response(request_id, -32002, "SaveTexture failed"), True
        return _result_response(
            request_id,
            {
                "path": str(temp_path),
                "size": temp_path.stat().st_size,
            },
        ), True

    if method == "tex_raw":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        if state.temp_dir is None:
            return _error_response(request_id, -32002, "temp directory not available"), True
        res_id = int(params.get("id", 0))
        resource = _find_resource_by_id(state, res_id)
        if resource is None:
            return _error_response(request_id, -32001, f"resource {res_id} not found"), True
        controller = state.adapter.controller
        raw_data = controller.GetTextureData(resource.resourceId, None)
        temp_path = state.temp_dir / f"tex_{res_id}.raw"
        temp_path.write_bytes(raw_data)
        return _result_response(
            request_id,
            {
                "path": str(temp_path),
                "size": len(raw_data),
            },
        ), True

    if method == "buf_info":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        res_id = int(params.get("id", 0))
        resource = _find_resource_by_id(state, res_id)
        if resource is None:
            return _error_response(request_id, -32001, f"resource {res_id} not found"), True
        return _result_response(
            request_id,
            {
                "id": res_id,
                "name": getattr(resource, "name", ""),
                "size": getattr(resource, "width", 0),  # RenderDoc stores buffer byte size in width
                "usage": getattr(resource, "creationFlags", 0),
            },
        ), True

    if method == "buf_raw":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
        if state.temp_dir is None:
            return _error_response(request_id, -32002, "temp directory not available"), True
        res_id = int(params.get("id", 0))
        resource = _find_resource_by_id(state, res_id)
        if resource is None:
            return _error_response(request_id, -32001, f"resource {res_id} not found"), True
        controller = state.adapter.controller
        raw_data = controller.GetBufferData(resource.resourceId, 0, 0)
        temp_path = state.temp_dir / f"buf_{res_id}.bin"
        temp_path.write_bytes(raw_data)
        return _result_response(
            request_id,
            {
                "path": str(temp_path),
                "size": len(raw_data),
            },
        ), True

    if method == "rt_export":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
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
            return _error_response(
                request_id, -32001, f"target index {target_idx} out of range"
            ), True
        temp_path = state.temp_dir / f"rt_{eid}_color{target_idx}.png"
        texsave = type(
            "TextureSave",
            (),
            {
                "resourceId": match[0].resource,
                "mip": 0,
                "slice": 0,
                "destType": 0,
            },
        )()
        state.adapter.controller.SaveTexture(texsave, str(temp_path))
        if not temp_path.exists():
            return _error_response(request_id, -32002, "SaveTexture failed"), True
        return _result_response(
            request_id,
            {
                "path": str(temp_path),
                "size": temp_path.stat().st_size,
            },
        ), True

    if method == "rt_depth":
        if state.adapter is None:
            return _error_response(request_id, -32002, "no replay loaded"), True
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
        texsave = type(
            "TextureSave",
            (),
            {
                "resourceId": depth.resource,
                "mip": 0,
                "slice": 0,
                "destType": 0,
            },
        )()
        state.adapter.controller.SaveTexture(texsave, str(temp_path))
        if not temp_path.exists():
            return _error_response(request_id, -32002, "SaveTexture failed"), True
        return _result_response(
            request_id,
            {
                "path": str(temp_path),
                "size": temp_path.stat().st_size,
            },
        ), True

    if method == "shutdown":
        if state.temp_dir is not None:
            import shutil

            shutil.rmtree(state.temp_dir, ignore_errors=True)
        if state.adapter is not None:
            state.adapter.shutdown()
        if state.cap is not None:
            state.cap.Shutdown()
        return _result_response(request_id, {"ok": True}), False

    return _error_response(request_id, -32601, "method not found"), True


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
    )

    if flags & _DRAWCALL:
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


def _handle_info(request_id: int, state: DaemonState) -> dict[str, Any]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded")
    from rdc.services.query_service import aggregate_stats

    flat = _get_flat_actions(state)
    stats = aggregate_stats(flat)
    return _result_response(
        request_id,
        {
            "Capture": state.capture,
            "API": state.api_name,
            "Events": len(flat),
            "Draw Calls": (
                f"{stats.total_draws} "
                f"({stats.indexed_draws} indexed, "
                f"{stats.non_indexed_draws} non-indexed, "
                f"{stats.dispatches} dispatches)"
            ),
            "Clears": stats.clears,
            "Copies": stats.copies,
        },
    )


def _handle_stats(request_id: int, state: DaemonState) -> dict[str, Any]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded")
    from rdc.services.query_service import aggregate_stats, get_top_draws

    flat = _get_flat_actions(state)
    stats = aggregate_stats(flat)
    top = get_top_draws(flat, limit=3)
    per_pass = [
        {
            "name": ps.name,
            "draws": ps.draws,
            "dispatches": ps.dispatches,
            "triangles": ps.triangles,
            "rt_w": ps.rt_w or "-",
            "rt_h": ps.rt_h or "-",
            "attachments": ps.attachments,
        }
        for ps in stats.per_pass
    ]
    top_draws = [
        {
            "eid": a.eid,
            "marker": a.parent_marker,
            "triangles": (a.num_indices // 3) * a.num_instances,
        }
        for a in top
    ]
    return _result_response(request_id, {"per_pass": per_pass, "top_draws": top_draws})


def _handle_events(request_id: int, params: dict[str, Any], state: DaemonState) -> dict[str, Any]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded")
    from rdc.services.query_service import filter_by_pattern, filter_by_type

    flat = _get_flat_actions(state)
    event_type = params.get("type")
    if event_type:
        flat = filter_by_type(flat, event_type)
    pattern = params.get("filter")
    if pattern:
        flat = filter_by_pattern(flat, pattern)
    eid_range = params.get("range")
    if eid_range and ":" in str(eid_range):
        parts = str(eid_range).split(":", 1)
        lo = int(parts[0]) if parts[0] else 0
        hi = int(parts[1]) if parts[1] else 999999999
        flat = [a for a in flat if lo <= a.eid <= hi]
    limit = params.get("limit")
    if limit is not None:
        flat = flat[: int(limit)]
    events = [{"eid": a.eid, "type": _action_type_str(a.flags), "name": a.name} for a in flat]
    return _result_response(request_id, {"events": events})


def _handle_draws(request_id: int, params: dict[str, Any], state: DaemonState) -> dict[str, Any]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded")
    from rdc.services.query_service import aggregate_stats, filter_by_pass, filter_by_type

    all_flat = _get_flat_actions(state)
    all_stats = aggregate_stats(all_flat)
    flat = filter_by_type(all_flat, "draw")
    pass_name = params.get("pass")
    if pass_name:
        flat = filter_by_pass(flat, pass_name)
    sort_field = params.get("sort")
    if sort_field == "triangles":
        flat.sort(key=lambda a: (a.num_indices // 3) * a.num_instances, reverse=True)
    limit = params.get("limit")
    if limit is not None:
        flat = flat[: int(limit)]
    draws = [
        {
            "eid": a.eid,
            "type": _action_type_str(a.flags),
            "triangles": (a.num_indices // 3) * a.num_instances,
            "instances": a.num_instances,
            "pass": a.pass_name,
            "marker": a.parent_marker,
        }
        for a in flat
    ]
    summary = (
        f"{all_stats.total_draws} draw calls "
        f"({all_stats.indexed_draws} indexed, "
        f"{all_stats.dispatches} dispatches, "
        f"{all_stats.clears} clears)"
    )
    return _result_response(request_id, {"draws": draws, "summary": summary})


def _handle_event_method(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> dict[str, Any]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded")
    eid = params.get("eid")
    if eid is None:
        return _error_response(request_id, -32602, "missing eid parameter")
    from rdc.services.query_service import find_action_by_eid

    eid = int(eid)
    action = find_action_by_eid(state.adapter.get_root_actions(), eid)
    if action is None:
        return _error_response(request_id, -32002, f"eid {eid} out of range (max: {state.max_eid})")
    sf = state.structured_file
    api_call = "-"
    params_dict: dict[str, Any] = {}
    if action.events and sf and hasattr(sf, "chunks"):
        for evt in action.events:
            idx = evt.chunkIndex
            if 0 <= idx < len(sf.chunks):
                chunk = sf.chunks[idx]
                api_call = chunk.name
                for child in chunk.children:
                    val = child.data.basic.value if child.data and child.data.basic else "-"
                    params_dict[child.name] = val
                break
    result: dict[str, Any] = {"EID": eid, "API Call": api_call}
    if params_dict:
        param_str = chr(10).join(f"  {k:<20}{v}" for k, v in params_dict.items())
        result["Parameters"] = chr(10) + param_str
    else:
        result["Parameters"] = "-"
    result["Duration"] = "-"
    return _result_response(request_id, result)


def _handle_draw_method(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> dict[str, Any]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded")
    from rdc.services.query_service import find_action_by_eid, walk_actions

    eid = params.get("eid")
    if eid is None:
        eid = state.current_eid
    eid = int(eid)
    root_actions = state.adapter.get_root_actions()
    action = find_action_by_eid(root_actions, eid)
    if action is None:
        return _error_response(request_id, -32002, f"eid {eid} out of range (max: {state.max_eid})")
    sf = state.structured_file
    flat = walk_actions(root_actions, sf)
    flat_match = [a for a in flat if a.eid == eid]
    name = action.GetName(sf) if sf else getattr(action, "_name", "-")
    marker = flat_match[0].parent_marker if flat_match else "-"
    tris = (action.numIndices // 3) * max(action.numInstances, 1)
    return _result_response(
        request_id,
        {
            "Event": eid,
            "Type": name,
            "Marker": marker,
            "Triangles": tris,
            "Instances": max(action.numInstances, 1),
        },
    )


_SHADER_PATH_RE = re.compile(r"^/draws/(\d+)/(?:shader|targets)(?:/|$)")


def _resolve_vfs_path(path: str, state: DaemonState) -> tuple[str, str | None]:
    """Normalize VFS path: strip trailing slash, resolve /current alias.

    Returns:
        (resolved_path, error_message_or_None)
    """
    path = path.rstrip("/") or "/"
    if path.startswith("/current"):
        if state.current_eid == 0:
            return path, "no current eid set"
        path = f"/draws/{state.current_eid}" + path[len("/current") :]
    return path, None


def _ensure_shader_populated(
    request_id: int, path: str, state: DaemonState
) -> dict[str, Any] | None:
    """Trigger dynamic shader subtree population if needed.

    Returns error response or None on success.
    """
    m = _SHADER_PATH_RE.match(path)
    if m and state.vfs_tree.get_draw_subtree(int(m.group(1))) is None:
        from rdc.vfs.tree_cache import populate_draw_subtree

        eid = int(m.group(1))
        err = _set_frame_event(state, eid)
        if err:
            return _error_response(request_id, -32002, err)
        pipe = state.adapter.get_pipeline_state()  # type: ignore[union-attr]
        populate_draw_subtree(state.vfs_tree, eid, pipe)
    return None


def _handle_vfs_ls(request_id: int, path: str, state: DaemonState) -> dict[str, Any]:
    path, err = _resolve_vfs_path(path, state)
    if err:
        return _error_response(request_id, -32002, err)

    if state.vfs_tree is None:
        return _error_response(request_id, -32002, "vfs tree not built")

    pop_err = _ensure_shader_populated(request_id, path, state)
    if pop_err:
        return pop_err

    node = state.vfs_tree.static.get(path)
    if node is None:
        return _error_response(request_id, -32001, f"not found: {path}")

    parent = path.rstrip("/")
    children = []
    for c in node.children:
        child_path = f"{parent}/{c}" if parent != "/" else f"/{c}"
        child_node = state.vfs_tree.static.get(child_path)
        children.append({"name": c, "kind": child_node.kind if child_node else "dir"})

    return _result_response(request_id, {"path": path, "kind": node.kind, "children": children})


def _handle_vfs_tree(request_id: int, path: str, depth: int, state: DaemonState) -> dict[str, Any]:
    path, err = _resolve_vfs_path(path, state)
    if err:
        return _error_response(request_id, -32002, err)

    if state.vfs_tree is None:
        return _error_response(request_id, -32002, "vfs tree not built")

    if depth < 1 or depth > 8:
        return _error_response(request_id, -32602, "depth must be 1-8")

    node = state.vfs_tree.static.get(path)
    if node is None:
        return _error_response(request_id, -32001, f"not found: {path}")

    tree = state.vfs_tree

    def _subtree(p: str, d: int) -> dict[str, Any]:
        _ensure_shader_populated(request_id, p, state)
        n = tree.static.get(p)
        if n is None:
            return {"name": p.rsplit("/", 1)[-1] or "/", "kind": "dir", "children": []}
        result: dict[str, Any] = {"name": n.name, "kind": n.kind, "children": []}
        if d > 0 and n.children:
            parent = p.rstrip("/")
            for c in n.children:
                child_path = f"{parent}/{c}" if parent != "/" else f"/{c}"
                result["children"].append(_subtree(child_path, d - 1))
        return result

    return _result_response(request_id, {"path": path, "tree": _subtree(path, depth)})


def _collect_pipe_states(
    actions: list[Any],
    state: DaemonState,
) -> dict[int, Any]:
    """Collect pipeline state for each draw/dispatch action."""
    result: dict[int, Any] = {}
    _collect_pipe_states_recursive(actions, state, result)
    return result


def _collect_pipe_states_recursive(
    actions: list[Any],
    state: DaemonState,
    result: dict[int, Any],
) -> None:
    for a in actions:
        flags = int(a.flags)
        is_draw = bool(flags & 0x0002)
        is_dispatch = bool(flags & 0x0004)
        if (is_draw or is_dispatch) and state.adapter is not None:
            _set_frame_event(state, a.eventId)
            result[a.eventId] = state.adapter.get_pipeline_state()
        if a.children:
            _collect_pipe_states_recursive(a.children, state, result)


def _result_response(request_id: int, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: int, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--idle-timeout", type=int, default=1800)
    parser.add_argument("--no-replay", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    state = DaemonState(capture=args.capture, current_eid=0, token=args.token)

    if not args.no_replay:
        err = _load_replay(state)
        if err:
            sys.stderr.write(f"error: {err}\n")
            sys.exit(1)

    run_server(
        host=args.host,
        port=args.port,
        state=state,
        idle_timeout_s=args.idle_timeout,
    )


if __name__ == "__main__":
    main()
