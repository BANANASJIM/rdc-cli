from __future__ import annotations

import argparse
import json
import secrets
import socket
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from rdc.adapter import RenderDocAdapter


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
    _eid_cache: int = field(default=-1, repr=False)


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
            identifier = str(params["name"])
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
    if method == "shutdown":
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
