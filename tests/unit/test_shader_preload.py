"""Tests for B3: single-pass shader cache + shaders_preload RPC + --preload flag."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as mock_rd
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
from rdc.vfs.tree_cache import build_vfs_skeleton

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VS_DISASM = "; Vertex Shader\nOpCapability Shader\n"
_PS_DISASM = "; Pixel Shader\nOpCapability Shader\n"


def _req(method: str, **params: Any) -> dict[str, Any]:
    p: dict[str, Any] = {"_token": "abcdef1234567890"}
    p.update(params)
    return {"id": 1, "method": method, "params": p}


def _build_pipe(vs_id: int, ps_id: int) -> MockPipeState:
    pipe = MockPipeState()
    pipe._shaders[ShaderStage.Vertex] = ResourceId(vs_id)
    pipe._shaders[ShaderStage.Pixel] = ResourceId(ps_id)
    vs_refl = ShaderReflection(resourceId=ResourceId(vs_id), stage=ShaderStage.Vertex)
    ps_refl = ShaderReflection(resourceId=ResourceId(ps_id), stage=ShaderStage.Pixel)
    pipe._reflections[ShaderStage.Vertex] = vs_refl
    pipe._reflections[ShaderStage.Pixel] = ps_refl
    return pipe


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tracked_controller() -> tuple[SimpleNamespace, list[int]]:
    """Controller with tracked SetFrameEvent calls via a separate log."""
    ctrl = mock_rd.MockReplayController()
    ctrl._disasm_text = {100: _VS_DISASM, 200: _PS_DISASM, 300: _VS_DISASM}

    # 3 draws with different EIDs, draws at eid 10 & 20 share vs=100/ps=200,
    # draw at eid 30 has vs=300/ps=200.
    pipe_10_20 = _build_pipe(vs_id=100, ps_id=200)
    pipe_30 = _build_pipe(vs_id=300, ps_id=200)

    pipe_map: dict[int, MockPipeState] = {10: pipe_10_20, 20: pipe_10_20, 30: pipe_30}
    current_pipe: list[MockPipeState] = [pipe_10_20]

    call_log: list[int] = []

    def _set_frame_event(eid: int, force: bool) -> None:
        call_log.append(eid)
        current_pipe[0] = pipe_map.get(eid, pipe_10_20)

    actions = [
        ActionDescription(eventId=10, flags=ActionFlags.Drawcall, numIndices=3, _name="Draw1"),
        ActionDescription(eventId=20, flags=ActionFlags.Drawcall, numIndices=3, _name="Draw2"),
        ActionDescription(eventId=30, flags=ActionFlags.Drawcall, numIndices=3, _name="Draw3"),
    ]

    ns = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: [ResourceDescription(resourceId=ResourceId(1), name="res0")],
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        SetFrameEvent=_set_frame_event,
        GetStructuredFile=lambda: SimpleNamespace(chunks=[]),
        GetPipelineState=lambda: current_pipe[0],
        GetTextures=lambda: [],
        GetBuffers=lambda: [],
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
        DisassembleShader=ctrl.DisassembleShader,
        GetDisassemblyTargets=lambda _with_pipeline: ["SPIR-V"],
    )
    return ns, call_log


@pytest.fixture()
def tracked_state(
    tracked_controller: tuple[SimpleNamespace, list[int]], tmp_path: Path
) -> tuple[DaemonState, list[int]]:
    ns, call_log = tracked_controller
    actions = ns.GetRootActions()
    resources = ns.GetResources()

    s = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    s.adapter = RenderDocAdapter(controller=ns, version=(1, 41))
    s.max_eid = 30
    s.rd = mock_rd
    s.temp_dir = tmp_path
    s.vfs_tree = build_vfs_skeleton(actions, resources)
    return s, call_log


@pytest.fixture()
def state(tmp_path: Path) -> DaemonState:
    """Standard state fixture with single draw, reusable for cache population tests."""
    ctrl = mock_rd.MockReplayController()
    ctrl._disasm_text = {100: _VS_DISASM, 200: _PS_DISASM}
    ctrl._pipe_state = _build_pipe(vs_id=100, ps_id=200)

    actions = [
        ActionDescription(eventId=10, flags=ActionFlags.Drawcall, numIndices=3, _name="Draw"),
    ]
    ctrl._actions = actions
    ctrl._resources = [ResourceDescription(resourceId=ResourceId(1), name="res0")]

    ns = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: ctrl._resources,
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: SimpleNamespace(chunks=[]),
        GetPipelineState=lambda: ctrl._pipe_state,
        GetTextures=lambda: [],
        GetBuffers=lambda: [],
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
        DisassembleShader=ctrl.DisassembleShader,
        GetDisassemblyTargets=lambda _with_pipeline: ["SPIR-V"],
    )

    s = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    s.adapter = RenderDocAdapter(controller=ns, version=(1, 41))
    s.max_eid = 10
    s.rd = mock_rd
    s.temp_dir = tmp_path
    s.vfs_tree = build_vfs_skeleton(actions, ctrl._resources)
    return s


# ---------------------------------------------------------------------------
# Tests: single-pass _build_shader_cache
# ---------------------------------------------------------------------------


class TestBuildShaderCacheSinglePass:
    def test_set_frame_event_called_once_per_draw(
        self, tracked_state: tuple[DaemonState, list[int]]
    ) -> None:
        s, call_log = tracked_state
        _build_shader_cache(s)
        # 3 draws with distinct EIDs -> SetFrameEvent called 3 times
        # (not 3 + N_unique_shaders for a second pass)
        assert len(call_log) == 3
        assert len(call_log) == len(set(call_log))

    def test_disasm_cache_populated(self, tracked_state: tuple[DaemonState, list[int]]) -> None:
        s, _ = tracked_state
        _build_shader_cache(s)
        # 3 unique shaders: 100, 200, 300
        assert 100 in s.disasm_cache
        assert 200 in s.disasm_cache
        assert 300 in s.disasm_cache

    def test_pipe_states_cache_populated(
        self, tracked_state: tuple[DaemonState, list[int]]
    ) -> None:
        s, _ = tracked_state
        _build_shader_cache(s)
        assert len(s._pipe_states_cache) == 3
        assert 10 in s._pipe_states_cache
        assert 20 in s._pipe_states_cache
        assert 30 in s._pipe_states_cache


class TestBuildShaderCacheIdempotent:
    def test_second_call_is_noop(self, tracked_state: tuple[DaemonState, list[int]]) -> None:
        s, call_log = tracked_state
        _build_shader_cache(s)
        count_first = len(call_log)
        # mutate cache
        s.disasm_cache[100] = "sentinel"
        _build_shader_cache(s)
        # second call must not increase call count
        assert len(call_log) == count_first
        # sentinel survives
        assert s.disasm_cache[100] == "sentinel"


class TestBuildShaderCachePopulatesCaches:
    def test_disasm_and_meta(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        assert 100 in state.disasm_cache
        assert 200 in state.disasm_cache
        assert 100 in state.shader_meta
        assert 200 in state.shader_meta
        assert "vs" in state.shader_meta[100]["stages"]
        assert "ps" in state.shader_meta[200]["stages"]

    def test_vfs_shaders_subtree(self, state: DaemonState) -> None:
        _build_shader_cache(state)
        assert state.vfs_tree is not None
        assert state.vfs_tree.static.get("/shaders/100") is not None
        assert state.vfs_tree.static.get("/shaders/200") is not None


# ---------------------------------------------------------------------------
# Tests: shaders_preload RPC handler
# ---------------------------------------------------------------------------


class TestHandlePreload:
    def test_builds_cache_and_returns_count(self, state: DaemonState) -> None:
        resp, running = _handle_request(_req("shaders_preload"), state)
        assert "error" not in resp
        assert resp["result"]["done"] is True
        assert resp["result"]["shaders"] > 0
        assert state._shader_cache_built is True
        assert running is True

    def test_idempotent(self, state: DaemonState) -> None:
        resp1, _ = _handle_request(_req("shaders_preload"), state)
        n1 = resp1["result"]["shaders"]
        # mutate to verify no rebuild
        state.disasm_cache[100] = "sentinel"
        resp2, _ = _handle_request(_req("shaders_preload"), state)
        n2 = resp2["result"]["shaders"]
        assert n1 == n2
        assert state.disasm_cache[100] == "sentinel"


# ---------------------------------------------------------------------------
# Tests: CLI --preload flag
# ---------------------------------------------------------------------------


class TestOpenPreloadFlag:
    def test_preload_calls_rpc(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
        monkeypatch.delenv("RDC_SESSION", raising=False)
        monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)

        captured: list[dict[str, Any]] = []
        import rdc.commands._helpers as helpers_mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)

        def _capture_send(_h: str, _p: int, payload: dict[str, Any]) -> dict[str, Any]:
            captured.append(payload)
            return {"result": {"done": True, "shaders": 5}}

        monkeypatch.setattr(helpers_mod, "send_request", _capture_send)

        runner = CliRunner()
        result = runner.invoke(main, ["open", "--preload", "test.rdc"])
        assert result.exit_code == 0
        assert "preloaded 5 shader(s)" in result.output
        preload_calls = [c for c in captured if c.get("method") == "shaders_preload"]
        assert len(preload_calls) == 1

    def test_no_preload_does_not_call_rpc(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
        monkeypatch.delenv("RDC_SESSION", raising=False)
        monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)

        captured: list[dict[str, Any]] = []
        import rdc.commands._helpers as helpers_mod

        monkeypatch.setattr(helpers_mod, "send_request", lambda *a: captured.append(a))

        runner = CliRunner()
        result = runner.invoke(main, ["open", "test.rdc"])
        assert result.exit_code == 0
        assert "preloaded" not in result.output
        preload_calls = [
            c for c in captured if isinstance(c, dict) and c.get("method") == "shaders_preload"
        ]
        assert len(preload_calls) == 0


# ---------------------------------------------------------------------------
# Tests: handler callers use cache, not _collect_pipe_states
# ---------------------------------------------------------------------------


class TestHandleShadersUsesCache:
    def test_uses_build_shader_cache(
        self, state: DaemonState, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        build_calls: list[bool] = []
        original_build = _build_shader_cache

        def _tracking_build(s: DaemonState) -> None:
            build_calls.append(True)
            original_build(s)

        monkeypatch.setattr("rdc.handlers.query._build_shader_cache", _tracking_build)

        resp, _ = _handle_request(_req("shaders"), state)
        assert "error" not in resp
        assert len(build_calls) == 1


class TestCountShadersUsesCache:
    def test_count_via_shader_meta(self, state: DaemonState) -> None:
        resp, _ = _handle_request(_req("count", what="shaders"), state)
        assert "error" not in resp
        count_val = resp["result"]["value"]
        assert count_val == len(state.shader_meta)
        assert count_val > 0


# ---------------------------------------------------------------------------
# Tests: B17 — read-only queries must not mutate current_eid
# ---------------------------------------------------------------------------


class TestEidPreservation:
    """B17: read-only queries must not mutate current_eid."""

    def test_build_shader_cache_preserves_current_eid(
        self, tracked_state: tuple[DaemonState, list[int]]
    ) -> None:
        s, _ = tracked_state
        s.current_eid = 50
        _build_shader_cache(s)
        assert s.current_eid == 50

    def test_stats_preserves_current_eid(
        self, tracked_state: tuple[DaemonState, list[int]]
    ) -> None:
        """_handle_stats RT enrichment must not change current_eid."""
        s, _ = tracked_state
        s.current_eid = 50
        s.structured_file = SimpleNamespace(chunks=[])
        resp, _ = _handle_request(_req("stats"), s)
        assert "error" not in resp
        assert s.current_eid == 50

    def test_pass_preserves_current_eid(self, tracked_state: tuple[DaemonState, list[int]]) -> None:
        """_handle_pass target lookup must not change current_eid."""
        s, _ = tracked_state
        s.current_eid = 50
        s.structured_file = SimpleNamespace(chunks=[])
        resp, _ = _handle_request(_req("pass", index=0), s)
        # Even if pass lookup fails, current_eid must be preserved
        assert s.current_eid == 50
