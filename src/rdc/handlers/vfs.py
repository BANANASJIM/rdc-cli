"""VFS handlers: vfs_ls, vfs_tree."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    _build_shader_cache,
    _ensure_shader_populated,
    _error_response,
    _resolve_vfs_path,
    _result_response,
)

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _handle_vfs_ls(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    path = str(params.get("path", "/"))
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

    parent = path.rstrip("/")
    children = []
    for c in node.children:
        child_path = f"{parent}/{c}" if parent != "/" else f"/{c}"
        child_node = state.vfs_tree.static.get(child_path)
        children.append({"name": c, "kind": child_node.kind if child_node else "dir"})

    result = {"path": path, "kind": node.kind, "children": children}
    return _result_response(request_id, result), True


def _handle_vfs_tree(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
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

    return _result_response(request_id, {"path": path, "tree": _subtree(path, depth)}), True


HANDLERS: dict[str, Any] = {
    "vfs_ls": _handle_vfs_ls,
    "vfs_tree": _handle_vfs_tree,
}
