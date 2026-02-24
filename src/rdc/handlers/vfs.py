"""VFS handlers: vfs_ls, vfs_tree."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    _action_type_str,
    _build_shader_cache,
    _ensure_shader_populated,
    _error_response,
    _get_flat_actions,
    _resolve_vfs_path,
    _result_response,
)
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState
    from rdc.vfs.tree_cache import VfsNode

# Column definitions per path context
_COLUMNS: dict[str, list[str]] = {
    "passes": ["NAME", "DRAWS", "DISPATCHES", "TRIANGLES"],
    "draws": ["EID", "NAME", "TYPE", "TRIANGLES", "INSTANCES"],
    "events": ["EID", "NAME", "TYPE"],
    "resources": ["ID", "NAME", "TYPE", "SIZE"],
    "textures": ["ID", "NAME", "WIDTH", "HEIGHT", "FORMAT"],
    "buffers": ["ID", "NAME", "LENGTH"],
    "shaders": ["ID", "STAGES", "ENTRY", "INPUTS", "OUTPUTS"],
}
_DEFAULT_COLUMNS = ["NAME", "TYPE"]


def _ls_long_children(
    path: str, node: VfsNode, state: DaemonState
) -> tuple[list[str], list[dict[str, Any]]]:
    """Enrich children with metadata based on path context.

    Returns:
        Tuple of (columns, enriched_children).
    """
    segments = [s for s in path.strip("/").split("/") if s]
    context = segments[0] if segments else ""
    depth = len(segments)

    parent = path.rstrip("/")

    # Context-specific enrichment only at top level (e.g., /draws, /passes)
    if depth == 1 and context in _COLUMNS:
        columns = _COLUMNS[context]
        if context == "passes":
            children = _long_passes(node, state)
        elif context == "draws":
            children = _long_draws(node, parent, state)
        elif context == "events":
            children = _long_events(node, parent, state)
        elif context == "resources":
            children = _long_resources(node, state)
        elif context == "textures":
            children = _long_textures(node, state)
        elif context == "buffers":
            children = _long_buffers(node, state)
        else:  # shaders
            children = _long_shaders(node, state)
    else:
        columns = _DEFAULT_COLUMNS
        children = _long_default(node, parent, state)

    return columns, children


def _long_passes(node: VfsNode, state: DaemonState) -> list[dict[str, Any]]:
    assert state.vfs_tree is not None
    pass_map = {p["name"]: p for p in (state.vfs_tree.pass_list or [])}
    safe_map = state.vfs_tree.pass_name_map
    result: list[dict[str, Any]] = []
    for name in node.children:
        orig = safe_map.get(name, name)
        p = pass_map.get(orig, {})
        result.append(
            {
                "name": name,
                "kind": "dir",
                "draws": p.get("draws", "-"),
                "dispatches": p.get("dispatches", "-"),
                "triangles": p.get("triangles", "-"),
            }
        )
    return result


def _long_draws(node: VfsNode, parent: str, state: DaemonState) -> list[dict[str, Any]]:
    assert state.vfs_tree is not None
    flat = _get_flat_actions(state)
    eid_map = {str(a.eid): a for a in flat}
    result: list[dict[str, Any]] = []
    for name in node.children:
        child_path = f"{parent}/{name}" if parent != "/" else f"/{name}"
        child_node = state.vfs_tree.static.get(child_path)
        a = eid_map.get(name)
        if a:
            triangles = (a.num_indices // 3) * a.num_instances
            result.append(
                {
                    "name": name,
                    "kind": child_node.kind if child_node else "dir",
                    "eid": a.eid,
                    "type": _action_type_str(a.flags),
                    "triangles": triangles,
                    "instances": a.num_instances,
                }
            )
        else:
            result.append(
                {
                    "name": name,
                    "kind": child_node.kind if child_node else "dir",
                    "eid": "-",
                    "type": "-",
                    "triangles": "-",
                    "instances": "-",
                }
            )
    return result


def _long_events(node: VfsNode, parent: str, state: DaemonState) -> list[dict[str, Any]]:
    assert state.vfs_tree is not None
    flat = _get_flat_actions(state)
    eid_map = {str(a.eid): a for a in flat}
    result: list[dict[str, Any]] = []
    for name in node.children:
        child_path = f"{parent}/{name}" if parent != "/" else f"/{name}"
        child_node = state.vfs_tree.static.get(child_path)
        a = eid_map.get(name)
        if a:
            result.append(
                {
                    "name": name,
                    "kind": child_node.kind if child_node else "leaf",
                    "eid": a.eid,
                    "type": _action_type_str(a.flags),
                }
            )
        else:
            result.append(
                {
                    "name": name,
                    "kind": child_node.kind if child_node else "leaf",
                    "eid": "-",
                    "type": "-",
                }
            )
    return result


def _long_resources(node: VfsNode, state: DaemonState) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name in node.children:
        rid_int = int(name) if name.isdigit() else 0
        res_type = state.res_types.get(rid_int, "-")
        rid_obj = state.res_rid_map.get(rid_int)
        size = getattr(rid_obj, "byteSize", "-") if rid_obj else "-"
        result.append(
            {
                "name": name,
                "kind": "dir",
                "id": rid_int,
                "type": res_type,
                "size": size,
            }
        )
    return result


def _long_textures(node: VfsNode, state: DaemonState) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name in node.children:
        rid_int = int(name) if name.isdigit() else 0
        tex = state.tex_map.get(rid_int)
        if tex:
            fmt = getattr(tex, "format", None)
            fmt_name = fmt.Name() if fmt and hasattr(fmt, "Name") else str(fmt) if fmt else "-"
            result.append(
                {
                    "name": name,
                    "kind": "dir",
                    "id": rid_int,
                    "width": getattr(tex, "width", "-"),
                    "height": getattr(tex, "height", "-"),
                    "format": fmt_name,
                }
            )
        else:
            result.append(
                {
                    "name": name,
                    "kind": "dir",
                    "id": rid_int,
                    "width": "-",
                    "height": "-",
                    "format": "-",
                }
            )
    return result


def _long_buffers(node: VfsNode, state: DaemonState) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name in node.children:
        rid_int = int(name) if name.isdigit() else 0
        buf = state.buf_map.get(rid_int)
        length = getattr(buf, "length", "-") if buf else "-"
        result.append(
            {
                "name": name,
                "kind": "dir",
                "id": rid_int,
                "length": length,
            }
        )
    return result


def _long_shaders(node: VfsNode, state: DaemonState) -> list[dict[str, Any]]:
    _build_shader_cache(state)
    result: list[dict[str, Any]] = []
    for name in node.children:
        sid = int(name) if name.isdigit() else 0
        meta = state.shader_meta.get(sid, {})
        stages = ",".join(meta.get("stages", []))
        result.append(
            {
                "name": name,
                "kind": "dir",
                "id": sid,
                "stages": stages or "-",
                "entry": meta.get("entry", "-"),
                "inputs": meta.get("inputs", "-"),
                "outputs": meta.get("outputs", "-"),
            }
        )
    return result


def _long_default(node: VfsNode, parent: str, state: DaemonState) -> list[dict[str, Any]]:
    assert state.vfs_tree is not None
    result: list[dict[str, Any]] = []
    for name in node.children:
        child_path = f"{parent}/{name}" if parent != "/" else f"/{name}"
        child_node = state.vfs_tree.static.get(child_path)
        result.append(
            {
                "name": name,
                "kind": child_node.kind if child_node else "dir",
                "type": child_node.kind if child_node else "dir",
            }
        )
    return result


def _handle_vfs_ls(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    path = str(params.get("path", "/"))
    long = bool(params.get("long", False))
    path, err = _resolve_vfs_path(path, state)
    if err:
        return _error_response(request_id, -32002, err), True

    if state.vfs_tree is None:
        return _error_response(request_id, -32002, "vfs tree not built"), True

    if path.startswith("/shaders") and not state._shader_cache_built:
        _build_shader_cache(state)

    pop_err = _ensure_shader_populated(request_id, path, state)
    if pop_err:
        return pop_err, True

    node = state.vfs_tree.static.get(path)
    if node is None:
        return _error_response(request_id, -32001, f"not found: {path}"), True

    if long and node.kind == "dir":
        columns, children = _ls_long_children(path, node, state)
        result: dict[str, Any] = {
            "path": path,
            "kind": node.kind,
            "long": True,
            "columns": columns,
            "children": children,
        }
    else:
        parent = path.rstrip("/")
        children_list: list[dict[str, Any]] = []
        for c in node.children:
            child_path = f"{parent}/{c}" if parent != "/" else f"/{c}"
            child_node = state.vfs_tree.static.get(child_path)
            children_list.append({"name": c, "kind": child_node.kind if child_node else "dir"})
        result = {"path": path, "kind": node.kind, "children": children_list}

    return _result_response(request_id, result), True


class _VfsPopulateError(Exception):
    """Raised when shader population fails inside recursive _subtree."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response


def _handle_vfs_tree(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    path = str(params.get("path", "/"))
    depth = int(params.get("depth", 2))
    path, err = _resolve_vfs_path(path, state)
    if err:
        return _error_response(request_id, -32002, err), True

    if state.vfs_tree is None:
        return _error_response(request_id, -32002, "vfs tree not built"), True

    if depth < 1 or depth > 8:
        return _error_response(request_id, -32602, "depth must be 1-8"), True

    if path.startswith("/shaders") and not state._shader_cache_built:
        _build_shader_cache(state)

    node = state.vfs_tree.static.get(path)
    if node is None:
        return _error_response(request_id, -32001, f"not found: {path}"), True

    tree = state.vfs_tree

    def _subtree(p: str, d: int) -> dict[str, Any]:
        err = _ensure_shader_populated(request_id, p, state)
        if err is not None:
            raise _VfsPopulateError(err)
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

    try:
        tree_data = _subtree(path, depth)
    except _VfsPopulateError as exc:
        return exc.response, True
    return _result_response(request_id, {"path": path, "tree": tree_data}), True


HANDLERS: dict[str, Handler] = {
    "vfs_ls": _handle_vfs_ls,
    "vfs_tree": _handle_vfs_tree,
}
