"""Tests for buffer decode daemon handlers (phase2-buffer-decode)."""

from __future__ import annotations

import struct
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import mock_renderdoc as mock_rd
import pytest
from conftest import rpc_request
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
            rpc_request(
                "cbuffer_decode", {"eid": 10, "set": 0, "binding": 0}, token="abcdef1234567890"
            ),
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
            rpc_request(
                "cbuffer_decode", {"eid": 10, "set": 0, "binding": 0}, token="abcdef1234567890"
            ),
            s,
        )
        assert resp["error"]["code"] == -32002

    def test_no_reflection(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request(
                "cbuffer_decode",
                {"eid": 10, "set": 0, "binding": 0, "stage": "vs"},
                token="abcdef1234567890",
            ),
            state,
        )
        assert resp["error"]["code"] == -32001

    def test_invalid_binding(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request(
                "cbuffer_decode", {"eid": 10, "set": 0, "binding": 99}, token="abcdef1234567890"
            ),
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
            rpc_request(
                "cbuffer_decode", {"eid": 10, "set": 0, "binding": 0}, token="abcdef1234567890"
            ),
            state,
        )
        r = resp["result"]
        assert r["variables"][0]["name"] == "light.dir"
        assert r["variables"][1]["name"] == "light.color"


class TestVbufferDecode:
    def test_happy_path(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("vbuffer_decode", {"eid": 10}, token="abcdef1234567890"), state
        )
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
        resp, _ = _handle_request(
            rpc_request("vbuffer_decode", {"eid": 10}, token="abcdef1234567890"), s
        )
        assert resp["error"]["code"] == -32002

    def test_no_vertex_inputs(self, state: DaemonState) -> None:
        state.adapter.controller.GetPipelineState()._vertex_inputs = []
        resp, _ = _handle_request(
            rpc_request("vbuffer_decode", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["columns"] == []
        assert r["vertices"] == []


class TestIbufferDecode:
    def test_happy_path_u16(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("ibuffer_decode", {"eid": 10}, token="abcdef1234567890"), state
        )
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
        resp, _ = _handle_request(
            rpc_request("ibuffer_decode", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["format"] == "uint32"
        assert r["indices"] == [0, 1, 2]

    def test_no_adapter(self) -> None:
        s = DaemonState(
            capture="t.rdc",
            current_eid=0,
            token="abcdef1234567890",
        )
        resp, _ = _handle_request(
            rpc_request("ibuffer_decode", {"eid": 10}, token="abcdef1234567890"), s
        )
        assert resp["error"]["code"] == -32002

    def test_no_index_buffer(self, state: DaemonState) -> None:
        pipe = state.adapter.controller.GetPipelineState()
        pipe._ibuffer = BoundVBuffer(
            resourceId=ResourceId(0),
            byteOffset=0,
            byteSize=0,
            byteStride=0,
        )
        resp, _ = _handle_request(
            rpc_request("ibuffer_decode", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["format"] == "none"
        assert r["indices"] == []


# --- P2-MAINT-1: buffer decode helper unit tests ---


class TestDecodeFloatComponents:
    """Unit tests for _decode_float_components helper."""

    def test_comp_width_4_float(self) -> None:
        from rdc.handlers.buffer import _decode_float_components

        data = struct.pack("<3f", 1.0, 2.0, 3.0)
        result = _decode_float_components(data, 0, 4, 3)
        assert result == pytest.approx([1.0, 2.0, 3.0])

    def test_comp_width_4_single(self) -> None:
        from rdc.handlers.buffer import _decode_float_components

        data = struct.pack("<f", -0.5)
        result = _decode_float_components(data, 0, 4, 1)
        assert result == pytest.approx([-0.5])

    def test_comp_width_2_half(self) -> None:
        from rdc.handlers.buffer import _decode_float_components

        data = struct.pack("<2e", 1.0, 0.5)
        result = _decode_float_components(data, 0, 2, 2)
        assert result == pytest.approx([1.0, 0.5])

    def test_comp_width_1_byte_normalize(self) -> None:
        from rdc.handlers.buffer import _decode_float_components

        data = bytes([0, 128, 255])
        result = _decode_float_components(data, 0, 1, 3)
        assert result == pytest.approx([0.0, 128 / 255.0, 1.0])

    def test_comp_width_1_single(self) -> None:
        from rdc.handlers.buffer import _decode_float_components

        data = bytes([200])
        result = _decode_float_components(data, 0, 1, 1)
        assert result == pytest.approx([200 / 255.0])

    def test_comp_count_4(self) -> None:
        from rdc.handlers.buffer import _decode_float_components

        data = struct.pack("<4f", 1.0, 2.0, 3.0, 4.0)
        result = _decode_float_components(data, 0, 4, 4)
        assert result == pytest.approx([1.0, 2.0, 3.0, 4.0])

    def test_with_offset(self) -> None:
        from rdc.handlers.buffer import _decode_float_components

        data = b"\x00\x00\x00\x00" + struct.pack("<2f", 5.0, 6.0)
        result = _decode_float_components(data, 4, 4, 2)
        assert result == pytest.approx([5.0, 6.0])


class TestDecodeIndexBuffer:
    """Unit tests for _decode_index_buffer helper."""

    def test_stride_2_uint16(self) -> None:
        from rdc.handlers.buffer import _decode_index_buffer

        data = struct.pack("<4H", 0, 1, 2, 3)
        result = _decode_index_buffer(data, 2)
        assert result == [0, 1, 2, 3]

    def test_stride_4_uint32(self) -> None:
        from rdc.handlers.buffer import _decode_index_buffer

        data = struct.pack("<3I", 100, 200, 300)
        result = _decode_index_buffer(data, 4)
        assert result == [100, 200, 300]

    def test_stride_1_byte(self) -> None:
        from rdc.handlers.buffer import _decode_index_buffer

        data = bytes([0, 5, 10])
        result = _decode_index_buffer(data, 1)
        assert result == [0, 5, 10]


class TestVbufferDecodeGolden:
    """Golden-value comparison: refactored vbuffer_decode matches original output."""

    def test_vbuffer_golden(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("vbuffer_decode", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        # 3 vertices, 5 components each (POSITION.xyz + TEXCOORD.xy)
        expected_v0 = [-1.0, -1.0, 0.0, 0.0, 0.0]
        expected_v1 = [1.0, -1.0, 0.0, 1.0, 0.0]
        expected_v2 = [0.0, 1.0, 0.0, 0.5, 1.0]
        assert r["vertices"][0] == pytest.approx(expected_v0)
        assert r["vertices"][1] == pytest.approx(expected_v1)
        assert r["vertices"][2] == pytest.approx(expected_v2)


class TestIbufferDecodeGolden:
    """Golden-value comparison: refactored ibuffer_decode matches original output."""

    def test_ibuffer_golden(self, state: DaemonState) -> None:
        resp, _ = _handle_request(
            rpc_request("ibuffer_decode", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["indices"] == [0, 1, 2]
        assert r["format"] == "uint16"


class TestMeshDataGolden:
    """Golden-value comparison: refactored mesh_data matches expected output."""

    def test_mesh_data_golden(self, state: DaemonState) -> None:
        """mesh_data with PostVS data returns correct vertices and indices."""
        vdata = struct.pack("<12f", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0)
        idata = struct.pack("<3H", 0, 1, 2)
        mesh = SimpleNamespace(
            vertexResourceId=ResourceId(99),
            vertexByteStride=16,
            vertexByteOffset=0,
            vertexByteSize=len(vdata),
            numIndices=3,
            indexResourceId=ResourceId(98),
            indexByteOffset=0,
            indexByteSize=len(idata),
            indexByteStride=2,
            format=ResourceFormat(name="R32G32B32A32_FLOAT", compByteWidth=4, compCount=4),
            topology="TriangleList",
        )
        orig_get = state.adapter.controller.GetBufferData
        orig_postvs = state.adapter.controller.GetPostVSData

        def _get(rid: Any, offset: int, length: int) -> bytes:
            if int(rid) == 99:
                return vdata
            if int(rid) == 98:
                return idata
            return orig_get(rid, offset, length)

        state.adapter.controller.GetBufferData = _get
        state.adapter.controller.GetPostVSData = lambda inst, view, stage: mesh
        resp, _ = _handle_request(
            rpc_request("mesh_data", {"eid": 10, "stage": "vs-out"}, token="abcdef1234567890"),
            state,
        )
        r = resp["result"]
        assert r["vertex_count"] == 3
        assert r["vertices"][0] == pytest.approx([1.0, 2.0, 3.0, 4.0])
        assert r["vertices"][1] == pytest.approx([5.0, 6.0, 7.0, 8.0])
        assert r["vertices"][2] == pytest.approx([9.0, 10.0, 11.0, 12.0])
        assert r["indices"] == [0, 1, 2]

        # Restore
        state.adapter.controller.GetBufferData = orig_get
        state.adapter.controller.GetPostVSData = orig_postvs
