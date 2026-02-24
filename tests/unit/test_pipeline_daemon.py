"""Tests for shaders daemon handler stage filter (phase2.7-bug-filters Fix 1)."""

from __future__ import annotations

import mock_renderdoc as rd
from conftest import rpc_request

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request


def _make_state() -> DaemonState:
    ctrl = rd.MockReplayController()
    a = rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)
    ctrl._actions = [a]
    vs_id = rd.ResourceId(1)
    ps_id = rd.ResourceId(2)
    ctrl._pipe_state._shaders[rd.ShaderStage.Vertex] = vs_id
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.api_name = "Vulkan"
    state.max_eid = 100
    return state


def _make_state_with_shader_meta() -> DaemonState:
    """Create state with pre-populated shader_meta (bypass _build_shader_cache)."""
    state = _make_state()
    state._shader_cache_built = True
    _m = {"first_eid": 10, "entry": "main", "inputs": 0, "outputs": 0}
    state.shader_meta = {
        1: {"stages": ["vs"], "uses": 2, **_m},
        2: {"stages": ["ps"], "uses": 2, **_m},
        3: {"stages": ["ps", "vs"], "uses": 1, **_m},
    }
    return state


class TestShadersStageFilter:
    def test_stage_filter_applied(self) -> None:
        state = _make_state_with_shader_meta()
        resp, _ = _handle_request(rpc_request("shaders", {"stage": "vs"}), state)
        rows = resp["result"]["rows"]
        assert len(rows) == 2
        for r in rows:
            assert "vs" in r["stages"].lower().split(",")

    def test_stage_filter_case_insensitive(self) -> None:
        state = _make_state_with_shader_meta()
        resp, _ = _handle_request(rpc_request("shaders", {"stage": "VS"}), state)
        rows = resp["result"]["rows"]
        assert len(rows) == 2
        for r in rows:
            assert "vs" in r["stages"].lower().split(",")

    def test_stage_filter_no_match(self) -> None:
        state = _make_state_with_shader_meta()
        resp, _ = _handle_request(rpc_request("shaders", {"stage": "cs"}), state)
        assert resp["result"]["rows"] == []

    def test_no_stage_filter_returns_all(self) -> None:
        state = _make_state_with_shader_meta()
        resp, _ = _handle_request(rpc_request("shaders"), state)
        assert len(resp["result"]["rows"]) == 3

    def test_invalid_stage_returns_empty_not_error(self) -> None:
        state = _make_state_with_shader_meta()
        resp, _ = _handle_request(rpc_request("shaders", {"stage": "zz"}), state)
        assert "error" not in resp
        assert resp["result"]["rows"] == []

    def test_no_adapter_returns_error(self) -> None:
        state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(rpc_request("shaders", {"stage": "vs"}), state)
        assert resp["error"]["code"] == -32002
