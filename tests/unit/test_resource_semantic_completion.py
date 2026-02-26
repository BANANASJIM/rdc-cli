"""Tests for resource-centric semantic shell completions."""

from __future__ import annotations

from click.shell_completion import CompletionItem

import rdc.commands.export as export_mod
import rdc.commands.resources as resources_mod
import rdc.commands.usage as usage_mod
from rdc.commands._helpers import complete_eid
from rdc.commands.export import buffer_cmd, rt_cmd, texture_cmd
from rdc.commands.resources import pass_cmd, resource_cmd, resources_cmd
from rdc.commands.usage import usage_cmd


def _values(items: list[CompletionItem]) -> list[str]:
    return [item.value for item in items]


def _arg(cmd, name: str):
    return next(p for p in cmd.params if p.name == name)


def _opt(cmd, name: str):
    return next(p for p in cmd.params if p.name == name)


def test_resource_command_shell_complete_wiring() -> None:
    assert _arg(resource_cmd, "resid").shell_complete is not None
    assert _arg(pass_cmd, "identifier").shell_complete is not None
    assert _opt(resources_cmd, "type_filter").shell_complete is not None
    assert _opt(resources_cmd, "name_filter").shell_complete is not None


def test_usage_command_shell_complete_wiring() -> None:
    assert _arg(usage_cmd, "resource_id").shell_complete is not None
    assert _opt(usage_cmd, "res_type").shell_complete is not None
    assert _opt(usage_cmd, "usage_filter").shell_complete is not None


def test_export_command_shell_complete_wiring() -> None:
    assert _arg(texture_cmd, "id").shell_complete is not None
    assert _arg(buffer_cmd, "id").shell_complete is not None
    assert _arg(rt_cmd, "eid")._custom_shell_complete is complete_eid
    assert _opt(rt_cmd, "target").shell_complete is not None


def test_resources_completion_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        resources_mod,
        "completion_call",
        lambda method, params: {
            "rows": [
                {"id": 7, "type": "Texture", "name": "Albedo"},
                {"id": 8, "type": "Buffer", "name": "Vertices"},
            ]
        },
    )
    assert _values(resources_mod._complete_resource_id(None, None, "")) == ["7", "8"]
    assert _values(resources_mod._complete_resource_type(None, None, "t")) == ["Texture"]
    assert _values(resources_mod._complete_resource_name(None, None, "a")) == ["Albedo"]


def test_pass_identifier_completion_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        resources_mod,
        "completion_call",
        lambda method, params: {"tree": {"passes": [{"name": "Shadow"}, {"name": "Main"}]}},
    )
    values = _values(resources_mod._complete_pass_identifier(None, None, ""))
    assert "0" in values
    assert "1" in values
    assert "Shadow" in values
    assert "Main" in values


def test_usage_completion_candidates(monkeypatch) -> None:
    def fake_call(method: str, params: dict):
        if method == "resources":
            return {
                "rows": [
                    {"id": 11, "type": "Texture", "name": "Albedo"},
                    {"id": 12, "type": "Buffer", "name": "VB"},
                ]
            }
        return {
            "rows": [
                {"id": 11, "name": "Albedo", "eid": 5, "usage": "ColorTarget"},
                {"id": 12, "name": "VB", "eid": 6, "usage": "VS_Constants"},
            ]
        }

    monkeypatch.setattr(usage_mod, "completion_call", fake_call)
    assert _values(usage_mod._complete_usage_resource_id(None, None, "1")) == ["11", "12"]
    assert _values(usage_mod._complete_usage_resource_type(None, None, "t")) == ["Texture"]
    assert _values(usage_mod._complete_usage_kind(None, None, "c")) == ["ColorTarget"]


def test_export_completion_candidates(monkeypatch) -> None:
    def fake_call(method: str, params: dict):
        if method == "resources":
            return {
                "rows": [
                    {"id": 21, "type": "Texture", "name": "Albedo"},
                    {"id": 22, "type": "Buffer", "name": "VB"},
                ]
            }
        return {
            "children": [
                {"name": "color0.png", "kind": "leaf_bin"},
                {"name": "color2.png", "kind": "leaf_bin"},
            ]
        }

    monkeypatch.setattr(export_mod, "completion_call", fake_call)
    assert _values(export_mod._complete_texture_id(None, None, "")) == ["21"]
    assert _values(export_mod._complete_buffer_id(None, None, "")) == ["22"]

    class _Ctx:
        params = {"eid": 100}

    assert _values(export_mod._complete_rt_target(_Ctx(), None, "")) == ["0", "2"]


def test_resource_completion_errors_return_empty(monkeypatch) -> None:
    monkeypatch.setattr(resources_mod, "completion_call", lambda method, params: None)
    monkeypatch.setattr(usage_mod, "completion_call", lambda method, params: None)
    monkeypatch.setattr(export_mod, "completion_call", lambda method, params: None)

    assert resources_mod._complete_resource_id(None, None, "") == []
    assert resources_mod._complete_pass_identifier(None, None, "") == []
    assert usage_mod._complete_usage_resource_id(None, None, "") == []
    assert usage_mod._complete_usage_kind(None, None, "") == []
    assert export_mod._complete_texture_id(None, None, "") == []


def test_rt_target_completion_defaults_without_eid() -> None:
    class _Ctx:
        params: dict[str, int] = {}

    assert _values(export_mod._complete_rt_target(_Ctx(), None, "1")) == ["1"]


def test_completion_non_numeric_ids_do_not_crash(monkeypatch) -> None:
    def fake_call(method: str, params: dict):
        if method == "resources":
            return {
                "rows": [
                    {"id": "foo", "type": "Texture", "name": "Albedo"},
                    {"id": 10, "type": "Buffer", "name": "VB"},
                    {"id": 2, "type": "Texture", "name": "Mask"},
                ]
            }
        return {"draws": [{"eid": "last"}, {"eid": 20}, {"eid": 5}]}

    monkeypatch.setattr(resources_mod, "completion_call", fake_call)
    monkeypatch.setattr(usage_mod, "completion_call", fake_call)
    monkeypatch.setattr(export_mod, "completion_call", fake_call)

    assert _values(resources_mod._complete_resource_id(None, None, "")) == ["2", "10", "foo"]
    assert _values(usage_mod._complete_usage_resource_id(None, None, "")) == ["2", "10", "foo"]
    assert _values(export_mod._complete_texture_id(None, None, "")) == ["2", "foo"]


def test_completion_malformed_payload_shapes_return_empty_or_filtered(monkeypatch) -> None:
    monkeypatch.setattr(resources_mod, "completion_call", lambda method, params: {"rows": "bad"})
    monkeypatch.setattr(usage_mod, "completion_call", lambda method, params: {"rows": "bad"})

    assert resources_mod._complete_resource_id(None, None, "") == []
    assert resources_mod._complete_resource_type(None, None, "") == []
    assert usage_mod._complete_usage_resource_id(None, None, "") == []
    assert usage_mod._complete_usage_kind(None, None, "") == []

    monkeypatch.setattr(export_mod, "completion_call", lambda method, params: {"draws": "bad"})


def test_completion_malformed_items_are_ignored(monkeypatch) -> None:
    def fake_call(method: str, params: dict):
        if method == "resources":
            return {
                "rows": [
                    {"id": 9, "type": "Texture", "name": "Good"},
                    "bad",
                    123,
                ]
            }
        if method == "passes":
            return {"tree": {"passes": [{"name": "Main"}, "bad"]}}
        if method == "vfs_ls":
            return {
                "children": [
                    {"name": "color1.png", "kind": "leaf_bin"},
                    "bad",
                ]
            }
        return None

    monkeypatch.setattr(resources_mod, "completion_call", fake_call)
    monkeypatch.setattr(export_mod, "completion_call", fake_call)

    class _Ctx:
        params = {"eid": 100}

    assert _values(resources_mod._complete_resource_id(None, None, "")) == ["9"]
    assert _values(resources_mod._complete_pass_identifier(None, None, "")) == ["0", "Main"]
    assert _values(export_mod._complete_rt_target(_Ctx(), None, "")) == ["1"]
