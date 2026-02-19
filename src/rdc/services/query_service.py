"""Query service for action tree traversal and stats aggregation.

Provides helpers for walking the RenderDoc action tree, filtering
events by type/pass/pattern, and aggregating per-pass statistics.
Also includes count and shader-map helpers for rdc count / rdc shader-map.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any


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


# ActionFlags constants (matching mock_renderdoc)
_DRAWCALL = 0x0001
_INDEXED = 0x0002
_DISPATCH = 0x0010
_CLEAR = 0x0020
_COPY = 0x0040
_PASS_BOUNDARY = 0x1000
_BEGIN_PASS = 0x2000
_END_PASS = 0x4000

_VALID_COUNT_TARGETS = frozenset(
    {"draws", "events", "resources", "triangles", "passes", "dispatches", "clears"}
)


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


def flatten_actions(actions: list[Any], sf: Any = None) -> list[FlatAction]:
    """Alias for walk_actions."""
    return walk_actions(actions, sf)


def filter_by_type(flat: list[FlatAction], action_type: str) -> list[FlatAction]:
    """Filter flattened actions by type string (draw/dispatch/clear/copy)."""
    type_map = {"draw": _DRAWCALL, "dispatch": _DISPATCH, "clear": _CLEAR, "copy": _COPY}
    flag = type_map.get(action_type.lower())
    if flag is None:
        return []
    return [a for a in flat if a.flags & flag]


def filter_by_pass(flat: list[FlatAction], pass_name: str) -> list[FlatAction]:
    """Filter flattened actions by pass name (case-insensitive)."""
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
    count = 0
    for a in actions:
        if int(a.flags) & _BEGIN_PASS:
            count += 1
        if a.children:
            count += _count_passes(a.children)
    return count


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
    """Build EID -> shader ID mapping table.

    Args:
        actions: Root action list.
        pipe_states: Dict mapping eid to pipeline state object.

    Returns:
        List of dicts with keys: eid, vs, ps, cs.
    """
    flat = walk_actions(actions)
    draws = [a for a in flat if a.flags & (_DRAWCALL | _DISPATCH)]
    rows = []

    for a in draws:
        state = pipe_states.get(a.eid)
        if state is None:
            continue

        def _shader_id(stage: int, _state: Any = state) -> Any:
            try:
                rid = _state.GetShader(stage)
                if rid is None or (hasattr(rid, "value") and rid.value == 0):
                    return "-"
                if hasattr(rid, "value"):
                    return rid.value
                return rid
            except Exception:
                return "-"

        rows.append(
            {
                "eid": a.eid,
                "vs": _shader_id(0),
                "hs": _shader_id(1),
                "ds": _shader_id(2),
                "gs": _shader_id(3),
                "ps": _shader_id(4),
                "cs": _shader_id(5),
            }
        )

    return rows
