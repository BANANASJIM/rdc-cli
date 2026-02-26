"""Tests for _complete_vfs_path shell completion callback and command wiring."""

from __future__ import annotations

import click
from click.shell_completion import CompletionItem

import rdc.commands.vfs as vfs_mod
from rdc.commands.vfs import _complete_vfs_path, cat_cmd, ls_cmd, tree_cmd

_ROOT_CHILDREN = [
    {"name": "info", "kind": "leaf"},
    {"name": "draws", "kind": "dir"},
    {"name": "events", "kind": "dir"},
    {"name": "stats", "kind": "leaf"},
]

_DRAWS_CHILDREN = [
    {"name": "140", "kind": "dir"},
    {"name": "141", "kind": "dir"},
    {"name": "142", "kind": "dir"},
    {"name": "200", "kind": "dir"},
]

_DRAW_142_CHILDREN = [
    {"name": "shader", "kind": "dir"},
    {"name": "pipeline", "kind": "dir"},
    {"name": "descriptors", "kind": "leaf"},
]


def _patch(monkeypatch, children: list[dict]) -> None:
    monkeypatch.setattr(vfs_mod, "call", lambda method, params=None: {"children": children})


def _values(items: list[CompletionItem]) -> list[str]:
    return [item.value for item in items]


# ── _complete_vfs_path callback ──────────────────────────────────────


def test_complete_root_partial(monkeypatch) -> None:
    _patch(monkeypatch, _ROOT_CHILDREN)
    result = _complete_vfs_path(ctx=None, param=None, incomplete="/d")
    assert any(item.value == "/draws" and item.type == "dir" for item in result)
    values = _values(result)
    assert "/info" not in values


def test_complete_root_empty(monkeypatch) -> None:
    _patch(monkeypatch, _ROOT_CHILDREN)
    result = _complete_vfs_path(ctx=None, param=None, incomplete="")
    assert any(item.value == "/draws" and item.type == "dir" for item in result)
    assert any(item.value == "/events" and item.type == "dir" for item in result)
    values = _values(result)
    assert "/info" in values
    assert "/stats" in values


def test_complete_nested_dir(monkeypatch) -> None:
    called_with: list[dict] = []

    def fake_call(method: str, params: dict | None = None) -> dict:
        if params:
            called_with.append(params)
        return {"children": _DRAWS_CHILDREN}

    monkeypatch.setattr(vfs_mod, "call", fake_call)
    result = _complete_vfs_path(ctx=None, param=None, incomplete="/draws/")
    assert called_with[0]["path"] == "/draws"
    values = _values(result)
    assert "/draws/142" in values
    assert "/draws/140" in values


def test_complete_nested_partial(monkeypatch) -> None:
    _patch(monkeypatch, _DRAWS_CHILDREN)
    result = _complete_vfs_path(ctx=None, param=None, incomplete="/draws/14")
    values = _values(result)
    assert "/draws/140" in values
    assert "/draws/141" in values
    assert "/draws/142" in values
    assert "/draws/200" not in values


def test_complete_leaf_no_slash(monkeypatch) -> None:
    children = [
        {"name": "descriptors", "kind": "leaf"},
        {"name": "binary_buf", "kind": "leaf_bin"},
        {"name": "shader", "kind": "dir"},
    ]
    _patch(monkeypatch, children)
    result = _complete_vfs_path(ctx=None, param=None, incomplete="/draws/142/")
    values = _values(result)
    assert "/draws/142/descriptors" in values
    assert "/draws/142/binary_buf" in values
    assert "/draws/142/shader" in values
    assert any(item.value == "/draws/142/shader" and item.type == "dir" for item in result)


def test_complete_deep_path(monkeypatch) -> None:
    _patch(monkeypatch, _DRAW_142_CHILDREN)
    result = _complete_vfs_path(ctx=None, param=None, incomplete="/draws/142/sh")
    values = _values(result)
    assert "/draws/142/shader" in values
    assert "/draws/142/pipeline" not in values


def test_complete_alias_treated_as_directory(monkeypatch) -> None:
    _patch(monkeypatch, [{"name": "current", "kind": "alias"}])
    result = _complete_vfs_path(ctx=None, param=None, incomplete="/c")
    assert any(item.value == "/current" and item.type == "dir" for item in result)


def test_complete_no_session(monkeypatch) -> None:
    def fake_call(method: str, params: dict | None = None) -> dict:
        raise SystemExit(1)

    monkeypatch.setattr(vfs_mod, "call", fake_call)
    result = _complete_vfs_path(ctx=None, param=None, incomplete="/d")
    assert result == []


def test_complete_no_session_silent(monkeypatch, capsys) -> None:
    def fake_call(method: str, params: dict | None = None) -> dict:
        click.echo("error: no active session (run 'rdc open' first)", err=True)
        raise SystemExit(1)

    monkeypatch.setattr(vfs_mod, "call", fake_call)
    result = _complete_vfs_path(ctx=None, param=None, incomplete="/d")
    assert result == []
    assert capsys.readouterr().err == ""


def test_complete_no_matches(monkeypatch) -> None:
    _patch(monkeypatch, _ROOT_CHILDREN)
    result = _complete_vfs_path(ctx=None, param=None, incomplete="/xyz")
    assert result == []


# ── argument wiring ──────────────────────────────────────────────────


def _path_param(cmd):
    return next(p for p in cmd.params if p.name == "path")


def test_ls_cmd_has_shell_complete() -> None:
    assert _path_param(ls_cmd).shell_complete is not None


def test_cat_cmd_has_shell_complete() -> None:
    assert _path_param(cat_cmd).shell_complete is not None


def test_tree_cmd_has_shell_complete() -> None:
    assert _path_param(tree_cmd).shell_complete is not None
