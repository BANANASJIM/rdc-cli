"""Tests for pipeline state daemon handlers (phase2-pipeline-state)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import mock_renderdoc as mock_rd
import pytest
from conftest import rpc_request
from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    BlendEquation,
    BoundVBuffer,
    ColorBlend,
    MeshFormat,
    MockPipeState,
    ResourceDescription,
    ResourceFormat,
    ResourceId,
    SamplerData,
    Scissor,
    ShaderStage,
    StencilFace,
    VertexInputAttribute,
    Viewport,
)

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request
from rdc.vfs.tree_cache import build_vfs_skeleton


def _build_actions():
    return [
        ActionDescription(
            eventId=10,
            flags=ActionFlags.Drawcall,
            numIndices=3,
            _name="Draw",
        ),
    ]


def _build_resources():
    return [ResourceDescription(resourceId=ResourceId(1), name="res0")]


@pytest.fixture()
def state(tmp_path: Path) -> DaemonState:
    pipe = MockPipeState()
    pipe._viewport = Viewport(x=0, y=0, width=1920, height=1080, minDepth=0.0, maxDepth=1.0)
    pipe._scissor = Scissor(x=0, y=0, width=1920, height=1080, enabled=True)
    pipe._color_blends = [
        ColorBlend(
            enabled=True,
            colorBlend=BlendEquation(source="SrcAlpha", destination="InvSrcAlpha", operation="Add"),
            alphaBlend=BlendEquation(source="One", destination="Zero", operation="Add"),
            writeMask=0xF,
        )
    ]
    pipe._stencil = (
        StencilFace(function="LessEqual", passOperation="Replace"),
        StencilFace(),
    )
    pipe._vertex_inputs = [
        VertexInputAttribute(
            name="POSITION",
            format=ResourceFormat(name="R32G32B32_FLOAT", compByteWidth=4, compCount=3),
        ),
        VertexInputAttribute(
            name="TEXCOORD",
            vertexBuffer=0,
            byteOffset=12,
            format=ResourceFormat(name="R32G32_FLOAT", compByteWidth=4, compCount=2),
        ),
    ]
    pipe._samplers = {
        ShaderStage.Pixel: [SamplerData(filter="Anisotropic", maxAnisotropy=16)],
    }
    pipe._vbuffers = [
        BoundVBuffer(
            resourceId=ResourceId(42),
            byteOffset=0,
            byteSize=4096,
            byteStride=20,
        ),
    ]
    pipe._ibuffer = BoundVBuffer(
        resourceId=ResourceId(43),
        byteOffset=0,
        byteSize=1024,
        byteStride=2,
    )

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
        GetPostVSData=lambda inst, view, stage: MeshFormat(
            numIndices=3, vertexByteStride=20, topology="TriangleList"
        ),
        Shutdown=lambda: None,
    )

    s = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    s.adapter = RenderDocAdapter(controller=controller, version=(1, 41))
    s.max_eid = 10
    s.rd = mock_rd
    s.temp_dir = tmp_path
    s.vfs_tree = build_vfs_skeleton(actions, resources)
    return s


class TestPipeTopology:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("pipe_topology", {"eid": 10}, token="abcdef1234567890"), state
        )
        result = resp["result"]
        assert result["topology"] == "TriangleList"
        assert result["eid"] == 10

    def test_no_adapter(self) -> None:
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(
            rpc_request("pipe_topology", {"eid": 10}, token="abcdef1234567890"), s
        )
        assert resp["error"]["code"] == -32002


class TestPipeViewport:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("pipe_viewport", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["width"] == 1920.0
        assert r["height"] == 1080.0
        assert r["minDepth"] == 0.0
        assert r["maxDepth"] == 1.0


class TestPipeScissor:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("pipe_scissor", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["width"] == 1920
        assert r["height"] == 1080
        assert r["enabled"] is True


class TestPipeBlend:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("pipe_blend", {"eid": 10}, token="abcdef1234567890"), state
        )
        blends = resp["result"]["blends"]
        assert len(blends) == 1
        assert blends[0]["enabled"] is True
        assert blends[0]["srcColor"] == "SrcAlpha"
        assert blends[0]["dstColor"] == "InvSrcAlpha"
        assert blends[0]["colorOp"] == "Add"


class TestPipeStencil:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("pipe_stencil", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["front"]["function"] == "LessEqual"
        assert r["front"]["passOperation"] == "Replace"
        assert r["back"]["function"] == "AlwaysTrue"


class TestPipeVinputs:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("pipe_vinputs", {"eid": 10}, token="abcdef1234567890"), state
        )
        inputs = resp["result"]["inputs"]
        assert len(inputs) == 2
        assert inputs[0]["name"] == "POSITION"
        assert "R32G32B32_FLOAT" in inputs[0]["format"]
        assert inputs[1]["name"] == "TEXCOORD"

    def test_empty(self, state: DaemonState) -> None:
        state.adapter.controller.GetPipelineState()._vertex_inputs = []
        resp, _ = _handle_request(
            rpc_request("pipe_vinputs", {"eid": 10}, token="abcdef1234567890"), state
        )
        assert resp["result"]["inputs"] == []


class TestPipeSamplers:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("pipe_samplers", {"eid": 10}, token="abcdef1234567890"), state
        )
        samplers = resp["result"]["samplers"]
        assert len(samplers) == 1
        assert samplers[0]["stage"] == "ps"
        assert samplers[0]["filter"] == "Anisotropic"
        assert samplers[0]["maxAnisotropy"] == 16


class TestPipeVbuffers:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("pipe_vbuffers", {"eid": 10}, token="abcdef1234567890"), state
        )
        vbs = resp["result"]["vbuffers"]
        assert len(vbs) == 1
        assert vbs[0]["resourceId"] == 42
        assert vbs[0]["byteStride"] == 20


class TestPipeIbuffer:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("pipe_ibuffer", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["resourceId"] == 43
        assert r["byteStride"] == 2


class TestPostvs:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("postvs", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["numIndices"] == 3
        assert r["topology"] == "TriangleList"
        assert r["vertexByteStride"] == 20
