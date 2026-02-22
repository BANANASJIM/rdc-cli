"""Query service for action tree traversal and stats aggregation.

Provides helpers for walking the RenderDoc action tree, filtering
events by type/pass/pattern, and aggregating per-pass statistics.
Also includes count, shader-map, pipeline, resource and pass helpers.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any

# ActionFlags constants (matching renderdoc v1.41)
_CLEAR = 0x0001
_DRAWCALL = 0x0002
_DISPATCH = 0x0004
_COPY = 0x0400
_INDEXED = 0x10000
_PUSH_MARKER = 0x0040
_CMD_BUFFER = 0x1000000
_BEGIN_PASS = 0x400000
_END_PASS = 0x800000

STAGE_MAP: dict[str, int] = {"vs": 0, "hs": 1, "ds": 2, "gs": 3, "ps": 4, "cs": 5}

_VALID_COUNT_TARGETS = frozenset(
    {"draws", "events", "resources", "triangles", "passes", "dispatches", "clears"}
)


def _rid(value: Any) -> int:
    """Extract resource ID from a renderdoc object."""
    return int(value)


# ---------------------------------------------------------------------------
# Action tree walking / filtering / stats
# ---------------------------------------------------------------------------


@dataclass
class FlatAction:
    """Flattened action with computed metadata."""

    eid: int
    name: str
    flags: int
    num_indices: int = 0
    num_instances: int = 1
    depth: int = 0
    parent_marker: str = "-"
    pass_name: str = "-"
    events: list[Any] = field(default_factory=list)


@dataclass
class PassStats:
    """Per-pass statistics."""

    name: str
    draws: int = 0
    dispatches: int = 0
    triangles: int = 0
    rt_w: int = 0
    rt_h: int = 0
    attachments: int = 0


@dataclass
class CaptureStats:
    """Aggregated capture statistics."""

    total_draws: int = 0
    indexed_draws: int = 0
    non_indexed_draws: int = 0
    dispatches: int = 0
    clears: int = 0
    copies: int = 0
    barriers: int = 0
    total_triangles: int = 0
    per_pass: list[PassStats] = field(default_factory=list)


def walk_actions(
    actions: list[Any],
    sf: Any = None,
    *,
    depth: int = 0,
    current_pass: str = "-",
    parent_marker: str = "-",
) -> list[FlatAction]:
    """Walk action tree and return flattened list with metadata."""
    result = []
    for a in actions:
        name = a.GetName(sf) if sf is not None else getattr(a, "_name", "")
        flags = int(a.flags)

        if flags & _BEGIN_PASS:
            current_pass = name

        flat = FlatAction(
            eid=a.eventId,
            name=name,
            flags=flags,
            num_indices=a.numIndices,
            num_instances=max(a.numInstances, 1),
            depth=depth,
            parent_marker=parent_marker,
            pass_name=current_pass,
            events=list(a.events) if a.events else [],
        )
        result.append(flat)

        if a.children:
            marker = name if not (flags & _BEGIN_PASS) else parent_marker
            result.extend(
                walk_actions(
                    a.children,
                    sf,
                    depth=depth + 1,
                    current_pass=current_pass,
                    parent_marker=marker,
                )
            )

        if flags & _END_PASS:
            current_pass = "-"

    return result


def filter_by_type(flat: list[FlatAction], action_type: str) -> list[FlatAction]:
    """Filter flattened actions by type string (draw/dispatch/clear/copy)."""
    type_map = {"draw": _DRAWCALL, "dispatch": _DISPATCH, "clear": _CLEAR, "copy": _COPY}
    flag = type_map.get(action_type.lower())
    if flag is None:
        return []
    return [a for a in flat if a.flags & flag]


def filter_by_pass(
    flat: list[FlatAction],
    pass_name: str,
    actions: list[Any] | None = None,
    sf: Any = None,
) -> list[FlatAction]:
    """Filter flattened actions by pass name (case-insensitive).

    When `actions` is provided, uses EID-range matching via `_build_pass_list`
    to support semantic pass names (e.g. 'Colour Pass #1'). Falls back to
    `a.pass_name` string comparison when no pass matches or `actions` is None.
    """
    if actions is not None:
        passes = _build_pass_list(actions, sf)
        target = next((p for p in passes if p["name"].lower() == pass_name.lower()), None)
        if target:
            return [a for a in flat if target["begin_eid"] <= a.eid <= target["end_eid"]]
    lower = pass_name.lower()
    return [a for a in flat if a.pass_name.lower() == lower]


def filter_by_pattern(flat: list[FlatAction], pattern: str) -> list[FlatAction]:
    """Filter flattened actions by name glob pattern."""
    return [a for a in flat if fnmatch.fnmatch(a.name, pattern)]


def find_action_by_eid(actions: list[Any], target_eid: int) -> Any | None:
    """Find an action by event ID in the action tree."""
    for a in actions:
        if a.eventId == target_eid:
            return a
        if a.children:
            found = find_action_by_eid(a.children, target_eid)
            if found is not None:
                return found
    return None


def _triangles_for_action(a: FlatAction) -> int:
    """Compute triangle count for a draw call."""
    if not (a.flags & _DRAWCALL):
        return 0
    return (a.num_indices // 3) * a.num_instances


def aggregate_stats(flat: list[FlatAction]) -> CaptureStats:
    """Aggregate statistics from flattened action list."""
    stats = CaptureStats()
    pass_map: dict[str, PassStats] = {}

    for a in flat:
        if a.flags & _DRAWCALL:
            stats.total_draws += 1
            tris = _triangles_for_action(a)
            stats.total_triangles += tris
            if a.flags & _INDEXED:
                stats.indexed_draws += 1
            else:
                stats.non_indexed_draws += 1
            if a.pass_name != "-":
                ps = pass_map.setdefault(a.pass_name, PassStats(name=a.pass_name))
                ps.draws += 1
                ps.triangles += tris
        elif a.flags & _DISPATCH:
            stats.dispatches += 1
            if a.pass_name != "-":
                ps = pass_map.setdefault(a.pass_name, PassStats(name=a.pass_name))
                ps.dispatches += 1
        elif a.flags & _CLEAR:
            stats.clears += 1
        elif a.flags & _COPY:
            stats.copies += 1

    stats.per_pass = list(pass_map.values())
    return stats


def get_top_draws(flat: list[FlatAction], limit: int = 3) -> list[FlatAction]:
    """Return top draw calls by triangle count."""
    draws = [a for a in flat if a.flags & _DRAWCALL]
    draws.sort(key=_triangles_for_action, reverse=True)
    return draws[:limit]


# ---------------------------------------------------------------------------
# count / shader-map helpers (used by rdc count, rdc shader-map)
# ---------------------------------------------------------------------------


def _count_events_recursive(actions: list[Any]) -> int:
    count = 0
    for a in actions:
        count += 1
        if a.children:
            count += _count_events_recursive(a.children)
    return count


def _count_passes(actions: list[Any]) -> int:
    return len(_build_pass_list(actions))


def count_from_actions(
    actions: list[Any],
    what: str,
    *,
    pass_name: str | None = None,
) -> int:
    """Count items from the action tree.

    Args:
        actions: Root action list from ReplayController.
        what: One of draws, events, triangles, dispatches, clears, passes.
        pass_name: Optional pass filter.

    Raises:
        ValueError: If what is not a recognized target.
    """
    if what not in _VALID_COUNT_TARGETS:
        raise ValueError(
            f"unknown count target {what!r}, expected one of {sorted(_VALID_COUNT_TARGETS)}"
        )

    if what == "events":
        return _count_events_recursive(actions)
    if what == "passes":
        return _count_passes(actions)

    flat = walk_actions(actions)
    if pass_name:
        flat = filter_by_pass(flat, pass_name)

    if what == "draws":
        return len(filter_by_type(flat, "draw"))
    if what == "triangles":
        return sum(_triangles_for_action(a) for a in filter_by_type(flat, "draw"))
    if what == "dispatches":
        return len(filter_by_type(flat, "dispatch"))
    if what == "clears":
        return len(filter_by_type(flat, "clear"))
    return 0


def count_resources(resources: list[Any]) -> int:
    """Count total resources."""
    return len(resources)


def collect_shader_map(
    actions: list[Any],
    pipe_states: dict[int, Any],
) -> list[dict[str, Any]]:
    """Collect shader-map rows from draw/dispatch actions."""
    rows: list[dict[str, Any]] = []
    _collect_recursive(actions, pipe_states, rows)
    return rows


def _collect_recursive(
    actions: list[Any],
    pipe_states: dict[int, Any],
    rows: list[dict[str, Any]],
) -> None:
    stage_cols = {0: "vs", 1: "hs", 2: "ds", 3: "gs", 4: "ps", 5: "cs"}
    for a in actions:
        flags = int(a.flags)
        if (flags & _DRAWCALL) or (flags & _DISPATCH):
            eid = a.eventId
            state = pipe_states.get(eid)
            if state is not None:
                row: dict[str, Any] = {"eid": eid}
                for stage_val, col in stage_cols.items():
                    sid = state.GetShader(stage_val)
                    sid_int = int(sid)
                    if sid_int == 0:
                        row[col] = "-"
                    else:
                        row[col] = sid_int
                rows.append(row)
        if a.children:
            _collect_recursive(a.children, pipe_states, rows)


# ---------------------------------------------------------------------------
# Pipeline / shader helpers (used by daemon pipeline/shader/bindings handlers)
# ---------------------------------------------------------------------------


def pipeline_row(
    eid: int,
    api_name: str,
    pipe_state: Any,
    *,
    section: str | None = None,
) -> dict[str, Any]:
    """Get pipeline state row for an event."""
    row: dict[str, Any] = {
        "eid": eid,
        "api": api_name,
        "topology": getattr((_topo := pipe_state.GetPrimitiveTopology()), "name", str(_topo)),
        "graphics_pipeline": _rid(pipe_state.GetGraphicsPipelineObject()),
        "compute_pipeline": _rid(pipe_state.GetComputePipelineObject()),
    }
    if section is not None and section in STAGE_MAP:
        row["section"] = section
        row["section_detail"] = shader_row(eid, pipe_state, section)
    return row


def bindings_rows(eid: int, pipe_state: Any) -> list[dict[str, Any]]:
    """Get descriptor binding rows for all shader stages."""
    rows: list[dict[str, Any]] = []
    for stage_name, stage_val in STAGE_MAP.items():
        refl = pipe_state.GetShaderReflection(stage_val)
        if refl is None:
            continue
        for r in getattr(refl, "readOnlyResources", []):
            rows.append(
                {
                    "eid": eid,
                    "stage": stage_name,
                    "kind": "ro",
                    "set": getattr(r, "fixedBindSetOrSpace", 0),
                    "slot": getattr(r, "fixedBindNumber", getattr(r, "bindPoint", 0)),
                    "name": r.name,
                }
            )
        for r in getattr(refl, "readWriteResources", []):
            rows.append(
                {
                    "eid": eid,
                    "stage": stage_name,
                    "kind": "rw",
                    "set": getattr(r, "fixedBindSetOrSpace", 0),
                    "slot": getattr(r, "fixedBindNumber", getattr(r, "bindPoint", 0)),
                    "name": r.name,
                }
            )
    return rows


def shader_row(eid: int, pipe_state: Any, stage_name: str) -> dict[str, Any]:
    """Get shader metadata row for a specific stage."""
    stage_val = STAGE_MAP[stage_name]
    sid = pipe_state.GetShader(stage_val)
    refl = pipe_state.GetShaderReflection(stage_val)
    return {
        "eid": eid,
        "stage": stage_name,
        "shader": _rid(sid),
        "entry": pipe_state.GetShaderEntryPoint(stage_val),
        "ro": len(getattr(refl, "readOnlyResources", [])) if refl else 0,
        "rw": len(getattr(refl, "readWriteResources", [])) if refl else 0,
        "cbuffers": len(getattr(refl, "constantBlocks", [])) if refl else 0,
    }


def shader_inventory(pipe_states: dict[int, Any]) -> list[dict[str, Any]]:
    """Get inventory of unique shaders in the frame."""
    inv: dict[int, dict[str, Any]] = {}
    for _eid, state in pipe_states.items():
        for stage_name, stage_val in STAGE_MAP.items():
            sid = state.GetShader(stage_val)
            sidv = int(sid)
            if sidv == 0:
                continue
            if sidv not in inv:
                inv[sidv] = {"shader": sidv, "stages": set(), "uses": 0}
            inv[sidv]["stages"].add(stage_name)
            inv[sidv]["uses"] += 1

    rows: list[dict[str, Any]] = []
    for sidv in sorted(inv):
        row = inv[sidv]
        rows.append(
            {
                "shader": sidv,
                "stages": ",".join(sorted(row["stages"])),
                "uses": row["uses"],
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Resource helpers (used by daemon resources/resource handlers)
# ---------------------------------------------------------------------------


def _resource_row(r: Any) -> dict[str, Any]:
    t = getattr(r, "type", None)
    return {
        "id": _rid(getattr(r, "resourceId", 0)),
        "name": getattr(r, "name", ""),
        "type": getattr(t, "name", str(t)) if t is not None else "",
    }


def get_resources(adapter: Any) -> list[dict[str, Any]]:
    """Get all resources from the capture."""
    resources = adapter.get_resources()
    return [_resource_row(r) for r in resources]


def get_resource_detail(adapter: Any, resid: int) -> dict[str, Any] | None:
    """Get detailed info for a specific resource."""
    resources = adapter.get_resources()
    for r in resources:
        if _rid(getattr(r, "resourceId", 0)) == resid:
            return _resource_row(r)
    return None


# ---------------------------------------------------------------------------
# Pass hierarchy (used by daemon passes handler)
# ---------------------------------------------------------------------------


def get_pass_hierarchy(actions: list[Any], sf: Any = None) -> dict[str, Any]:
    """Get render pass hierarchy from actions."""
    enriched = _build_pass_list(actions, sf)
    return {"passes": [{"name": p["name"], "draws": p["draws"]} for p in enriched]}


def _subtree_has_draws(action: Any) -> bool:
    if int(action.flags) & _DRAWCALL:
        return True
    for c in action.children:
        if _subtree_has_draws(c):
            return True
    return False


def _window_stats(begin: Any, window: list[Any], sf: Any = None) -> dict[str, Any]:
    """Aggregate stats for a render pass window (begin node + flat sibling list)."""
    name = begin.GetName(sf) if sf is not None else getattr(begin, "_name", "")
    draws = dispatches = triangles = 0
    eids = [begin.eventId] + [w.eventId for w in window]
    min_eid, max_eid = min(eids), max(eids)

    def _walk(a: Any) -> None:
        nonlocal draws, dispatches, triangles, min_eid, max_eid
        flags = int(a.flags)
        min_eid = min(min_eid, a.eventId)
        max_eid = max(max_eid, a.eventId)
        if flags & _DRAWCALL:
            draws += 1
            triangles += (a.numIndices // 3) * max(a.numInstances, 1)
        elif flags & _DISPATCH:
            dispatches += 1
        for c in a.children:
            _walk(c)

    for w in window:
        _walk(w)
    return {
        "name": name,
        "begin_eid": min_eid,
        "end_eid": max_eid,
        "draws": draws,
        "dispatches": dispatches,
        "triangles": triangles,
    }


def _subtree_stats(action: Any, sf: Any = None) -> dict[str, Any]:
    name = action.GetName(sf) if sf is not None else getattr(action, "_name", "")
    draws = 0
    dispatches = 0
    triangles = 0
    min_eid = action.eventId
    max_eid = action.eventId

    def _walk(a: Any) -> None:
        nonlocal draws, dispatches, triangles, min_eid, max_eid
        flags = int(a.flags)
        min_eid = min(min_eid, a.eventId)
        max_eid = max(max_eid, a.eventId)
        if flags & _DRAWCALL:
            draws += 1
            triangles += (a.numIndices // 3) * max(a.numInstances, 1)
        elif flags & _DISPATCH:
            dispatches += 1
        for c in a.children:
            _walk(c)

    _walk(action)
    return {
        "name": name,
        "begin_eid": min_eid,
        "end_eid": max_eid,
        "draws": draws,
        "dispatches": dispatches,
        "triangles": triangles,
    }


def _friendly_pass_name(api_name: str, index: int) -> str:
    """Generate a readable pass name from raw API string when no debug markers exist."""
    color_count = api_name.count("C=")
    has_depth = "D=" in api_name
    parts = []
    if color_count:
        parts.append(f"{color_count} Target{'s' if color_count > 1 else ''}")
    if has_depth:
        parts.append("Depth")
    suffix = f" ({' + '.join(parts)})" if parts else ""
    return f"Colour Pass #{index + 1}{suffix}"


def _build_pass_list(actions: list[Any], sf: Any = None) -> list[dict[str, Any]]:
    """Build enriched pass list with begin/end EID, draws, dispatches, triangles."""
    passes: list[dict[str, Any]] = []
    _build_pass_list_recursive(actions, passes, sf)
    return passes


def _build_pass_list_recursive(
    actions: list[Any],
    passes: list[dict[str, Any]],
    sf: Any = None,
) -> None:
    # Real RenderDoc API: BeginPass node may have children (draws/markers)
    # OR BeginPass/EndPass are flat siblings with content between them.
    # Children take priority; flat-sibling window is the fallback.
    i = 0
    while i < len(actions):
        a = actions[i]
        flags = int(a.flags)
        is_begin = bool(flags & _BEGIN_PASS) and not (flags & (_END_PASS | _CMD_BUFFER))

        if is_begin:
            api_name = a.GetName(sf) if sf is not None else getattr(a, "_name", "")
            if a.children:
                # Children-of-BeginPass: real API and mock tree patterns
                content = a.children
                marker_groups = [
                    c for c in content if (int(c.flags) & _PUSH_MARKER) and _subtree_has_draws(c)
                ]
                if marker_groups:
                    for g in marker_groups:
                        passes.append(_subtree_stats(g, sf))
                elif any(_subtree_has_draws(c) for c in content):
                    entry = _subtree_stats(a, sf)
                    if "(" in api_name:
                        entry["name"] = _friendly_pass_name(api_name, len(passes))
                    passes.append(entry)
                i += 1
            else:
                # Flat-sibling: collect window between BeginPass and EndPass
                window: list[Any] = []
                j = i + 1
                while j < len(actions):
                    if int(actions[j].flags) & _END_PASS:
                        break
                    window.append(actions[j])
                    j += 1
                marker_groups = [
                    c for c in window if (int(c.flags) & _PUSH_MARKER) and _subtree_has_draws(c)
                ]
                if marker_groups:
                    for g in marker_groups:
                        passes.append(_subtree_stats(g, sf))
                elif any(_subtree_has_draws(c) for c in window):
                    entry = _window_stats(a, window, sf)
                    if "(" in api_name:
                        entry["name"] = _friendly_pass_name(api_name, len(passes))
                    passes.append(entry)
                i = j
        elif a.children:
            _build_pass_list_recursive(a.children, passes, sf)
            i += 1
        else:
            i += 1


def get_pass_detail(
    actions: list[Any],
    sf: Any = None,
    identifier: int | str = 0,
) -> dict[str, Any] | None:
    """Get detail for a single pass by index (int) or name (str)."""
    passes = _build_pass_list(actions, sf)
    if isinstance(identifier, int):
        return passes[identifier] if 0 <= identifier < len(passes) else None
    lower = identifier.lower()
    for p in passes:
        if p["name"].lower() == lower:
            return p
    return None
