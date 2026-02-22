"""Tests for rt_overlay daemon handler (phase4c-overlay)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as mock_rd
from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    Descriptor,
    MockReplayOutput,
    ResourceDescription,
    ResourceId,
)

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request
from rdc.vfs.tree_cache import build_vfs_skeleton


def _build_actions() -> list[ActionDescription]:
    return [
        ActionDescription(
            eventId=10,
            flags=ActionFlags.Drawcall,
            numIndices=3,
            _name="Draw",
        ),
    ]


def _build_resources() -> list[ResourceDescription]:
    return [ResourceDescription(resourceId=ResourceId(1), name="res0")]


def _req(method: str, **params: Any) -> dict[str, Any]:
    p: dict[str, Any] = {"_token": "abcdef1234567890"}
    p.update(params)
    return {"id": 1, "method": method, "params": p}


@pytest.fixture()
def state(tmp_path: Path) -> DaemonState:
    actions = _build_actions()
    resources = _build_resources()

    output_targets = [Descriptor(resource=ResourceId(100))]
    create_output_calls: list[tuple[Any, Any]] = []

    def _create_output(windowing: Any, output_type: Any) -> MockReplayOutput:
        create_output_calls.append((windowing, output_type))
        return MockReplayOutput()

    controller = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: resources,
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: SimpleNamespace(chunks=[]),
        GetPipelineState=lambda: SimpleNamespace(
            GetOutputTargets=lambda: output_targets,
        ),
        GetTextures=lambda: [],
        GetBuffers=lambda: [],
        GetDebugMessages=lambda: [],
        SaveTexture=lambda texsave, path: (
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100),
            True,
        )[1],
        CreateOutput=_create_output,
        Shutdown=lambda: None,
        _output_targets=output_targets,
        _create_output_calls=create_output_calls,
    )

    s = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    s.adapter = RenderDocAdapter(controller=controller, version=(1, 41))
    s.max_eid = 10
    s.rd = mock_rd
    s.temp_dir = tmp_path
    s.vfs_tree = build_vfs_skeleton(actions, resources)
    return s


class TestOverlayHandler:
    def test_wireframe_overlay(self, state: DaemonState) -> None:
        resp, _ = _handle_request(_req("rt_overlay", eid=10, overlay="wireframe"), state)
        r = resp["result"]
        assert Path(r["path"]).exists()
        assert r["size"] > 0
        assert r["overlay"] == "wireframe"
        assert r["eid"] == 10

    def test_depth_overlay(self, state: DaemonState) -> None:
        resp, _ = _handle_request(_req("rt_overlay", eid=10, overlay="depth"), state)
        r = resp["result"]
        assert r["size"] > 0
        assert r["overlay"] == "depth"

    def test_overdraw_overlay(self, state: DaemonState) -> None:
        resp, _ = _handle_request(_req("rt_overlay", eid=10, overlay="overdraw"), state)
        r = resp["result"]
        assert r["size"] > 0
        assert r["overlay"] == "overdraw"

    def test_custom_dimensions(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            _req("rt_overlay", eid=10, overlay="wireframe", width=512, height=512), state
        )
        assert "result" in resp
        calls = state.adapter.controller._create_output_calls
        assert len(calls) == 1
        windowing, _ = calls[0]
        assert windowing.width == 512
        assert windowing.height == 512

    def test_default_eid_uses_current(self, state: DaemonState) -> None:
        state.current_eid = 10
        resp, _ = _handle_request(_req("rt_overlay", overlay="wireframe"), state)
        r = resp["result"]
        assert r["eid"] == 10

    def test_replay_output_cached(self, state: DaemonState) -> None:
        existing = MockReplayOutput()
        state.replay_output = existing
        state.replay_output_dims = (256, 256)
        resp, _ = _handle_request(_req("rt_overlay", eid=10, overlay="wireframe"), state)
        assert "result" in resp
        assert len(state.adapter.controller._create_output_calls) == 0
        assert state.replay_output is existing

    def test_replay_output_recreated_on_dimension_change(self, state: DaemonState) -> None:
        old_output = MockReplayOutput()
        state.replay_output = old_output
        state.replay_output_dims = (256, 256)
        resp, _ = _handle_request(
            _req("rt_overlay", eid=10, overlay="wireframe", width=512, height=512), state
        )
        assert "result" in resp
        calls = state.adapter.controller._create_output_calls
        assert len(calls) == 1
        windowing, _ = calls[0]
        assert windowing.width == 512
        assert windowing.height == 512
        assert state.replay_output is not old_output
        assert state.replay_output_dims == (512, 512)

    def test_invalid_overlay_name(self, state: DaemonState) -> None:
        resp, _ = _handle_request(_req("rt_overlay", eid=10, overlay="invalid"), state)
        assert resp["error"]["code"] == -32602

    def test_no_adapter(self) -> None:
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(_req("rt_overlay", eid=10, overlay="wireframe"), s)
        assert resp["error"]["code"] == -32002

    def test_no_output_targets(self, state: DaemonState) -> None:
        state.adapter.controller._output_targets.clear()
        resp, _ = _handle_request(_req("rt_overlay", eid=10, overlay="wireframe"), state)
        assert resp["error"]["code"] == -32001

    def test_rd_none(self, state: DaemonState) -> None:
        state.rd = None
        resp, _ = _handle_request(_req("rt_overlay", eid=10, overlay="wireframe"), state)
        assert resp["error"]["code"] == -32002

    def test_temp_dir_none(self, state: DaemonState) -> None:
        state.temp_dir = None
        resp, _ = _handle_request(_req("rt_overlay", eid=10, overlay="wireframe"), state)
        assert resp["error"]["code"] == -32002
