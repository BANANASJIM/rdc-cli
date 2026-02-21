"""Tests for phase2.6-output-quality: _enum_name, _sanitize_size, client timeout."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as mock_rd  # noqa: E402
from mock_renderdoc import (  # noqa: E402
    ActionDescription,
    ActionFlags,
    BlendEquation,
    BoundVBuffer,
    ColorBlend,
    MeshFormat,
    MockPipeState,
    ResourceDescription,
    ResourceId,
    SamplerData,
    ShaderStage,
    StencilFace,
)

from rdc.adapter import RenderDocAdapter
from rdc.daemon_client import send_request
from rdc.daemon_server import DaemonState, _enum_name, _handle_request, _sanitize_size
from rdc.vfs.tree_cache import build_vfs_skeleton


def _req(method: str, **params: Any) -> dict[str, Any]:
    p: dict[str, Any] = {"_token": "abcdef1234567890"}
    p.update(params)
    return {"id": 1, "method": method, "params": p}


def _make_state(pipe: MockPipeState, tmp_path: Path) -> DaemonState:
    actions = [
        ActionDescription(eventId=10, flags=ActionFlags.Drawcall, numIndices=3, _name="Draw")
    ]
    resources = [ResourceDescription(resourceId=ResourceId(1), name="res0")]
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
            numIndices=3,
            vertexByteStride=20,
            topology=SimpleNamespace(name="TriangleList"),
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


class TestEnumName:
    def test_with_name_attr(self) -> None:
        obj = SimpleNamespace(name="TriangleList")
        assert _enum_name(obj) == "TriangleList"

    def test_plain_string(self) -> None:
        assert _enum_name("foo") == "foo"

    def test_plain_int(self) -> None:
        assert _enum_name(42) == 42

    def test_empty_string(self) -> None:
        assert _enum_name("") == ""

    def test_none(self) -> None:
        assert _enum_name(None) is None


class TestSanitizeSize:
    def test_normal_value(self) -> None:
        assert _sanitize_size(4096) == 4096

    def test_zero(self) -> None:
        assert _sanitize_size(0) == 0

    def test_uint_max(self) -> None:
        assert _sanitize_size((1 << 64) - 1) == "-"

    def test_just_below_uint_max(self) -> None:
        assert _sanitize_size((1 << 64) - 2) == (1 << 64) - 2


class TestClientTimeout:
    def test_default_timeout_is_30(self) -> None:
        sig = inspect.signature(send_request)
        assert sig.parameters["timeout"].default == 30.0


class TestPipeTopologyEnumName:
    def test_enum_name_not_repr(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe.GetPrimitiveTopology = lambda: SimpleNamespace(name="TriangleList")  # type: ignore[method-assign]
        state = _make_state(pipe, tmp_path)
        resp, _ = _handle_request(_req("pipe_topology", eid=10), state)
        topo = resp["result"]["topology"]
        assert topo == "TriangleList"
        assert "." not in topo


class TestPipeBlendEnumNames:
    def test_blend_fields_are_plain_names(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe._color_blends = [
            ColorBlend(
                enabled=True,
                colorBlend=BlendEquation(
                    source=SimpleNamespace(name="SrcAlpha"),  # type: ignore[arg-type]
                    destination=SimpleNamespace(name="InvSrcAlpha"),  # type: ignore[arg-type]
                    operation=SimpleNamespace(name="Add"),  # type: ignore[arg-type]
                ),
                alphaBlend=BlendEquation(
                    source=SimpleNamespace(name="One"),  # type: ignore[arg-type]
                    destination=SimpleNamespace(name="Zero"),  # type: ignore[arg-type]
                    operation=SimpleNamespace(name="Add"),  # type: ignore[arg-type]
                ),
                writeMask=0xF,
            )
        ]
        state = _make_state(pipe, tmp_path)
        resp, _ = _handle_request(_req("pipe_blend", eid=10), state)
        b = resp["result"]["blends"][0]
        assert b["srcColor"] == "SrcAlpha"
        assert b["dstColor"] == "InvSrcAlpha"
        assert b["colorOp"] == "Add"
        assert b["srcAlpha"] == "One"
        assert b["dstAlpha"] == "Zero"
        assert b["alphaOp"] == "Add"
        for f in ("srcColor", "dstColor", "colorOp", "srcAlpha", "dstAlpha", "alphaOp"):
            assert "." not in str(b[f])


class TestPipeStencilEnumNames:
    def test_stencil_fields_are_plain_names(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe._stencil = (
            StencilFace(
                failOperation=SimpleNamespace(name="Keep"),  # type: ignore[arg-type]
                depthFailOperation=SimpleNamespace(name="Keep"),  # type: ignore[arg-type]
                passOperation=SimpleNamespace(name="Replace"),  # type: ignore[arg-type]
                function=SimpleNamespace(name="LessEqual"),  # type: ignore[arg-type]
            ),
            StencilFace(
                failOperation=SimpleNamespace(name="Keep"),  # type: ignore[arg-type]
                depthFailOperation=SimpleNamespace(name="Keep"),  # type: ignore[arg-type]
                passOperation=SimpleNamespace(name="Keep"),  # type: ignore[arg-type]
                function=SimpleNamespace(name="AlwaysTrue"),  # type: ignore[arg-type]
            ),
        )
        state = _make_state(pipe, tmp_path)
        resp, _ = _handle_request(_req("pipe_stencil", eid=10), state)
        front = resp["result"]["front"]
        assert front["passOperation"] == "Replace"
        assert front["function"] == "LessEqual"
        assert "." not in str(front["failOperation"])
        back = resp["result"]["back"]
        assert back["function"] == "AlwaysTrue"


class TestPipeSamplersEnumNames:
    def test_sampler_address_fields_are_plain_names(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        sd = SamplerData(
            addressU=SimpleNamespace(name="Wrap"),  # type: ignore[arg-type]
            addressV=SimpleNamespace(name="Clamp"),  # type: ignore[arg-type]
            addressW=SimpleNamespace(name="Mirror"),  # type: ignore[arg-type]
            filter=SimpleNamespace(name="Linear"),  # type: ignore[arg-type]
            maxAnisotropy=1,
        )
        pipe._samplers = {ShaderStage.Pixel: [sd]}
        state = _make_state(pipe, tmp_path)
        resp, _ = _handle_request(_req("pipe_samplers", eid=10), state)
        s = resp["result"]["samplers"][0]
        assert s["addressU"] == "Wrap"
        assert s["addressV"] == "Clamp"
        assert s["addressW"] == "Mirror"
        assert s["filter"] == "Linear"
        for f in ("addressU", "addressV", "addressW", "filter"):
            assert "." not in str(s[f])


class TestPipeVbuffersUintMax:
    def test_uint_max_bytesize_shown_as_dash(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe._vbuffers = [
            BoundVBuffer(
                resourceId=ResourceId(42),
                byteOffset=0,
                byteSize=(1 << 64) - 1,
                byteStride=20,
            )
        ]
        state = _make_state(pipe, tmp_path)
        resp, _ = _handle_request(_req("pipe_vbuffers", eid=10), state)
        assert resp["result"]["vbuffers"][0]["byteSize"] == "-"

    def test_normal_bytesize_shown_as_int(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe._vbuffers = [
            BoundVBuffer(resourceId=ResourceId(42), byteOffset=0, byteSize=4096, byteStride=20)
        ]
        state = _make_state(pipe, tmp_path)
        resp, _ = _handle_request(_req("pipe_vbuffers", eid=10), state)
        assert resp["result"]["vbuffers"][0]["byteSize"] == 4096


class TestPipeIbufferUintMax:
    def test_uint_max_bytesize_shown_as_dash(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe._ibuffer = BoundVBuffer(
            resourceId=ResourceId(43), byteOffset=0, byteSize=(1 << 64) - 1, byteStride=4
        )
        state = _make_state(pipe, tmp_path)
        resp, _ = _handle_request(_req("pipe_ibuffer", eid=10), state)
        assert resp["result"]["byteSize"] == "-"

    def test_normal_bytesize_shown_as_int(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe._ibuffer = BoundVBuffer(
            resourceId=ResourceId(43), byteOffset=0, byteSize=1024, byteStride=4
        )
        state = _make_state(pipe, tmp_path)
        resp, _ = _handle_request(_req("pipe_ibuffer", eid=10), state)
        assert resp["result"]["byteSize"] == 1024
