"""Tests for shaders daemon handler stage filter (phase2.7-bug-filters Fix 1)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd

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


def _req(method: str, **params: Any) -> dict[str, Any]:
    p: dict[str, Any] = {"_token": "tok"}
    p.update(params)
    return {"id": 1, "method": method, "params": p}


_MOCK_ROWS = [
    {"shader": 1, "stages": "vs", "uses": 2},
    {"shader": 2, "stages": "ps", "uses": 2},
    {"shader": 3, "stages": "vs,ps", "uses": 1},
]


class TestShadersStageFilter:
    def test_stage_filter_applied(self) -> None:
        state = _make_state()
        with patch("rdc.services.query_service.shader_inventory", return_value=list(_MOCK_ROWS)):
            resp, _ = _handle_request(_req("shaders", stage="vs"), state)
        rows = resp["result"]["rows"]
        assert len(rows) == 2
        for r in rows:
            assert "vs" in r["stages"].lower().split(",")

    def test_stage_filter_case_insensitive(self) -> None:
        state = _make_state()
        with patch("rdc.services.query_service.shader_inventory", return_value=list(_MOCK_ROWS)):
            resp, _ = _handle_request(_req("shaders", stage="VS"), state)
        rows = resp["result"]["rows"]
        assert len(rows) == 2
        for r in rows:
            assert "vs" in r["stages"].lower().split(",")

    def test_stage_filter_no_match(self) -> None:
        state = _make_state()
        with patch("rdc.services.query_service.shader_inventory", return_value=list(_MOCK_ROWS)):
            resp, _ = _handle_request(_req("shaders", stage="cs"), state)
        assert resp["result"]["rows"] == []

    def test_no_stage_filter_returns_all(self) -> None:
        state = _make_state()
        with patch("rdc.services.query_service.shader_inventory", return_value=list(_MOCK_ROWS)):
            resp, _ = _handle_request(_req("shaders"), state)
        assert len(resp["result"]["rows"]) == 3

    def test_invalid_stage_returns_empty_not_error(self) -> None:
        state = _make_state()
        with patch("rdc.services.query_service.shader_inventory", return_value=list(_MOCK_ROWS)):
            resp, _ = _handle_request(_req("shaders", stage="zz"), state)
        assert "error" not in resp
        assert resp["result"]["rows"] == []

    def test_no_adapter_returns_error(self) -> None:
        state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(_req("shaders", stage="vs"), state)
        assert resp["error"]["code"] == -32002
