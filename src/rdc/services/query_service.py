"""Query service for count and shader-map aggregation."""

from __future__ import annotations

from typing import Any

_VALID_COUNT_TARGETS = frozenset(
    {"draws", "events", "resources", "triangles", "passes", "dispatches", "clears"}
)

# Flag constants matching renderdoc ActionFlags
_FLAG_DRAWCALL = 0x0001
_FLAG_DISPATCH = 0x0010
_FLAG_CLEAR = 0x0020
_FLAG_BEGIN_PASS = 0x2000
_FLAG_END_PASS = 0x4000


def count_from_actions(
    actions: list[Any],
    what: str,
    *,
    pass_name: str | None = None,
) -> int:
    """Count items from the action tree.

    Args:
        actions: Root action list from controller.GetRootActions().
        what: Target to count (draws, events, triangles, passes, dispatches, clears).
        pass_name: Optional render pass name filter.

    Returns:
        Integer count.

    Raises:
        ValueError: If *what* is not a recognised target.
    """
    if what == "resources":
        msg = "use count_resources() for resource counting"
        raise ValueError(msg)
    if what not in _VALID_COUNT_TARGETS:
        msg = f"unknown count target: {what}"
        raise ValueError(msg)

    counter = _CountWalker()
    counter.walk(actions, pass_name)

    lookup = {
        "draws": counter.draws,
        "events": counter.events,
        "triangles": counter.triangles,
        "passes": counter.passes,
        "dispatches": counter.dispatches,
        "clears": counter.clears,
    }
    return lookup[what]


def count_resources(resources: list[Any]) -> int:
    """Count total resources."""
    return len(resources)


class _CountWalker:
    """Walk an action tree and tally counts."""

    def __init__(self) -> None:
        self.draws = 0
        self.events = 0
        self.triangles = 0
        self.passes = 0
        self.dispatches = 0
        self.clears = 0

    def walk(self, actions: list[Any], pass_name: str | None) -> None:
        self._walk(actions, pass_name, None)

    def _walk(
        self,
        actions: list[Any],
        pass_name: str | None,
        current_pass: str | None,
    ) -> str | None:
        for a in actions:
            self.events += 1
            flags = int(a.flags)

            if flags & _FLAG_BEGIN_PASS:
                current_pass = a.GetName(None)
                self.passes += 1

            in_target = pass_name is None or current_pass == pass_name

            if flags & _FLAG_DRAWCALL and in_target:
                self.draws += 1
                tris = a.numIndices // 3 if a.numIndices else 0
                self.triangles += tris * max(a.numInstances, 1)
            elif flags & _FLAG_DISPATCH and in_target:
                self.dispatches += 1
            elif flags & _FLAG_CLEAR and in_target:
                self.clears += 1

            if a.children:
                current_pass = self._walk(a.children, pass_name, current_pass)

            if flags & _FLAG_END_PASS:
                current_pass = None

        return current_pass


def collect_shader_map(
    actions: list[Any],
    pipe_states: dict[int, Any],
) -> list[dict[str, Any]]:
    """Collect shader-map rows from draw/dispatch actions.

    Args:
        actions: Flat or nested action list.
        pipe_states: Mapping of EID -> PipeState for each draw/dispatch.

    Returns:
        List of dicts with keys: eid, vs, hs, ds, gs, ps, cs.
    """
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
        if (flags & _FLAG_DRAWCALL) or (flags & _FLAG_DISPATCH):
            eid = a.eventId
            state = pipe_states.get(eid)
            if state is not None:
                row: dict[str, Any] = {"eid": eid}
                for stage_val, col in stage_cols.items():
                    sid = state.GetShader(stage_val)
                    if getattr(sid, "value", 0) == 0:
                        row[col] = "-"
                    else:
                        row[col] = sid.value
                rows.append(row)
        if a.children:
            _collect_recursive(a.children, pipe_states, rows)


_STAGE_MAP: dict[str, int] = {"vs": 0, "hs": 1, "ds": 2, "gs": 3, "ps": 4, "cs": 5}


def pipeline_row(
    eid: int,
    api_name: str,
    pipe_state: Any,
    *,
    section: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "eid": eid,
        "api": api_name,
        "topology": str(pipe_state.GetPrimitiveTopology()),
        "graphics_pipeline": _rid(pipe_state.GetGraphicsPipelineObject()),
        "compute_pipeline": _rid(pipe_state.GetComputePipelineObject()),
    }
    if section is not None and section in _STAGE_MAP:
        row["section"] = section
        row["section_detail"] = shader_row(eid, pipe_state, section)
    return row


def bindings_rows(eid: int, pipe_state: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage_name, stage_val in _STAGE_MAP.items():
        refl = pipe_state.GetShaderReflection(stage_val)
        if refl is None:
            continue
        for r in getattr(refl, "readOnlyResources", []):
            rows.append(
                {
                    "eid": eid,
                    "stage": stage_name,
                    "kind": "ro",
                    "slot": r.bindPoint,
                    "name": r.name,
                }
            )
        for r in getattr(refl, "readWriteResources", []):
            rows.append(
                {
                    "eid": eid,
                    "stage": stage_name,
                    "kind": "rw",
                    "slot": r.bindPoint,
                    "name": r.name,
                }
            )
    return rows


def shader_row(eid: int, pipe_state: Any, stage_name: str) -> dict[str, Any]:
    stage_val = _STAGE_MAP[stage_name]
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
    inv: dict[int, dict[str, Any]] = {}
    for _eid, state in pipe_states.items():
        for stage_name, stage_val in _STAGE_MAP.items():
            sid = state.GetShader(stage_val)
            sidv = getattr(sid, "value", 0)
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


def _rid(value: Any) -> int:
    return int(getattr(value, "value", 0))
