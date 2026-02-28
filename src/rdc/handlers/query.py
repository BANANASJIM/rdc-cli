"""Query handlers: shader_map, pipeline, bindings, shader, shaders, resources,
resource, passes, pass, events, draws, event, draw, search, info, stats, log.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from rdc.handlers._helpers import (
    _LOG_SEVERITY_MAP,
    _SECTION_MAP,
    _SHADER_STAGES,
    _VALID_LOG_LEVELS,
    STAGE_MAP,
    _action_type_str,
    _build_shader_cache,
    _error_response,
    _result_response,
    _seek_replay,
    require_pipe,
)
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _get_flat_actions(state: DaemonState) -> list[Any]:
    """Late-bound wrapper so tests can patch rdc.daemon_server._get_flat_actions."""
    import rdc.daemon_server as ds

    return ds._get_flat_actions(state)


def _handle_shader_map(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    from rdc.services.query_service import collect_shader_map

    _build_shader_cache(state)
    actions = state.adapter.get_root_actions()
    rows = collect_shader_map(actions, state._pipe_states_cache)
    return _result_response(request_id, {"rows": rows}), True


def _handle_pipeline(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    from rdc.services.query_service import pipeline_row

    section = params.get("section")
    if section is not None:
        section = str(section).lower()
        if section not in _SHADER_STAGES and section not in _SECTION_MAP:
            return _error_response(request_id, -32602, "invalid section"), True
    result = require_pipe(params, state, request_id)
    if isinstance(result[1], bool):
        return result  # type: ignore[return-value]
    eid, pipe_state = cast(tuple[int, Any], result)
    if section is not None and section in _SECTION_MAP:
        from rdc.handlers.pipe_state import HANDLERS as PIPE_HANDLERS

        handler = PIPE_HANDLERS.get(_SECTION_MAP[section])
        if handler is not None:
            pipe_result: tuple[dict[str, Any], bool] = handler(
                request_id, {"_token": params.get("_token", ""), "eid": eid}, state
            )
            return pipe_result
        return _error_response(request_id, -32602, "invalid section"), True
    row = pipeline_row(state.current_eid, state.api_name, pipe_state, section=section)
    return _result_response(request_id, {"row": row}), True


def _handle_bindings(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    from rdc.services.query_service import bindings_rows

    result = require_pipe(params, state, request_id)
    if isinstance(result[1], bool):
        return result  # type: ignore[return-value]
    _eid, pipe_state = cast(tuple[int, Any], result)
    rows = bindings_rows(state.current_eid, pipe_state)

    set_filter = params.get("set")
    if set_filter is not None:
        rows = [r for r in rows if r.get("set") == int(set_filter)]
    binding_index = params.get("binding")
    if binding_index is not None:
        rows = [r for r in rows if r.get("slot") == int(binding_index)]

    return _result_response(request_id, {"rows": rows}), True


def _handle_shader(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    from rdc.services.query_service import shader_row

    stage = str(params.get("stage", "ps")).lower()
    if stage not in STAGE_MAP:
        return _error_response(request_id, -32602, "invalid stage"), True
    result = require_pipe(params, state, request_id)
    if isinstance(result[1], bool):
        return result  # type: ignore[return-value]
    _eid, pipe_state = cast(tuple[int, Any], result)
    row = shader_row(state.current_eid, pipe_state, stage)
    return _result_response(request_id, {"row": row}), True


def _handle_shaders(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    _build_shader_cache(state)
    rows = [
        {"shader": sid, "stages": ",".join(sorted(meta["stages"])), "uses": meta["uses"]}
        for sid, meta in sorted(state.shader_meta.items())
    ]
    stage_filter = params.get("stage")
    if stage_filter:
        stage_filter = stage_filter.lower()
        rows = [r for r in rows if stage_filter in r["stages"].lower().split(",")]
    return _result_response(request_id, {"rows": rows}), True


def _handle_resources(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    from rdc.services.query_service import get_resources

    rows = get_resources(state.adapter)
    type_filter = params.get("type")
    name_filter = params.get("name")
    sort_by = params.get("sort", "id")
    if type_filter:
        rows = [r for r in rows if r["type"].lower() == type_filter.lower()]
    if name_filter:
        name_lower = name_filter.lower()
        rows = [r for r in rows if name_lower in r["name"].lower()]
    if sort_by in ("name", "type"):
        rows.sort(key=lambda r: r[sort_by].lower())
    return _result_response(request_id, {"rows": rows}), True


def _handle_resource(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    from rdc.services.query_service import get_resource_detail

    resid = int(params.get("id", 0))
    detail = get_resource_detail(state.adapter, resid)
    if detail is None:
        return _error_response(request_id, -32001, "resource not found"), True
    return _result_response(request_id, {"resource": detail}), True


def _handle_passes(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    from rdc.services.query_service import get_pass_hierarchy

    actions = state.adapter.get_root_actions()
    tree = get_pass_hierarchy(actions, state.structured_file)
    return _result_response(request_id, {"tree": tree}), True


def _handle_pass(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    from rdc.services.query_service import get_pass_detail

    identifier: int | str
    if "index" in params:
        try:
            identifier = int(params["index"])
        except (TypeError, ValueError):
            return _error_response(request_id, -32602, "index must be an integer"), True
    elif "name" in params:
        name = str(params["name"])
        if state.vfs_tree and name in state.vfs_tree.pass_name_map:
            name = state.vfs_tree.pass_name_map[name]
        identifier = name
    else:
        return _error_response(request_id, -32602, "missing index or name"), True
    actions = state.adapter.get_root_actions()
    detail = get_pass_detail(actions, state.structured_file, identifier)
    if detail is None:
        return _error_response(request_id, -32001, "pass not found"), True
    err = _seek_replay(state, detail["begin_eid"])
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


def _handle_log(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
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
    if state._debug_messages_cache is None:
        raw = controller.GetDebugMessages() if hasattr(controller, "GetDebugMessages") else []
        state._debug_messages_cache = list(raw)
    msgs = state._debug_messages_cache
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


def _handle_info(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    from rdc.services.query_service import aggregate_stats

    flat = _get_flat_actions(state)
    stats = aggregate_stats(flat)
    result: dict[str, Any] = {
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
    }
    if state.cap is not None:
        result["has_callstacks"] = state.cap.HasCallstacks()
        result["machine_ident"] = state.cap.RecordedMachineIdent()
        result["timestamp_base"] = state.cap.TimestampBase()
    return _result_response(request_id, result), True


def _handle_stats(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    from rdc.services.query_service import aggregate_stats, get_top_draws

    flat = _get_flat_actions(state)
    stats = aggregate_stats(flat)
    top = get_top_draws(flat, limit=3)

    # Find a representative draw EID per pass for RT enrichment
    from rdc.services.query_service import _DRAWCALL, _MESHDRAW

    pass_first_draw: dict[str, int] = {}
    for a in flat:
        if (a.flags & (_DRAWCALL | _MESHDRAW)) and a.pass_name not in pass_first_draw:
            pass_first_draw[a.pass_name] = a.eid
    for ps in stats.per_pass:
        draw_eid = pass_first_draw.get(ps.name)
        if draw_eid is None:
            continue
        err = _seek_replay(state, draw_eid)
        if err:
            continue
        try:
            pipe = state.adapter.get_pipeline_state()
            targets = pipe.GetOutputTargets()
            non_null = [t for t in targets if int(t.resource) != 0]
            ps.attachments = len(non_null)
            depth_id = int(pipe.GetDepthTarget().resource)
            if depth_id != 0:
                ps.attachments += 1
            if non_null:
                rid = int(non_null[0].resource)
                tex = state.tex_map.get(rid)
                if tex is not None:
                    ps.rt_w = tex.width
                    ps.rt_h = tex.height
        except Exception:
            pass  # fallback to defaults (0)

    # Restore replay head to user's position
    if state.current_eid != 0:
        _seek_replay(state, state.current_eid)

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
    return _result_response(request_id, {"per_pass": per_pass, "top_draws": top_draws}), True


def _handle_events(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
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
    return _result_response(request_id, {"events": events}), True


def _handle_draws(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    from rdc.services.query_service import (
        aggregate_stats,
        filter_by_pass,
        filter_by_type,
        pass_name_for_eid,
    )

    all_flat = _get_flat_actions(state)
    passes = state.vfs_tree.pass_list if state.vfs_tree else []
    pass_name = params.get("pass")
    if pass_name:
        _actions = state.adapter.get_root_actions()
        _sf = state.structured_file
        all_flat = filter_by_pass(all_flat, pass_name, actions=_actions, sf=_sf)
    stats = aggregate_stats(all_flat)
    flat = filter_by_type(all_flat, "draw")
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
            "pass": pass_name_for_eid(a.eid, passes),
            "marker": a.parent_marker,
        }
        for a in flat
    ]
    summary = (
        f"{stats.total_draws} draw calls "
        f"({stats.indexed_draws} indexed, "
        f"{stats.dispatches} dispatches, "
        f"{stats.clears} clears)"
    )
    return _result_response(request_id, {"draws": draws, "summary": summary}), True


def _handle_event(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    eid = params.get("eid")
    if eid is None:
        return _error_response(request_id, -32602, "missing eid parameter"), True
    from rdc.services.query_service import find_action_by_eid

    eid = int(eid)
    action = find_action_by_eid(state.adapter.get_root_actions(), eid)
    if action is None:
        return (
            _error_response(request_id, -32002, f"eid {eid} out of range (max: {state.max_eid})"),
            True,
        )
    sf = state.structured_file
    api_call = "-"
    params_dict: dict[str, Any] = {}
    if action.events and sf and hasattr(sf, "chunks"):
        for evt in action.events:
            idx = evt.chunkIndex
            if 0 <= idx < len(sf.chunks):
                chunk = sf.chunks[idx]
                api_call = chunk.name
                if hasattr(chunk, "NumChildren"):
                    for ci in range(chunk.NumChildren()):
                        child = chunk.GetChild(ci)
                        val = child.AsString() if hasattr(child, "AsString") else "-"
                        params_dict[child.name] = val
                else:
                    for child in chunk.children:
                        val = child.data.basic.value if child.data and child.data.basic else "-"
                        params_dict[child.name] = val
    result: dict[str, Any] = {"EID": eid, "API Call": api_call}
    if params_dict:
        param_str = chr(10).join(f"  {k:<20}{v}" for k, v in params_dict.items())
        result["Parameters"] = chr(10) + param_str
    else:
        result["Parameters"] = "-"
    result["Duration"] = "-"
    return _result_response(request_id, result), True


def _handle_draw(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    from rdc.services.query_service import find_action_by_eid, walk_actions

    eid = params.get("eid")
    if eid is None:
        eid = state.current_eid
    eid = int(eid)
    root_actions = state.adapter.get_root_actions()
    action = find_action_by_eid(root_actions, eid)
    if action is None:
        return (
            _error_response(request_id, -32002, f"eid {eid} out of range (max: {state.max_eid})"),
            True,
        )
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
    ), True


def _handle_search(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    pattern = str(params.get("pattern", ""))
    if not pattern:
        return _error_response(request_id, -32602, "missing pattern"), True
    if len(pattern) > 500:
        return _error_response(request_id, -32602, "pattern too long (max 500)"), True
    stage_filter = params.get("stage")
    if stage_filter is not None:
        stage_filter = str(stage_filter).lower()
    case_sensitive = bool(params.get("case_sensitive", False))
    limit = max(1, int(params.get("limit", 200)))
    context_lines = int(params.get("context", 0))
    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        return _error_response(request_id, -32602, f"invalid regex: {exc}"), True
    _build_shader_cache(state)
    matches: list[dict[str, Any]] = []
    truncated = False
    for sid, text in state.disasm_cache.items():
        meta = state.shader_meta.get(sid, {})
        shader_stages: list[str] = meta.get("stages", [])
        if stage_filter and stage_filter not in shader_stages:
            continue
        lines = text.splitlines()
        for lineno, line in enumerate(lines):
            if compiled.search(line):
                ctx_before = lines[max(0, lineno - context_lines) : lineno]
                ctx_after = lines[lineno + 1 : lineno + 1 + context_lines]
                matches.append(
                    {
                        "shader": sid,
                        "stages": shader_stages,
                        "first_eid": meta.get("first_eid", 0),
                        "line": lineno + 1,
                        "text": line,
                        "context_before": ctx_before,
                        "context_after": ctx_after,
                    }
                )
                if len(matches) >= limit:
                    truncated = True
                    break
        if truncated:
            break
    return _result_response(request_id, {"matches": matches, "truncated": truncated}), True


def _handle_pass_deps(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    from rdc.services.query_service import _build_pass_list, build_pass_deps

    actions = state.adapter.get_root_actions()
    passes = _build_pass_list(actions, state.structured_file)
    usage_data: dict[int, list[Any]] = {}
    for resid, rid_obj in state.res_rid_map.items():
        usage_data[resid] = state.adapter.controller.GetUsage(rid_obj)
    result = build_pass_deps(passes, usage_data)
    return _result_response(request_id, result), True


def _handle_preload(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    _build_shader_cache(state)
    return _result_response(
        request_id,
        {"done": True, "shaders": len(state.disasm_cache)},
    ), True


HANDLERS: dict[str, Handler] = {
    "shader_map": _handle_shader_map,
    "pipeline": _handle_pipeline,
    "bindings": _handle_bindings,
    "shader": _handle_shader,
    "shaders": _handle_shaders,
    "resources": _handle_resources,
    "resource": _handle_resource,
    "passes": _handle_passes,
    "pass": _handle_pass,
    "pass_deps": _handle_pass_deps,
    "log": _handle_log,
    "info": _handle_info,
    "stats": _handle_stats,
    "events": _handle_events,
    "draws": _handle_draws,
    "event": _handle_event,
    "draw": _handle_draw,
    "search": _handle_search,
    "shaders_preload": _handle_preload,
}
