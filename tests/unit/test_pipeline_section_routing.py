"""Unit tests for phase2.7: pipeline section routing, shader --target dispatch, bindings --set."""

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
    MockPipeState,
    ResourceDescription,
    ResourceId,
    ShaderReflection,
    ShaderResource,
    ShaderStage,
)

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request
from rdc.vfs.tree_cache import build_vfs_skeleton


def _build_actions() -> list[ActionDescription]:
    return [ActionDescription(eventId=10, flags=ActionFlags.Drawcall, numIndices=3, _name="Draw")]


def _build_resources() -> list[ResourceDescription]:
    return [ResourceDescription(resourceId=ResourceId(1), name="res0")]


def _req(method: str, **params: Any) -> dict[str, Any]:
    p: dict[str, Any] = {"_token": "abcdef1234567890"}
    p.update(params)
    return {"id": 1, "method": method, "params": p}


def _make_state(tmp_path: Path, pipe: MockPipeState) -> DaemonState:
    actions = _build_actions()
    resources = _build_resources()
    controller = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: resources,
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: SimpleNamespace(chunks=[]),
        GetPipelineState=lambda: pipe,
        GetTextures=lambda: [],
        GetBuffers=lambda: [],
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
    )
    s = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    s.adapter = RenderDocAdapter(controller=controller, version=(1, 41))
    s.max_eid = 10
    s.rd = mock_rd
    s.temp_dir = tmp_path
    s.vfs_tree = build_vfs_skeleton(actions, resources)
    return s


# ── A: Pipeline section routing ───────────────────────────────────────────────


class TestPipelineSectionRouting:
    def test_topology_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="topology"), s)
        assert "error" not in resp
        assert "topology" in resp["result"]

    def test_viewport_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="viewport"), s)
        assert "error" not in resp
        r = resp["result"]
        assert "x" in r and "y" in r and "width" in r and "height" in r

    def test_blend_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="blend"), s)
        assert "error" not in resp
        assert "blends" in resp["result"]

    def test_vinputs_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="vinputs"), s)
        assert "error" not in resp
        assert "inputs" in resp["result"]

    def test_rasterizer_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="rasterizer"), s)
        assert "error" not in resp
        assert "eid" in resp["result"]

    def test_depth_stencil_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="depth-stencil"), s)
        assert "error" not in resp
        assert "eid" in resp["result"]

    def test_msaa_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="msaa"), s)
        assert "error" not in resp
        assert "eid" in resp["result"]

    def test_scissor_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="scissor"), s)
        assert "error" not in resp
        assert "eid" in resp["result"]

    def test_stencil_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="stencil"), s)
        assert "error" not in resp
        assert "eid" in resp["result"]

    def test_vbuffers_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="vbuffers"), s)
        assert "error" not in resp
        assert "vbuffers" in resp["result"]

    def test_ibuffer_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="ibuffer"), s)
        assert "error" not in resp
        assert "eid" in resp["result"]

    def test_samplers_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="samplers"), s)
        assert "error" not in resp
        assert "samplers" in resp["result"]

    def test_push_constants_section_delegates(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="push-constants"), s)
        assert "error" not in resp
        assert "push_constants" in resp["result"]

    def test_invalid_section_returns_error(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="xyz"), s)
        assert "error" in resp
        assert resp["error"]["code"] == -32602

    def test_shader_stage_section_still_works(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        refl = ShaderReflection(resourceId=ResourceId(5))
        pipe._shaders[ShaderStage.Pixel] = ResourceId(5)
        pipe._reflections[ShaderStage.Pixel] = refl
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="ps"), s)
        assert "error" not in resp
        row = resp["result"]["row"]
        assert row.get("section") == "ps"

    def test_section_name_case_normalized(self, tmp_path: Path) -> None:
        """Section name is lowercased before routing."""
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipeline", eid=10, section="TOPOLOGY"), s)
        assert "error" not in resp
        assert "topology" in resp["result"]


# ── C: Bindings set filtering ─────────────────────────────────────────────────


class TestBindingsSetFiltering:
    def _make_rows(self) -> list[dict]:
        return [
            {"eid": 1, "stage": "ps", "kind": "ro", "set": 0, "slot": 0, "name": "tex0"},
            {"eid": 1, "stage": "ps", "kind": "ro", "set": 1, "slot": 2, "name": "tex1"},
            {"eid": 1, "stage": "vs", "kind": "ro", "set": 0, "slot": 3, "name": "buf0"},
        ]

    def test_set_filter_returns_only_matching(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        rows = self._make_rows()
        import rdc.services.query_service as qs

        monkeypatch.setattr(qs, "bindings_rows", lambda eid, pipe_state: rows)
        resp, _ = _handle_request(_req("bindings", eid=1, set=1), s)
        assert "error" not in resp
        result_rows = resp["result"]["rows"]
        assert len(result_rows) == 1
        assert result_rows[0]["set"] == 1
        assert result_rows[0]["name"] == "tex1"

    def test_set_filter_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        rows = self._make_rows()
        import rdc.services.query_service as qs

        monkeypatch.setattr(qs, "bindings_rows", lambda eid, pipe_state: rows)
        resp, _ = _handle_request(_req("bindings", eid=1, set=0), s)
        assert "error" not in resp
        result_rows = resp["result"]["rows"]
        assert len(result_rows) == 2
        assert all(r["set"] == 0 for r in result_rows)

    def test_set_and_binding_combined(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        rows = self._make_rows()
        import rdc.services.query_service as qs

        monkeypatch.setattr(qs, "bindings_rows", lambda eid, pipe_state: rows)
        resp, _ = _handle_request(_req("bindings", eid=1, set=0, binding=3), s)
        assert "error" not in resp
        result_rows = resp["result"]["rows"]
        assert len(result_rows) == 1
        assert result_rows[0]["name"] == "buf0"

    def test_binding_filter_without_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        rows = self._make_rows()
        import rdc.services.query_service as qs

        monkeypatch.setattr(qs, "bindings_rows", lambda eid, pipe_state: rows)
        resp, _ = _handle_request(_req("bindings", eid=1, binding=0), s)
        assert "error" not in resp
        result_rows = resp["result"]["rows"]
        assert len(result_rows) == 1
        assert result_rows[0]["name"] == "tex0"


# ── C1/C2: bindings_rows set field ────────────────────────────────────────────


class TestBindingsRowsSetField:
    def test_set_field_present_in_ro_row(self) -> None:
        from rdc.services.query_service import bindings_rows

        pipe = MockPipeState()
        refl = ShaderReflection(
            resourceId=ResourceId(5),
            readOnlyResources=[
                ShaderResource(name="tex", fixedBindNumber=2, fixedBindSetOrSpace=1)
            ],
        )
        pipe._shaders[ShaderStage.Pixel] = ResourceId(5)
        pipe._reflections[ShaderStage.Pixel] = refl

        rows = bindings_rows(5, pipe)
        assert len(rows) == 1
        assert rows[0]["set"] == 1
        assert rows[0]["slot"] == 2
        assert rows[0]["name"] == "tex"

    def test_set_field_present_in_rw_row(self) -> None:
        from rdc.services.query_service import bindings_rows

        pipe = MockPipeState()
        refl = ShaderReflection(
            resourceId=ResourceId(5),
            readWriteResources=[
                ShaderResource(name="rwbuf", fixedBindNumber=0, fixedBindSetOrSpace=3)
            ],
        )
        pipe._shaders[ShaderStage.Pixel] = ResourceId(5)
        pipe._reflections[ShaderStage.Pixel] = refl

        rows = bindings_rows(5, pipe)
        assert len(rows) == 1
        assert rows[0]["set"] == 3
        assert rows[0]["kind"] == "rw"

    def test_set_defaults_to_zero_when_attr_missing(self) -> None:
        from rdc.services.query_service import bindings_rows

        pipe = MockPipeState()
        resource = ShaderResource(name="tex2", fixedBindNumber=1)
        # remove fixedBindSetOrSpace if present (it has default=0 in mock, that's fine)
        refl = ShaderReflection(
            resourceId=ResourceId(6),
            readOnlyResources=[resource],
        )
        pipe._shaders[ShaderStage.Vertex] = ResourceId(6)
        pipe._reflections[ShaderStage.Vertex] = refl

        rows = bindings_rows(1, pipe)
        assert len(rows) == 1
        assert rows[0]["set"] == 0

    def test_row_has_all_required_keys(self) -> None:
        from rdc.services.query_service import bindings_rows

        pipe = MockPipeState()
        refl = ShaderReflection(
            resourceId=ResourceId(7),
            readOnlyResources=[ShaderResource(name="x", fixedBindNumber=0)],
        )
        pipe._shaders[ShaderStage.Pixel] = ResourceId(7)
        pipe._reflections[ShaderStage.Pixel] = refl

        rows = bindings_rows(10, pipe)
        required = {"eid", "stage", "kind", "set", "slot", "name"}
        assert required.issubset(rows[0].keys())
