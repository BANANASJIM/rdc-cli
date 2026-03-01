"""Tests for phase2-search: daemon search handler, VFS /shaders/, and CLI command."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import mock_renderdoc as mock_rd
import pytest
from click.testing import CliRunner
from conftest import rpc_request
from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    MockPipeState,
    ResourceDescription,
    ResourceId,
    ShaderReflection,
    ShaderStage,
)

from rdc.adapter import RenderDocAdapter
from rdc.cli import main
from rdc.daemon_server import DaemonState, _build_shader_cache, _handle_request
from rdc.vfs.tree_cache import VfsNode, VfsTree, build_vfs_skeleton, populate_shaders_subtree

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VS_DISASM = (
    "; Vertex Shader\nOpCapability Shader\n%pos = OpLoad %v4float %in_pos\nOpStore %out_pos %pos\n"
)
_PS_DISASM = (
    "; Pixel Shader\n"
    "OpCapability Shader\n"
    "%color = OpLoad %v4float %in_color\n"
    "%result = OpFMul %float %a %b\n"
    "OpStore %out_color %result\n"
)


def _build_pipe(vs_id: int, ps_id: int) -> MockPipeState:
    pipe = MockPipeState()
    pipe._shaders[ShaderStage.Vertex] = ResourceId(vs_id)
    pipe._shaders[ShaderStage.Pixel] = ResourceId(ps_id)
    vs_refl = ShaderReflection(resourceId=ResourceId(vs_id), stage=ShaderStage.Vertex)
    ps_refl = ShaderReflection(resourceId=ResourceId(ps_id), stage=ShaderStage.Pixel)
    pipe._reflections[ShaderStage.Vertex] = vs_refl
    pipe._reflections[ShaderStage.Pixel] = ps_refl
    return pipe


@pytest.fixture()
def controller() -> mock_rd.MockReplayController:
    ctrl = mock_rd.MockReplayController()
    ctrl._disasm_text = {100: _VS_DISASM, 200: _PS_DISASM}
    ctrl._pipe_state = _build_pipe(vs_id=100, ps_id=200)

    actions = [
        ActionDescription(eventId=10, flags=ActionFlags.Drawcall, numIndices=3, _name="Draw"),
    ]
    ctrl._actions = actions
    ctrl._resources = [ResourceDescription(resourceId=ResourceId(1), name="res0")]
    return ctrl


@pytest.fixture()
def state(controller: mock_rd.MockReplayController, tmp_path: Path) -> DaemonState:
    actions = controller._actions
    resources = controller._resources

    ns = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: resources,
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: SimpleNamespace(chunks=[]),
        GetPipelineState=lambda: controller._pipe_state,
        GetTextures=lambda: [],
        GetBuffers=lambda: [],
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
        DisassembleShader=controller.DisassembleShader,
        GetDisassemblyTargets=lambda _with_pipeline: ["SPIR-V"],
    )

    s = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    s.adapter = RenderDocAdapter(controller=ns, version=(1, 41))
    s.max_eid = 10
    s.rd = mock_rd
    s.temp_dir = tmp_path
    s.vfs_tree = build_vfs_skeleton(actions, resources)
    return s


# ---------------------------------------------------------------------------
# Tests: _build_shader_cache
# ---------------------------------------------------------------------------


class TestBuildShaderCache:
    def test_populates_disasm_cache(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        assert 100 in state.disasm_cache
        assert 200 in state.disasm_cache
        assert "Vertex Shader" in state.disasm_cache[100]
        assert "Pixel Shader" in state.disasm_cache[200]

    def test_populates_shader_meta(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        assert 100 in state.shader_meta
        assert 200 in state.shader_meta
        assert "vs" in state.shader_meta[100]["stages"]
        assert "ps" in state.shader_meta[200]["stages"]

    def test_no_rebuild_on_second_call(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        original = dict(state.disasm_cache)
        state.disasm_cache[100] = "mutated"
        _build_shader_cache(state)
        # Should not rebuild — sentinel value persists
        assert state.disasm_cache[100] == "mutated"
        _ = original  # used

    def test_no_adapter_is_noop(self) -> None:
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        _build_shader_cache(s)
        assert s.disasm_cache == {}
        assert s.shader_meta == {}

    def test_populates_vfs_shaders_subtree(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        assert state.vfs_tree is not None
        assert state.vfs_tree.static.get("/shaders") is not None
        children = state.vfs_tree.static["/shaders"].children
        assert "100" in children
        assert "200" in children


# ---------------------------------------------------------------------------
# Tests: search handler
# ---------------------------------------------------------------------------


class TestSearchHandler:
    def test_basic_match(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("search", {"pattern": "OpCapability"}, token="abcdef1234567890"), state
        )
        matches = resp["result"]["matches"]
        assert len(matches) >= 2

    def test_case_insensitive_default(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("search", {"pattern": "opcapability"}, token="abcdef1234567890"), state
        )
        matches = resp["result"]["matches"]
        assert len(matches) >= 2

    def test_case_sensitive(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request(
                "search",
                {"pattern": "opcapability", "case_sensitive": True},
                token="abcdef1234567890",
            ),
            state,
        )
        matches = resp["result"]["matches"]
        assert matches == []

    def test_case_sensitive_hits(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request(
                "search",
                {"pattern": "OpCapability", "case_sensitive": True},
                token="abcdef1234567890",
            ),
            state,
        )
        matches = resp["result"]["matches"]
        assert len(matches) >= 2

    def test_stage_filter_vs(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("search", {"pattern": "Shader", "stage": "vs"}, token="abcdef1234567890"),
            state,
        )
        matches = resp["result"]["matches"]
        assert all("vs" in m["stages"] for m in matches)
        assert any("Vertex" in m["text"] for m in matches)

    def test_stage_filter_ps(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("search", {"pattern": "Shader", "stage": "ps"}, token="abcdef1234567890"),
            state,
        )
        matches = resp["result"]["matches"]
        assert all("ps" in m["stages"] for m in matches)
        assert any("Pixel" in m["text"] for m in matches)

    def test_stage_filter_no_match(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request(
                "search", {"pattern": "OpCapability", "stage": "cs"}, token="abcdef1234567890"
            ),
            state,
        )
        matches = resp["result"]["matches"]
        assert matches == []

    def test_limit_and_truncated(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("search", {"pattern": "Op", "limit": 1}, token="abcdef1234567890"), state
        )
        result = resp["result"]
        assert len(result["matches"]) == 1
        assert result["truncated"] is True

    def test_no_truncation_when_under_limit(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("search", {"pattern": "Vertex Shader"}, token="abcdef1234567890"), state
        )
        result = resp["result"]
        assert result["truncated"] is False

    def test_context_lines(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request(
                "search",
                {"pattern": "OpCapability", "stage": "vs", "context": 1},
                token="abcdef1234567890",
            ),
            state,
        )
        matches = resp["result"]["matches"]
        assert len(matches) >= 1
        hit = matches[0]
        # context_before or context_after must be present (since line 2 has context from line 1)
        assert "context_before" in hit
        assert "context_after" in hit

    def test_invalid_regex(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("search", {"pattern": "[invalid("}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32602
        assert "invalid regex" in resp["error"]["message"]

    def test_pattern_too_long(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("search", {"pattern": "a" * 501}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32602
        assert "too long" in resp["error"]["message"]

    def test_no_adapter(self) -> None:
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(
            rpc_request("search", {"pattern": "foo"}, token="abcdef1234567890"), s
        )
        assert resp["error"]["code"] == -32002

    def test_no_matches_returns_empty(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("search", {"pattern": "XYZZY_NEVER_MATCHES_42"}, token="abcdef1234567890"),
            state,
        )
        result = resp["result"]
        assert result["matches"] == []
        assert result["truncated"] is False

    def test_match_has_expected_fields(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request(
                "search", {"pattern": "OpCapability", "stage": "vs"}, token="abcdef1234567890"
            ),
            state,
        )
        m = resp["result"]["matches"][0]
        assert "shader" in m
        assert "stages" in m
        assert "first_eid" in m
        assert "line" in m
        assert "text" in m
        assert "context_before" in m
        assert "context_after" in m

    def test_missing_pattern(self, state: DaemonState) -> None:
        resp, _ = _handle_request(rpc_request("search", token="abcdef1234567890"), state)
        assert resp["error"]["code"] == -32602

    def test_cache_reuse(self, state: DaemonState) -> None:
        _handle_request(
            rpc_request("search", {"pattern": "OpCapability"}, token="abcdef1234567890"), state
        )
        assert state.disasm_cache  # cache built
        call_count_before = len(state.disasm_cache)
        # Mutate cache — second call must not rebuild
        state.disasm_cache[100] = "sentinel"
        _handle_request(
            rpc_request("search", {"pattern": "sentinel"}, token="abcdef1234567890"), state
        )
        assert state.disasm_cache[100] == "sentinel"
        assert len(state.disasm_cache) == call_count_before


# ---------------------------------------------------------------------------
# Tests: shader_list_info handler
# ---------------------------------------------------------------------------


class TestShaderListInfo:
    def test_happy_path(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        resp, _ = _handle_request(
            rpc_request("shader_list_info", {"id": 100}, token="abcdef1234567890"), state
        )
        result = resp["result"]
        assert result["id"] == 100
        assert "vs" in result["stages"]
        assert result["uses"] >= 1

    def test_not_found(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        resp, _ = _handle_request(
            rpc_request("shader_list_info", {"id": 9999}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001

    def test_no_adapter(self) -> None:
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(
            rpc_request("shader_list_info", {"id": 100}, token="abcdef1234567890"), s
        )
        assert resp["error"]["code"] == -32002


# ---------------------------------------------------------------------------
# Tests: shader_list_disasm handler
# ---------------------------------------------------------------------------


class TestShaderListDisasm:
    def test_happy_path(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        resp, _ = _handle_request(
            rpc_request("shader_list_disasm", {"id": 200}, token="abcdef1234567890"), state
        )
        result = resp["result"]
        assert result["id"] == 200
        assert "Pixel Shader" in result["disasm"]

    def test_not_found(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        resp, _ = _handle_request(
            rpc_request("shader_list_disasm", {"id": 9999}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001

    def test_no_adapter(self) -> None:
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(
            rpc_request("shader_list_disasm", {"id": 100}, token="abcdef1234567890"), s
        )
        assert resp["error"]["code"] == -32002


# ---------------------------------------------------------------------------
# Tests: VFS /shaders/ tree
# ---------------------------------------------------------------------------


class TestVfsShaders:
    def test_shaders_dir_after_cache_build(self, state: DaemonState) -> None:
        assert state.vfs_tree is not None
        _build_shader_cache(state)
        node = state.vfs_tree.static.get("/shaders")
        assert node is not None
        assert "100" in node.children
        assert "200" in node.children

    def test_shader_subdir_nodes(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        tree = state.vfs_tree
        assert tree is not None
        node_100 = tree.static.get("/shaders/100")
        assert node_100 is not None
        assert node_100.kind == "dir"
        assert "info" in node_100.children
        assert "disasm" in node_100.children

    def test_shader_info_leaf(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        tree = state.vfs_tree
        assert tree is not None
        assert tree.static.get("/shaders/100/info") is not None
        assert tree.static.get("/shaders/100/disasm") is not None

    def test_vfs_ls_shaders(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        resp, _ = _handle_request(
            rpc_request("vfs_ls", {"path": "/shaders"}, token="abcdef1234567890"), state
        )
        assert "result" in resp
        children = resp["result"]["children"]
        names = [c["name"] for c in children]
        assert "100" in names
        assert "200" in names

    def test_populate_shaders_subtree_standalone(self) -> None:
        tree = VfsTree()
        tree.static["/shaders"] = VfsNode("shaders", "dir")
        meta = {
            42: {"stages": ["vs"], "uses": 1, "first_eid": 5, "entry": "main"},
        }
        populate_shaders_subtree(tree, meta)
        assert "42" in tree.static["/shaders"].children
        assert tree.static.get("/shaders/42") is not None
        assert tree.static.get("/shaders/42/info") is not None
        assert tree.static.get("/shaders/42/disasm") is not None


# ---------------------------------------------------------------------------
# Tests: CLI command
# ---------------------------------------------------------------------------


def _patch_search(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]) -> None:
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload, **_kw: {"result": response})


class TestSearchCli:
    def test_basic_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_search(
            monkeypatch,
            {
                "matches": [
                    {
                        "shader": 100,
                        "stages": ["vs"],
                        "first_eid": 10,
                        "line": 2,
                        "text": "OpCapability Shader",
                        "context_before": [],
                        "context_after": [],
                    }
                ],
                "truncated": False,
            },
        )
        result = CliRunner().invoke(main, ["search", "OpCapability"])
        assert result.exit_code == 0
        assert "shader:100" in result.output
        assert "OpCapability" in result.output

    def test_json_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_search(
            monkeypatch,
            {
                "matches": [
                    {
                        "shader": 200,
                        "stages": ["ps"],
                        "first_eid": 10,
                        "line": 3,
                        "text": "OpFMul",
                        "context_before": [],
                        "context_after": [],
                    }
                ],
                "truncated": False,
            },
        )
        result = CliRunner().invoke(main, ["search", "--json", "OpFMul"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert data["matches"][0]["shader"] == 200

    def test_no_matches_silent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_search(monkeypatch, {"matches": [], "truncated": False})
        result = CliRunner().invoke(main, ["search", "NEVERMATCHES"])
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_truncated_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_search(
            monkeypatch,
            {
                "matches": [
                    {
                        "shader": 100,
                        "stages": ["vs"],
                        "first_eid": 10,
                        "line": 1,
                        "text": "Op",
                        "context_before": [],
                        "context_after": [],
                    }
                ],
                "truncated": True,
            },
        )
        result = CliRunner().invoke(main, ["search", "--limit", "1", "Op"])
        assert result.exit_code == 0
        assert "truncated" in result.output or "truncated" in (result.output + result.output)

    def test_context_lines_in_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_search(
            monkeypatch,
            {
                "matches": [
                    {
                        "shader": 100,
                        "stages": ["vs"],
                        "first_eid": 10,
                        "line": 2,
                        "text": "OpCapability Shader",
                        "context_before": ["; Vertex Shader"],
                        "context_after": ["%pos = OpLoad %v4float %in_pos"],
                    }
                ],
                "truncated": False,
            },
        )
        result = CliRunner().invoke(main, ["search", "-C", "1", "OpCapability"])
        assert result.exit_code == 0
        assert "Vertex Shader" in result.output
        assert "OpLoad" in result.output

    def test_stage_option_passed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        import rdc.commands._helpers as mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(mod, "load_session", lambda: session)

        def _capture_request(
            _h: str,
            _p: int,
            payload: dict[str, Any],
            **_kw: Any,
        ) -> dict[str, Any]:
            captured.append(payload)
            return {"result": {"matches": [], "truncated": False}}

        monkeypatch.setattr(mod, "send_request", _capture_request)
        CliRunner().invoke(main, ["search", "--stage", "vs", "Op"])
        assert captured
        assert captured[0]["params"]["stage"] == "vs"

    def test_case_sensitive_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        import rdc.commands._helpers as mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(mod, "load_session", lambda: session)

        def _capture_request(
            _h: str,
            _p: int,
            payload: dict[str, Any],
            **_kw: Any,
        ) -> dict[str, Any]:
            captured.append(payload)
            return {"result": {"matches": [], "truncated": False}}

        monkeypatch.setattr(mod, "send_request", _capture_request)
        CliRunner().invoke(main, ["search", "--case-sensitive", "Op"])
        assert captured[0]["params"]["case_sensitive"] is True

    def test_short_i_flag_removed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """B19: -i shorthand removed to avoid grep confusion."""
        _patch_search(monkeypatch, {"matches": [], "truncated": False})
        result = CliRunner().invoke(main, ["search", "-i", "Op"])
        assert result.exit_code != 0
