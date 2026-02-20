"""Tests for buffer decode daemon handlers (phase2-buffer-decode)."""

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
    BoundVBuffer,
    ConstantBlock,
    Descriptor,
    MockPipeState,
    ResourceDescription,
    ResourceFormat,
    ResourceId,
    ShaderReflection,
    ShaderStage,
    ShaderValue,
    ShaderVariable,
    VertexInputAttribute,
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


def _make_vbuffer_data() -> bytes:
    """3 vertices: POSITION (vec3) + TEXCOORD (vec2), stride=20."""
    verts = [
        (-1.0, -1.0, 0.0, 0.0, 0.0),
        (1.0, -1.0, 0.0, 1.0, 0.0),
        (0.0, 1.0, 0.0, 0.5, 1.0),
    ]
    data = b""
    for v in verts:
        data += struct.pack("<5f", *v)
    return data


def _make_ibuffer_data_u16() -> bytes:
    """3 uint16 indices: 0, 1, 2."""
    return struct.pack("<3H", 0, 1, 2)


def _make_ibuffer_data_u32() -> bytes:
    """3 uint32 indices: 0, 1, 2."""
    return struct.pack("<3I", 0, 1, 2)


@pytest.fixture()
def state(tmp_path: Path) -> DaemonState:
    pipe = MockPipeState()
    # Set up shader with reflection for cbuffer tests
    pipe._shaders[ShaderStage.Pixel] = ResourceId(100)
    refl = ShaderReflection(
        constantBlocks=[
            ConstantBlock(
                name="Params",
                byteSize=64,
                fixedBindSetOrSpace=0,
                fixedBindNumber=0,
            ),
        ],
    )
    pipe._reflections[ShaderStage.Pixel] = refl
    # Set up cbuffer descriptor for GetConstantBlock
    pipe._cbuffer_descriptors[(ShaderStage.Pixel, 0)] = Descriptor(
        resource=ResourceId(50),
    )

    # Vertex inputs for vbuffer test
    pipe._vertex_inputs = [
        VertexInputAttribute(
            name="POSITION",
            vertexBuffer=0,
            byteOffset=0,
            format=ResourceFormat(
                name="R32G32B32_FLOAT",
                compByteWidth=4,
                compCount=3,
            ),
        ),
        VertexInputAttribute(
            name="TEXCOORD",
            vertexBuffer=0,
            byteOffset=12,
            format=ResourceFormat(
                name="R32G32_FLOAT",
                compByteWidth=4,
                compCount=2,
            ),
        ),
    ]
    pipe._vbuffers = [
        BoundVBuffer(
            resourceId=ResourceId(42),
            byteOffset=0,
            byteSize=60,
            byteStride=20,
        ),
    ]
    pipe._ibuffer = BoundVBuffer(
        resourceId=ResourceId(43),
        byteOffset=0,
        byteSize=6,
        byteStride=2,
    )

    vbuf_data = _make_vbuffer_data()
    ibuf_data = _make_ibuffer_data_u16()
    light_val = ShaderValue(f32v=[0.5, 0.7, 0.0] + [0.0] * 13)
    intensity_val = ShaderValue(f32v=[1.0] + [0.0] * 15)
    cbuffer_vars = [
        ShaderVariable(
            name="lightDir",
            type="vec3",
            rows=1,
            columns=3,
            value=light_val,
        ),
        ShaderVariable(
            name="intensity",
            type="float",
            rows=1,
            columns=1,
            value=intensity_val,
        ),
    ]

    actions = _build_actions()
    resources = _build_resources()

    def _get_buffer_data(
        resource_id: Any,
        offset: int,
        length: int,
    ) -> bytes:
        rid = int(resource_id)
        if rid == 42:
            return vbuf_data
        if rid == 43:
            return ibuf_data
        return b""

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
        GetPostVSData=lambda inst, view, stage: SimpleNamespace(),
        GetBufferData=_get_buffer_data,
        GetCBufferVariableContents=lambda *args: cbuffer_vars,
        Shutdown=lambda: None,
    )

    s = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    s.adapter = RenderDocAdapter(controller=controller, version=(1, 41))
    s.max_eid = 10
    s.rd = mock_rd
    s.temp_dir = tmp_path
    s.vfs_tree = build_vfs_skeleton(actions, resources)
    return s


class TestCbufferDecode:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            _req("cbuffer_decode", eid=10, set=0, binding=0),
            state,
        )
        r = resp["result"]
        assert r["eid"] == 10
        assert r["set"] == 0
        assert r["binding"] == 0
        assert len(r["variables"]) == 2
        assert r["variables"][0]["name"] == "lightDir"
        assert r["variables"][0]["value"] == [0.5, 0.7, 0.0]
        assert r["variables"][1]["name"] == "intensity"
        assert r["variables"][1]["value"] == pytest.approx(1.0)

    def test_no_adapter(self) -> None:
        s = DaemonState(
            capture="t.rdc",
            current_eid=0,
            token="abcdef1234567890",
        )
        resp, _ = _handle_request(
            _req("cbuffer_decode", eid=10, set=0, binding=0),
            s,
        )
        assert resp["error"]["code"] == -32002

    def test_no_reflection(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            _req("cbuffer_decode", eid=10, set=0, binding=0, stage="vs"),
            state,
        )
        assert resp["error"]["code"] == -32001

    def test_invalid_binding(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            _req("cbuffer_decode", eid=10, set=0, binding=99),
            state,
        )
        assert resp["error"]["code"] == -32001

    def test_nested_variables(self, state: DaemonState) -> None:
        """Nested ShaderVariable members flatten with dot notation."""
        dir_val = ShaderValue(f32v=[1.0, 0.0, 0.0] + [0.0] * 13)
        color_val = ShaderValue(f32v=[1.0, 1.0, 1.0] + [0.0] * 13)
        nested = [
            ShaderVariable(
                name="light",
                type="struct",
                members=[
                    ShaderVariable(
                        name="dir",
                        type="vec3",
                        rows=1,
                        columns=3,
                        value=dir_val,
                    ),
                    ShaderVariable(
                        name="color",
                        type="vec3",
                        rows=1,
                        columns=3,
                        value=color_val,
                    ),
                ],
            ),
        ]
        # Override cbuffer return
        state.adapter.controller.GetCBufferVariableContents = lambda *args: nested
        resp, _ = _handle_request(
            _req("cbuffer_decode", eid=10, set=0, binding=0),
            state,
        )
        r = resp["result"]
        assert r["variables"][0]["name"] == "light.dir"
        assert r["variables"][1]["name"] == "light.color"


class TestVbufferDecode:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(_req("vbuffer_decode", eid=10), state)
        r = resp["result"]
        assert r["eid"] == 10
        assert len(r["columns"]) == 5  # 3 (POSITION) + 2 (TEXCOORD)
        assert r["columns"][0] == "POSITION.x"
        assert r["columns"][3] == "TEXCOORD.x"
        assert len(r["vertices"]) == 3
        # First vertex: POSITION (-1, -1, 0)
        assert r["vertices"][0][0] == pytest.approx(-1.0)
        assert r["vertices"][0][1] == pytest.approx(-1.0)
        assert r["vertices"][0][2] == pytest.approx(0.0)
        # First vertex: TEXCOORD (0, 0)
        assert r["vertices"][0][3] == pytest.approx(0.0)
        assert r["vertices"][0][4] == pytest.approx(0.0)

    def test_no_adapter(self) -> None:
        s = DaemonState(
            capture="t.rdc",
            current_eid=0,
            token="abcdef1234567890",
        )
        resp, _ = _handle_request(_req("vbuffer_decode", eid=10), s)
        assert resp["error"]["code"] == -32002

    def test_no_vertex_inputs(self, state: DaemonState) -> None:
        state.adapter.controller.GetPipelineState()._vertex_inputs = []
        resp, _ = _handle_request(_req("vbuffer_decode", eid=10), state)
        r = resp["result"]
        assert r["columns"] == []
        assert r["vertices"] == []


class TestIbufferDecode:
    def test_happy_path_u16(self, state: DaemonState) -> None:
        resp, _ = _handle_request(_req("ibuffer_decode", eid=10), state)
        r = resp["result"]
        assert r["eid"] == 10
        assert r["format"] == "uint16"
        assert r["indices"] == [0, 1, 2]

    def test_uint32(self, state: DaemonState) -> None:
        pipe = state.adapter.controller.GetPipelineState()
        pipe._ibuffer = BoundVBuffer(
            resourceId=ResourceId(44),
            byteOffset=0,
            byteSize=12,
            byteStride=4,
        )
        u32_data = _make_ibuffer_data_u32()
        orig_get = state.adapter.controller.GetBufferData

        def _get(rid: Any, offset: int, length: int) -> bytes:
            if int(rid) == 44:
                return u32_data
            return orig_get(rid, offset, length)

        state.adapter.controller.GetBufferData = _get
        resp, _ = _handle_request(_req("ibuffer_decode", eid=10), state)
        r = resp["result"]
        assert r["format"] == "uint32"
        assert r["indices"] == [0, 1, 2]

    def test_no_adapter(self) -> None:
        s = DaemonState(
            capture="t.rdc",
            current_eid=0,
            token="abcdef1234567890",
        )
        resp, _ = _handle_request(_req("ibuffer_decode", eid=10), s)
        assert resp["error"]["code"] == -32002

    def test_no_index_buffer(self, state: DaemonState) -> None:
        pipe = state.adapter.controller.GetPipelineState()
        pipe._ibuffer = BoundVBuffer(
            resourceId=ResourceId(0),
            byteOffset=0,
            byteSize=0,
            byteStride=0,
        )
        resp, _ = _handle_request(_req("ibuffer_decode", eid=10), state)
        r = resp["result"]
        assert r["format"] == "none"
        assert r["indices"] == []
