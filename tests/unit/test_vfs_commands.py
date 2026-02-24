"""Tests for rdc ls/cat/tree/_complete CLI commands."""

from __future__ import annotations

import json

from click.testing import CliRunner

import rdc.commands.vfs as vfs_mod
from rdc.commands.vfs import cat_cmd, complete_cmd, ls_cmd, tree_cmd
from rdc.vfs.router import PathMatch


def _patch(monkeypatch, responses: dict):
    """Patch call to return different responses based on method name."""

    def fake_call(method, params=None):
        return responses.get(method, {})

    monkeypatch.setattr(vfs_mod, "call", fake_call)


def _patch_no_session(monkeypatch):
    """Patch call to simulate no active session."""

    def fake_call(method, params=None):
        from click import echo

        echo("error: no active session", err=True)
        raise SystemExit(1)

    monkeypatch.setattr(vfs_mod, "call", fake_call)


# ── ls ──────────────────────────────────────────────────────────────


def test_ls_root(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {
                "path": "/",
                "kind": "dir",
                "children": [
                    {"name": "info", "kind": "leaf"},
                    {"name": "draws", "kind": "dir"},
                    {"name": "events", "kind": "dir"},
                    {"name": "current", "kind": "alias"},
                ],
            },
        },
    )
    result = CliRunner().invoke(ls_cmd, ["/"])
    assert result.exit_code == 0
    assert "info" in result.output
    assert "draws" in result.output


def test_ls_classify(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {
                "path": "/",
                "kind": "dir",
                "children": [
                    {"name": "info", "kind": "leaf"},
                    {"name": "draws", "kind": "dir"},
                    {"name": "current", "kind": "alias"},
                    {"name": "binary", "kind": "leaf_bin"},
                ],
            },
        },
    )
    result = CliRunner().invoke(ls_cmd, ["-F", "/"])
    assert result.exit_code == 0
    assert "draws/" in result.output
    assert "current@" in result.output
    lines = result.output.strip().split("\n")
    info_line = [x for x in lines if x.startswith("info")][0]
    assert info_line == "info"


def test_ls_json(monkeypatch) -> None:
    children = [
        {"name": "info", "kind": "leaf"},
        {"name": "draws", "kind": "dir"},
    ]
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/", "kind": "dir", "children": children},
        },
    )
    result = CliRunner().invoke(ls_cmd, ["--json", "/"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
    assert len(parsed) == 2


def test_ls_not_a_directory(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/info", "kind": "leaf", "children": []},
        },
    )
    result = CliRunner().invoke(ls_cmd, ["/info"])
    assert result.exit_code == 1
    assert "Not a directory" in result.output


def test_ls_no_session(monkeypatch) -> None:
    _patch_no_session(monkeypatch)
    result = CliRunner().invoke(ls_cmd, ["/"])
    assert result.exit_code == 1
    assert "no active session" in result.output


# ── cat ─────────────────────────────────────────────────────────────


def test_cat_info(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/info", "kind": "leaf", "children": []},
            "info": {"capture": "test.rdc", "api": "Vulkan", "event_count": 1000},
        },
    )
    monkeypatch.setattr(
        vfs_mod,
        "resolve_path",
        lambda p: PathMatch(kind="leaf", handler="info", args={}),
    )
    result = CliRunner().invoke(cat_cmd, ["/info"])
    assert result.exit_code == 0
    assert "Vulkan" in result.output
    assert "capture:" in result.output


def test_cat_shader_disasm(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/draws/142/shader/ps/disasm", "kind": "leaf", "children": []},
            "shader_disasm": {"disasm": "; SPIR-V\n; disassembly output"},
        },
    )
    monkeypatch.setattr(
        vfs_mod,
        "resolve_path",
        lambda p: PathMatch(kind="leaf", handler="shader_disasm", args={"eid": 142, "stage": "ps"}),
    )
    result = CliRunner().invoke(cat_cmd, ["/draws/142/shader/ps/disasm"])
    assert result.exit_code == 0
    assert "SPIR-V" in result.output


def test_cat_json(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/info", "kind": "leaf", "children": []},
            "info": {"capture": "test.rdc", "api": "Vulkan"},
        },
    )
    monkeypatch.setattr(
        vfs_mod,
        "resolve_path",
        lambda p: PathMatch(kind="leaf", handler="info", args={}),
    )
    result = CliRunner().invoke(cat_cmd, ["--json", "/info"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["api"] == "Vulkan"


def test_cat_directory_error(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/draws/142/shader", "kind": "dir", "children": []},
        },
    )
    result = CliRunner().invoke(cat_cmd, ["/draws/142/shader"])
    assert result.exit_code == 1
    assert "Is a directory" in result.output


def test_cat_alias_error(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/current", "kind": "alias", "children": []},
        },
    )
    result = CliRunner().invoke(cat_cmd, ["/current"])
    assert result.exit_code == 1
    assert "no event selected" in result.output


def test_cat_no_handler(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/nonexistent", "kind": "leaf", "children": []},
        },
    )
    monkeypatch.setattr(vfs_mod, "resolve_path", lambda p: None)
    result = CliRunner().invoke(cat_cmd, ["/nonexistent"])
    assert result.exit_code == 1
    assert "no content handler" in result.output


def test_cat_resource(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/resources/1/info", "kind": "leaf", "children": []},
            "resource": {"resource": {"id": 1, "type": "Texture2D", "name": "Albedo"}},
        },
    )
    monkeypatch.setattr(
        vfs_mod,
        "resolve_path",
        lambda p: PathMatch(kind="leaf", handler="resource", args={"id": 1}),
    )
    result = CliRunner().invoke(cat_cmd, ["/resources/1/info"])
    assert result.exit_code == 0
    assert "Albedo" in result.output


def test_cat_pipeline(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/draws/10/pipeline/summary", "kind": "leaf", "children": []},
            "pipeline": {"row": {"stage": "VS", "shader_id": 5}},
        },
    )
    monkeypatch.setattr(
        vfs_mod,
        "resolve_path",
        lambda p: PathMatch(kind="leaf", handler="pipeline", args={"eid": 10, "section": None}),
    )
    result = CliRunner().invoke(cat_cmd, ["/draws/10/pipeline/summary"])
    assert result.exit_code == 0
    assert "VS" in result.output


def test_cat_log(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/log", "kind": "leaf", "children": []},
            "log": {
                "messages": [
                    {"level": "HIGH", "eid": 0, "message": "validation error"},
                ]
            },
        },
    )
    monkeypatch.setattr(
        vfs_mod,
        "resolve_path",
        lambda p: PathMatch(kind="leaf", handler="log", args={}),
    )
    result = CliRunner().invoke(cat_cmd, ["/log"])
    assert result.exit_code == 0
    assert "HIGH" in result.output
    assert "validation error" in result.output


def test_cat_shader_source(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/draws/10/shader/ps/source", "kind": "leaf", "children": []},
            "shader_source": {"source": "void main() {}"},
        },
    )
    monkeypatch.setattr(
        vfs_mod,
        "resolve_path",
        lambda p: PathMatch(kind="leaf", handler="shader_source", args={"eid": 10, "stage": "ps"}),
    )
    result = CliRunner().invoke(cat_cmd, ["/draws/10/shader/ps/source"])
    assert result.exit_code == 0
    assert "void main()" in result.output


def test_cat_descriptors(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/draws/5/descriptors", "kind": "leaf", "children": []},
            "descriptors": {
                "eid": 5,
                "descriptors": [
                    {
                        "stage": "Vertex",
                        "type": "ConstantBuffer",
                        "index": 0,
                        "array_element": 0,
                        "resource_id": 42,
                        "format": "",
                        "byte_size": 256,
                    },
                    {
                        "stage": "Pixel",
                        "type": "ConstantBuffer",
                        "index": 0,
                        "array_element": 0,
                        "resource_id": 43,
                        "format": "",
                        "byte_size": 128,
                    },
                ],
            },
        },
    )
    monkeypatch.setattr(
        vfs_mod,
        "resolve_path",
        lambda p: PathMatch(kind="leaf", handler="descriptors", args={"eid": 5}),
    )
    result = CliRunner().invoke(cat_cmd, ["/draws/5/descriptors"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "STAGE\tTYPE\tINDEX\tARRAY_EL\tRESOURCE\tFORMAT\tBYTE_SIZE"
    assert len(lines) == 3
    assert "Vertex\tConstantBuffer\t0\t0\t42\t\t256" in lines[1]


def test_cat_descriptors_empty(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {"path": "/draws/0/descriptors", "kind": "leaf", "children": []},
            "descriptors": {"eid": 0, "descriptors": []},
        },
    )
    monkeypatch.setattr(
        vfs_mod,
        "resolve_path",
        lambda p: PathMatch(kind="leaf", handler="descriptors", args={"eid": 0}),
    )
    result = CliRunner().invoke(cat_cmd, ["/draws/0/descriptors"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "STAGE\tTYPE\tINDEX\tARRAY_EL\tRESOURCE\tFORMAT\tBYTE_SIZE"
    assert len(lines) == 1


# ── tree ────────────────────────────────────────────────────────────


def test_tree_root(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_tree": {
                "tree": {
                    "name": "",
                    "kind": "dir",
                    "children": [
                        {"name": "info", "kind": "leaf"},
                        {"name": "draws", "kind": "dir", "children": []},
                    ],
                },
            },
        },
    )
    result = CliRunner().invoke(tree_cmd, ["/", "--depth", "1"])
    assert result.exit_code == 0
    assert "\u251c\u2500\u2500" in result.output or "\u2514\u2500\u2500" in result.output


def test_tree_json(monkeypatch) -> None:
    tree_data = {
        "tree": {
            "name": "",
            "kind": "dir",
            "children": [{"name": "info", "kind": "leaf"}],
        },
    }
    _patch(monkeypatch, {"vfs_tree": tree_data})
    result = CliRunner().invoke(tree_cmd, ["--json", "/"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "tree" in parsed


def test_tree_no_session(monkeypatch) -> None:
    _patch_no_session(monkeypatch)
    result = CliRunner().invoke(tree_cmd, ["/"])
    assert result.exit_code == 1
    assert "no active session" in result.output


# ── _complete ───────────────────────────────────────────────────────


def test_complete_filter(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {
                "path": "/draws",
                "kind": "dir",
                "children": [
                    {"name": "140", "kind": "dir"},
                    {"name": "141", "kind": "dir"},
                    {"name": "142", "kind": "dir"},
                    {"name": "200", "kind": "dir"},
                ],
            },
        },
    )
    result = CliRunner().invoke(complete_cmd, ["/draws/14"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert len(lines) == 3
    assert "/draws/140/" in lines
    assert "/draws/141/" in lines
    assert "/draws/142/" in lines


def test_complete_root(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {
                "path": "/",
                "kind": "dir",
                "children": [
                    {"name": "info", "kind": "leaf"},
                    {"name": "draws", "kind": "dir"},
                    {"name": "events", "kind": "dir"},
                ],
            },
        },
    )
    result = CliRunner().invoke(complete_cmd, ["/"])
    assert result.exit_code == 0
    assert "/info" in result.output
    assert "/draws/" in result.output
    assert "/events/" in result.output


def test_complete_daemon_unreachable(monkeypatch) -> None:
    def fake_call(method, params=None):
        raise SystemExit(1)

    monkeypatch.setattr(vfs_mod, "call", fake_call)
    result = CliRunner().invoke(complete_cmd, ["/draws/14"])
    assert result.exit_code == 0
    assert result.output == ""


# ── ls -l (long format) ───────────────────────────────────────────


def _patch_long(monkeypatch, response: dict):
    """Patch call; return response for vfs_ls regardless of params."""

    def fake_call(method, params=None):
        if method == "vfs_ls":
            return response
        return {}

    monkeypatch.setattr(vfs_mod, "call", fake_call)


_LONG_PASSES_RESPONSE = {
    "path": "/passes",
    "kind": "dir",
    "long": True,
    "columns": ["NAME", "DRAWS", "DISPATCHES", "TRIANGLES"],
    "children": [
        {"name": "Shadow", "kind": "dir", "draws": 10, "dispatches": 0, "triangles": 5000},
        {"name": "GBuffer", "kind": "dir", "draws": 25, "dispatches": 3, "triangles": 80000},
    ],
}


def test_ls_long_calls_rpc_with_long_true(monkeypatch) -> None:
    """Verify -l flag sends long=True in RPC params."""
    captured_params = {}

    def fake_call(method, params=None):
        if method == "vfs_ls":
            captured_params.update(params or {})
            return _LONG_PASSES_RESPONSE
        return {}

    monkeypatch.setattr(vfs_mod, "call", fake_call)
    CliRunner().invoke(ls_cmd, ["-l", "/passes"])
    assert captured_params.get("long") is True


def test_ls_long_renders_tsv_header(monkeypatch) -> None:
    _patch_long(monkeypatch, _LONG_PASSES_RESPONSE)
    result = CliRunner().invoke(ls_cmd, ["-l", "/passes"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "NAME\tDRAWS\tDISPATCHES\tTRIANGLES"


def test_ls_long_renders_tsv_rows(monkeypatch) -> None:
    _patch_long(monkeypatch, _LONG_PASSES_RESPONSE)
    result = CliRunner().invoke(ls_cmd, ["-l", "/passes"])
    lines = result.output.strip().split("\n")
    assert len(lines) == 3
    assert lines[1] == "Shadow\t10\t0\t5000"
    assert lines[2] == "GBuffer\t25\t3\t80000"


def test_ls_long_missing_value_renders_dash(monkeypatch) -> None:
    resp = {
        "path": "/draws",
        "kind": "dir",
        "long": True,
        "columns": ["EID", "NAME", "TYPE", "TRIANGLES", "INSTANCES"],
        "children": [
            {"name": "42", "kind": "dir", "eid": 42, "type": "DrawIndexed"},
        ],
    }
    _patch_long(monkeypatch, resp)
    result = CliRunner().invoke(ls_cmd, ["-l", "/draws"])
    lines = result.output.strip().split("\n")
    row = lines[1].split("\t")
    assert row[3] == "-"
    assert row[4] == "-"


def test_ls_long_json_emits_full_response(monkeypatch) -> None:
    _patch_long(monkeypatch, _LONG_PASSES_RESPONSE)
    result = CliRunner().invoke(ls_cmd, ["-l", "--json", "/passes"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "columns" in parsed
    assert parsed["long"] is True
    assert len(parsed["children"]) == 2


def test_ls_long_classify_mutex(monkeypatch) -> None:
    _patch_long(monkeypatch, _LONG_PASSES_RESPONSE)
    result = CliRunner().invoke(ls_cmd, ["-l", "-F", "/passes"])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output


def test_ls_long_empty_directory(monkeypatch) -> None:
    resp = {
        "path": "/passes",
        "kind": "dir",
        "long": True,
        "columns": ["NAME", "DRAWS", "DISPATCHES", "TRIANGLES"],
        "children": [],
    }
    _patch_long(monkeypatch, resp)
    result = CliRunner().invoke(ls_cmd, ["-l", "/passes"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert len(lines) == 1
    assert lines[0] == "NAME\tDRAWS\tDISPATCHES\tTRIANGLES"


def test_ls_no_long_default_unchanged(monkeypatch) -> None:
    """Without -l, existing short format still works."""
    _patch(
        monkeypatch,
        {
            "vfs_ls": {
                "path": "/",
                "kind": "dir",
                "children": [
                    {"name": "info", "kind": "leaf"},
                    {"name": "draws", "kind": "dir"},
                ],
            },
        },
    )
    result = CliRunner().invoke(ls_cmd, ["/"])
    assert result.exit_code == 0
    assert "info" in result.output
    assert "draws" in result.output
    assert "\t" not in result.output


# ── ls -l output options ───────────────────────────────────────────


def test_ls_long_no_header(monkeypatch) -> None:
    _patch_long(monkeypatch, _LONG_PASSES_RESPONSE)
    result = CliRunner().invoke(ls_cmd, ["-l", "--no-header", "/passes"])
    assert result.exit_code == 0
    assert "NAME\tDRAWS\tDISPATCHES\tTRIANGLES" not in result.output
    assert "Shadow" in result.output


def test_ls_long_jsonl(monkeypatch) -> None:
    _patch_long(monkeypatch, _LONG_PASSES_RESPONSE)
    result = CliRunner().invoke(ls_cmd, ["-l", "--jsonl", "/passes"])
    assert result.exit_code == 0
    lines = [json.loads(ln) for ln in result.output.strip().splitlines()]
    assert len(lines) == 2
    assert lines[0]["name"] == "Shadow"


def test_ls_long_quiet(monkeypatch) -> None:
    _patch_long(monkeypatch, _LONG_PASSES_RESPONSE)
    result = CliRunner().invoke(ls_cmd, ["-l", "-q", "/passes"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["Shadow", "GBuffer"]


def test_ls_long_options_ignored_without_l(monkeypatch) -> None:
    _patch(
        monkeypatch,
        {
            "vfs_ls": {
                "path": "/",
                "kind": "dir",
                "children": [
                    {"name": "info", "kind": "leaf"},
                    {"name": "draws", "kind": "dir"},
                ],
            },
        },
    )
    result = CliRunner().invoke(ls_cmd, ["--no-header", "/"])
    assert result.exit_code == 0
    assert "info" in result.output
