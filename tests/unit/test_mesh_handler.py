"""Tests for mesh_data daemon handler (phase4c-mesh-export)."""

from __future__ import annotations

import struct
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
    MeshFormat,
    ResourceDescription,
    ResourceFormat,
    ResourceId,
)

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request
from rdc.vfs.tree_cache import build_vfs_skeleton

# 3 vertices: (x, y, z, w)
_VERTS = [
    (0.0, 0.5, 0.0, 1.0),
    (-0.5, -0.5, 0.0, 1.0),
    (0.5, -0.5, 0.0, 1.0),
]
_VBUF = b"".join(struct.pack("<4f", *v) for v in _VERTS)
_IBUF = struct.pack("<3H", 0, 2, 1)


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


def _triangle_mesh(
    *,
    indexed: bool = False,
    stage_val: int = 1,
) -> MeshFormat:
    """Build a MeshFormat for a 3-vertex triangle."""
    m = MeshFormat(
        vertexResourceId=ResourceId(800),
        vertexByteStride=16,
        vertexByteOffset=0,
        vertexByteSize=len(_VBUF),
        format=ResourceFormat(
            name="R32G32B32A32_FLOAT",
            compByteWidth=4,
            compCount=4,
        ),
        numIndices=3,
        topology="TriangleList",
    )
    if indexed:
        m.indexResourceId = ResourceId(801)
        m.indexByteStride = 2
        m.indexByteOffset = 0
        m.indexByteSize = len(_IBUF)
    return m


@pytest.fixture()
def state() -> DaemonState:
    actions = _build_actions()
    resources = _build_resources()

    def _get_buffer_data(resource_id: Any, offset: int, length: int) -> bytes:
        rid = int(resource_id)
        if rid == 800:
            return _VBUF
        if rid == 801:
            return _IBUF
        return b""

    # Default: vs-out returns triangle mesh, gs-out returns empty
    postvs: dict[int, MeshFormat] = {1: _triangle_mesh()}

    def _get_postvs(inst: int, view: int, stage: Any) -> MeshFormat:
        return postvs.get(int(stage), MeshFormat())

    controller = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: resources,
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: SimpleNamespace(chunks=[]),
        GetPipelineState=lambda: SimpleNamespace(),
        GetTextures=lambda: [],
        GetBuffers=lambda: [],
        GetDebugMessages=lambda: [],
        GetPostVSData=_get_postvs,
        GetBufferData=_get_buffer_data,
        Shutdown=lambda: None,
        _postvs=postvs,
    )

    s = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    s.adapter = RenderDocAdapter(controller=controller, version=(1, 41))
    s.max_eid = 10
    s.rd = mock_rd
    s.vfs_tree = build_vfs_skeleton(actions, resources)
    return s


class TestMeshData:
    def test_mesh_data_triangle_list(self, state: DaemonState) -> None:
        """Non-indexed triangle returns 3 vertices with correct values."""
        resp, _ = _handle_request(_req("mesh_data", eid=10), state)
        r = resp["result"]
        assert r["vertex_count"] == 3
        assert r["topology"] == "TriangleList"
        assert r["index_count"] == 0
        assert r["indices"] == []
        assert len(r["vertices"]) == 3
        assert r["comp_count"] == 4
        assert r["stride"] == 16
        # Check first vertex
        assert r["vertices"][0] == pytest.approx([0.0, 0.5, 0.0, 1.0])
        assert r["vertices"][1] == pytest.approx([-0.5, -0.5, 0.0, 1.0])
        assert r["vertices"][2] == pytest.approx([0.5, -0.5, 0.0, 1.0])

    def test_mesh_data_indexed(self, state: DaemonState) -> None:
        """Indexed triangle returns indices [0, 2, 1]."""
        state.adapter.controller._postvs[1] = _triangle_mesh(indexed=True)
        resp, _ = _handle_request(_req("mesh_data", eid=10), state)
        r = resp["result"]
        assert r["index_count"] == 3
        assert r["indices"] == [0, 2, 1]
        assert r["vertex_count"] == 3

    def test_mesh_data_gs_out(self, state: DaemonState) -> None:
        """stage=gs-out passes stage_val=2 to GetPostVSData."""
        state.adapter.controller._postvs[2] = _triangle_mesh()
        resp, _ = _handle_request(_req("mesh_data", eid=10, stage="gs-out"), state)
        r = resp["result"]
        assert r["stage"] == "gs-out"
        assert r["vertex_count"] == 3

    def test_mesh_data_default_stage(self, state: DaemonState) -> None:
        """Omitting stage defaults to vs-out."""
        resp, _ = _handle_request(_req("mesh_data", eid=10), state)
        r = resp["result"]
        assert r["stage"] == "vs-out"

    def test_mesh_data_no_postvs(self, state: DaemonState) -> None:
        """Empty MeshFormat (vertexResourceId=0) returns error -32001."""
        state.adapter.controller._postvs.clear()
        resp, _ = _handle_request(_req("mesh_data", eid=10), state)
        assert resp["error"]["code"] == -32001

    def test_mesh_data_no_adapter(self) -> None:
        """No adapter loaded returns error -32002."""
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(_req("mesh_data", eid=10), s)
        assert resp["error"]["code"] == -32002

    def test_mesh_data_uses_current_eid(self, state: DaemonState) -> None:
        """Omitting eid uses state.current_eid."""
        state.current_eid = 10
        resp, _ = _handle_request(_req("mesh_data"), state)
        r = resp["result"]
        assert r["eid"] == 10
