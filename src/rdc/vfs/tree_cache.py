"""VFS tree cache for rdc-cli.

Builds a static virtual filesystem skeleton from capture data and lazily
populates per-draw subtrees (shader stages, bindings) on first access.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from rdc.services.query_service import (
    _DISPATCH,
    _DRAWCALL,
    _STAGE_MAP,
    _build_pass_list,
    walk_actions,
)

_ROOT_CHILDREN = [
    "capabilities",
    "info",
    "stats",
    "log",
    "events",
    "draws",
    "by-marker",
    "passes",
    "resources",
    "textures",
    "buffers",
    "shaders",
    "current",
]

_DRAW_CHILDREN = ["pipeline", "shader", "bindings"]
_PIPELINE_CHILDREN = ["summary"]
_PASS_CHILDREN = ["info", "draws", "attachments"]
_SHADER_STAGE_CHILDREN = ["disasm", "source", "reflect", "constants"]


@dataclass
class VfsNode:
    """Single node in the virtual filesystem tree."""

    name: str
    kind: str  # "dir" | "leaf" | "leaf_bin" | "alias"
    children: list[str] = field(default_factory=list)


@dataclass
class VfsTree:
    """Virtual filesystem tree with LRU-cached draw subtrees."""

    static: dict[str, VfsNode] = field(default_factory=dict)
    pass_name_map: dict[str, str] = field(default_factory=dict)
    _draw_subtrees: OrderedDict[int, dict[str, list[str]]] = field(default_factory=OrderedDict)
    _lru_capacity: int = 64

    def get_draw_subtree(self, eid: int) -> dict[str, list[str]] | None:
        """Return cached draw subtree or None, promoting on access."""
        val = self._draw_subtrees.get(eid)
        if val is not None:
            self._draw_subtrees.move_to_end(eid)
        return val

    def _evict_draw_subtree(self, eid: int) -> None:
        """Remove a draw subtree and its dynamic static nodes."""
        subtree = self._draw_subtrees.get(eid)
        if subtree is None:
            return
        for path, children in subtree.items():
            for child in children:
                child_path = f"{path}/{child}"
                self.static.pop(child_path, None)
            node = self.static.get(path)
            if node is not None:
                node.children = []
        del self._draw_subtrees[eid]

    def set_draw_subtree(self, eid: int, subtree: dict[str, list[str]]) -> None:
        """Cache a draw subtree with LRU eviction."""
        if eid in self._draw_subtrees:
            self._draw_subtrees.move_to_end(eid)
        elif len(self._draw_subtrees) >= self._lru_capacity:
            oldest_eid = next(iter(self._draw_subtrees))
            self._evict_draw_subtree(oldest_eid)
        self._draw_subtrees[eid] = subtree


def build_vfs_skeleton(
    actions: list[Any],
    resources: list[Any],
    sf: Any = None,
) -> VfsTree:
    """Build the static VFS skeleton from capture data.

    Args:
        actions: Root action list from ReplayController.
        resources: Resource list from ReplayController.
        sf: Optional StructuredFile for action name resolution.
    """
    tree = VfsTree()
    flat = walk_actions(actions, sf)

    draw_eids = [str(a.eid) for a in flat if a.flags & (_DRAWCALL | _DISPATCH)]
    event_eids = [str(a.eid) for a in flat]
    pass_list = _build_pass_list(actions, sf)
    pass_names = [p["name"] for p in pass_list]
    resource_ids = [str(int(getattr(r, "resourceId", 0))) for r in resources]

    # Root
    tree.static["/"] = VfsNode("/", "dir", list(_ROOT_CHILDREN))

    # Top-level leaves
    for leaf in ("capabilities", "info", "stats", "log"):
        tree.static[f"/{leaf}"] = VfsNode(leaf, "leaf")

    # /events
    tree.static["/events"] = VfsNode("events", "dir", list(event_eids))
    for eid in event_eids:
        tree.static[f"/events/{eid}"] = VfsNode(eid, "leaf")

    # /draws
    tree.static["/draws"] = VfsNode("draws", "dir", list(draw_eids))
    for eid in draw_eids:
        prefix = f"/draws/{eid}"
        tree.static[prefix] = VfsNode(eid, "dir", list(_DRAW_CHILDREN))
        tree.static[f"{prefix}/pipeline"] = VfsNode("pipeline", "dir", list(_PIPELINE_CHILDREN))
        for child in _PIPELINE_CHILDREN:
            tree.static[f"{prefix}/pipeline/{child}"] = VfsNode(child, "leaf")
        tree.static[f"{prefix}/shader"] = VfsNode("shader", "dir")
        tree.static[f"{prefix}/bindings"] = VfsNode("bindings", "dir")

    # /passes — sanitize names containing "/" to avoid path corruption
    safe_pass_names = [n.replace("/", "_") for n in pass_names]
    for safe, orig in zip(safe_pass_names, pass_names, strict=True):
        if safe != orig:
            tree.pass_name_map[safe] = orig
    tree.static["/passes"] = VfsNode("passes", "dir", list(safe_pass_names))
    for name in safe_pass_names:
        prefix = f"/passes/{name}"
        tree.static[prefix] = VfsNode(name, "dir", list(_PASS_CHILDREN))
        tree.static[f"{prefix}/info"] = VfsNode("info", "leaf")
        tree.static[f"{prefix}/draws"] = VfsNode("draws", "dir")
        tree.static[f"{prefix}/attachments"] = VfsNode("attachments", "dir")

    # /resources
    tree.static["/resources"] = VfsNode("resources", "dir", list(resource_ids))
    for rid in resource_ids:
        tree.static[f"/resources/{rid}"] = VfsNode(rid, "dir", ["info"])
        tree.static[f"/resources/{rid}/info"] = VfsNode("info", "leaf")

    # Placeholder dirs
    for name in ("by-marker", "textures", "buffers", "shaders"):
        tree.static[f"/{name}"] = VfsNode(name, "dir")

    # /current alias
    tree.static["/current"] = VfsNode("current", "alias")

    return tree


def populate_draw_subtree(
    tree: VfsTree,
    eid: int,
    pipe_state: Any,
) -> dict[str, list[str]]:
    """Discover active shader stages and populate draw subtree nodes.

    Args:
        tree: The VFS tree to update.
        eid: Draw event ID.
        pipe_state: Pipeline state object with GetShader().

    Returns:
        Mapping of path -> child names for the populated subtree.
    """
    cached = tree.get_draw_subtree(eid)
    if cached is not None:
        return cached

    stages: list[str] = []
    for stage_name, stage_idx in _STAGE_MAP.items():
        if int(pipe_state.GetShader(stage_idx)) != 0:
            stages.append(stage_name)

    prefix = f"/draws/{eid}"
    subtree: dict[str, list[str]] = {}

    # Update shader node children
    tree.static[f"{prefix}/shader"].children = list(stages)
    subtree[f"{prefix}/shader"] = list(stages)

    for stage in stages:
        stage_path = f"{prefix}/shader/{stage}"
        tree.static[stage_path] = VfsNode(stage, "dir", list(_SHADER_STAGE_CHILDREN))
        subtree[stage_path] = list(_SHADER_STAGE_CHILDREN)

        for child in _SHADER_STAGE_CHILDREN:
            child_path = f"{stage_path}/{child}"
            tree.static[child_path] = VfsNode(child, "leaf")

    tree.set_draw_subtree(eid, subtree)
    return subtree
