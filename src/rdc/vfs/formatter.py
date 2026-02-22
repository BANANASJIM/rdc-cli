"""VFS tree formatter for rdc-cli.

Renders ls output and ASCII tree views from VFS node structures.
"""

from __future__ import annotations

from typing import Any

_CLASSIFY: dict[str, str] = {"dir": "/", "leaf_bin": "*", "alias": "@", "leaf": ""}


def render_ls_long(children: list[dict[str, Any]], columns: list[str]) -> str:
    """Render long-format ls output as TSV with header row.

    Args:
        children: List of child dicts with metadata fields.
        columns: Column headers (uppercase); child keys are lowercase.
    """
    header = "\t".join(columns)
    rows: list[str] = [header]
    for child in children:
        vals: list[str] = []
        for col in columns:
            v = child.get(col.lower())
            vals.append(str(v) if v is not None else "-")
        rows.append("\t".join(vals))
    return "\n".join(rows)


def render_ls(children: list[dict[str, str]], *, classify: bool = False) -> str:
    """Render ls output: one name per line, optional -F classification suffix.

    Args:
        children: List of dicts with "name" and "kind" keys.
        classify: Append type suffix (/ for dir, * for binary, @ for alias).
    """
    lines: list[str] = []
    for child in children:
        suffix = _CLASSIFY.get(child["kind"], "") if classify else ""
        lines.append(child["name"] + suffix)
    return "\n".join(lines)


def render_tree_root(path: str, node: dict[str, Any], max_depth: int) -> str:
    """Render complete tree from root label with ASCII art.

    Args:
        path: Display path for the root node (e.g. "/draws/142/").
        node: Tree dict with "name", "kind", and optional "children".
        max_depth: Maximum depth to render (0 = root only).
    """
    suffix = "/" if node.get("kind") == "dir" else ""
    lines = [path + suffix]
    _render_children(node.get("children", []), lines, "", max_depth, 1)
    return "\n".join(lines)


def _render_children(
    children: list[dict[str, Any]],
    lines: list[str],
    prefix: str,
    max_depth: int,
    depth: int,
) -> None:
    if depth > max_depth or not children:
        return
    for i, child in enumerate(children):
        is_last = i == len(children) - 1
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        suffix = _CLASSIFY.get(child.get("kind", "leaf"), "")
        lines.append(prefix + connector + child["name"] + suffix)
        extension = "    " if is_last else "\u2502   "
        _render_children(
            child.get("children", []),
            lines,
            prefix + extension,
            max_depth,
            depth + 1,
        )
