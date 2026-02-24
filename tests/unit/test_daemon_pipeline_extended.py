"""Tests for extended pipeline state handlers (phase2.6-pipeline-extended)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as mock_rd
from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    ConstantBlock,
    DepthStencilState,
    Descriptor,
    MockPipeState,
    MultisampleState,
    RasterizerState,
    ResourceDescription,
    ResourceId,
    ShaderReflection,
    ShaderStage,
    ShaderValue,
    ShaderVariable,
)

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request
from rdc.vfs.router import resolve_path
from rdc.vfs.tree_cache import _PIPELINE_CHILDREN, build_vfs_skeleton


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
    cbvars: dict[tuple[int, int], list[Any]] = {}

    def _get_cbuf(
        _pipe: Any,
        _sh: Any,
        stage: Any,
        _e: str,
        idx: int,
        _r: Any,
        _o: int,
        _s: int,
    ) -> list[Any]:
        return cbvars.get((int(stage), idx), [])

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
        _cbuffer_variables=cbvars,
        GetCBufferVariableContents=_get_cbuf,
    )
    s = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    s.adapter = RenderDocAdapter(controller=controller, version=(1, 41))
    s.max_eid = 10
    s.rd = mock_rd
    s.temp_dir = tmp_path
    s.vfs_tree = build_vfs_skeleton(actions, resources)
    return s


# ── VFS tree cache ────────────────────────────────────────────────────────────


class TestPipelineChildren:
    def test_new_children_in_list(self) -> None:
        for name in ("push-constants", "rasterizer", "depth-stencil", "msaa"):
            assert name in _PIPELINE_CHILDREN

    def test_tree_has_pipeline_nodes(self, tmp_path: Path) -> None:
        actions = _build_actions()
        resources = _build_resources()
        tree = build_vfs_skeleton(actions, resources)
        node = tree.static["/draws/10/pipeline"]
        for name in ("push-constants", "rasterizer", "depth-stencil", "msaa"):
            assert name in node.children
        for name in ("push-constants", "rasterizer", "depth-stencil", "msaa"):
            assert f"/draws/10/pipeline/{name}" in tree.static


# ── Router ────────────────────────────────────────────────────────────────────


class TestPipelineExtendedRoutes:
    def test_push_constants_route(self) -> None:
        m = resolve_path("/draws/10/pipeline/push-constants")
        assert m is not None
        assert m.kind == "leaf"
        assert m.handler == "pipe_push_constants"
        assert m.args["eid"] == 10

    def test_rasterizer_route(self) -> None:
        m = resolve_path("/draws/10/pipeline/rasterizer")
        assert m is not None
        assert m.handler == "pipe_rasterizer"
        assert m.args["eid"] == 10

    def test_depth_stencil_route(self) -> None:
        m = resolve_path("/draws/10/pipeline/depth-stencil")
        assert m is not None
        assert m.handler == "pipe_depth_stencil"
        assert m.args["eid"] == 10

    def test_msaa_route(self) -> None:
        m = resolve_path("/draws/10/pipeline/msaa")
        assert m is not None
        assert m.handler == "pipe_msaa"
        assert m.args["eid"] == 10

    def test_eid_coercion(self) -> None:
        for path, handler in (
            ("/draws/42/pipeline/push-constants", "pipe_push_constants"),
            ("/draws/42/pipeline/rasterizer", "pipe_rasterizer"),
            ("/draws/42/pipeline/depth-stencil", "pipe_depth_stencil"),
            ("/draws/42/pipeline/msaa", "pipe_msaa"),
        ):
            m = resolve_path(path)
            assert m is not None
            assert isinstance(m.args["eid"], int)
            assert m.args["eid"] == 42
            assert m.handler == handler


# ── pipe_push_constants ───────────────────────────────────────────────────────


class TestPipePushConstants:
    def test_no_adapter(self) -> None:
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(_req("pipe_push_constants", eid=10), s)
        assert resp["error"]["code"] == -32002

    def test_empty_when_no_shaders(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_push_constants", eid=10), s)
        assert "error" not in resp
        assert resp["result"]["push_constants"] == []
        assert resp["result"]["raw_bytes"] == ""

    def test_empty_when_all_buffer_backed(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        refl = ShaderReflection(
            resourceId=ResourceId(5),
            constantBlocks=[ConstantBlock(name="ubo", bufferBacked=True, byteSize=64)],
        )
        pipe._shaders[ShaderStage.Vertex] = ResourceId(5)
        pipe._reflections[ShaderStage.Vertex] = refl
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_push_constants", eid=10), s)
        assert resp["result"]["push_constants"] == []

    def test_single_stage_push_constants(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        cb = ConstantBlock(name="push_block", bufferBacked=False, byteSize=16)
        refl = ShaderReflection(resourceId=ResourceId(5), constantBlocks=[cb])
        pipe._shaders[ShaderStage.Vertex] = ResourceId(5)
        pipe._reflections[ShaderStage.Vertex] = refl
        pipe._cbuffer_descriptors[(ShaderStage.Vertex, 0)] = Descriptor(
            resource=ResourceId(100),
            byteSize=16,
        )
        val = ShaderValue()
        val.f32v = [1.0, 2.0, 3.0, 4.0] + [0.0] * 12
        var = ShaderVariable(name="color", type="vec4", rows=1, columns=4, value=val)
        s = _make_state(tmp_path, pipe)
        s.adapter.controller._cbuffer_variables[(ShaderStage.Vertex, 0)] = [var]
        resp, _ = _handle_request(_req("pipe_push_constants", eid=10), s)
        result = resp["result"]
        assert len(result["push_constants"]) == 1
        pc = result["push_constants"][0]
        assert pc["stage"] == "vs"
        assert pc["name"] == "push_block"
        assert pc["size"] == 16
        assert len(pc["variables"]) == 1
        assert pc["variables"][0]["name"] == "color"
        assert pc["variables"][0]["value"] == [1.0, 2.0, 3.0, 4.0]

    def test_multiple_stages(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        for stage, sid in ((ShaderStage.Vertex, 5), (ShaderStage.Pixel, 6)):
            cb = ConstantBlock(name="pc", bufferBacked=False, byteSize=8)
            refl = ShaderReflection(resourceId=ResourceId(sid), constantBlocks=[cb])
            pipe._shaders[stage] = ResourceId(sid)
            pipe._reflections[stage] = refl
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_push_constants", eid=10), s)
        stages = {pc["stage"] for pc in resp["result"]["push_constants"]}
        assert "vs" in stages
        assert "ps" in stages

    def test_raw_bytes_present(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe.pushconsts = b"\x01\x02\xab"
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_push_constants", eid=10), s)
        assert resp["result"]["raw_bytes"] == "0102ab"

    def test_raw_bytes_empty_when_no_attr(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        delattr(pipe, "pushconsts")
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_push_constants", eid=10), s)
        assert resp["result"]["raw_bytes"] == ""

    def test_mixed_buffer_backed_and_push(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        blocks = [
            ConstantBlock(name="ubo", bufferBacked=True, byteSize=64),
            ConstantBlock(name="pc", bufferBacked=False, byteSize=16),
        ]
        refl = ShaderReflection(resourceId=ResourceId(5), constantBlocks=blocks)
        pipe._shaders[ShaderStage.Vertex] = ResourceId(5)
        pipe._reflections[ShaderStage.Vertex] = refl
        pipe._cbuffer_descriptors[(ShaderStage.Vertex, 1)] = Descriptor(
            resource=ResourceId(200),
            byteSize=16,
        )
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_push_constants", eid=10), s)
        pcs = resp["result"]["push_constants"]
        assert len(pcs) == 1
        assert pcs[0]["name"] == "pc"


# ── pipe_rasterizer ───────────────────────────────────────────────────────────


class TestPipeRasterizer:
    def test_no_adapter(self) -> None:
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(_req("pipe_rasterizer", eid=10), s)
        assert resp["error"]["code"] == -32002

    def test_happy_path(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe.rasterizer = RasterizerState(frontCCW=True, lineWidth=1.5)
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_rasterizer", eid=10), s)
        r = resp["result"]
        assert r["eid"] == 10
        assert r["frontCCW"] is True
        assert r["lineWidth"] == 1.5

    def test_enum_fields_serialized_as_name(self, tmp_path: Path) -> None:
        from mock_renderdoc import CullMode, FillMode

        pipe = MockPipeState()
        pipe.rasterizer = RasterizerState(
            fillMode=FillMode("Wireframe"),
            cullMode=CullMode("None"),
        )
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_rasterizer", eid=10), s)
        r = resp["result"]
        assert r["fillMode"] == "Wireframe"
        assert r["cullMode"] == "None"

    def test_no_rasterizer_attribute(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        del pipe.rasterizer
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_rasterizer", eid=10), s)
        assert resp["result"] == {"eid": 10}

    def test_depth_bias_fields(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe.rasterizer = RasterizerState(
            depthBiasEnable=True,
            depthBiasConstantFactor=2.0,
            depthBiasClamp=0.5,
            depthBiasSlopeFactor=1.5,
        )
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_rasterizer", eid=10), s)
        r = resp["result"]
        assert r["depthBiasEnable"] is True
        assert r["depthBiasConstantFactor"] == 2.0
        assert r["depthBiasClamp"] == 0.5
        assert r["depthBiasSlopeFactor"] == 1.5


# ── pipe_depth_stencil ────────────────────────────────────────────────────────


class TestPipeDepthStencil:
    def test_no_adapter(self) -> None:
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(_req("pipe_depth_stencil", eid=10), s)
        assert resp["error"]["code"] == -32002

    def test_happy_path(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe.depthStencil = DepthStencilState(
            depthTestEnable=True,
            depthWriteEnable=True,
            depthBoundsEnable=False,
            minDepthBounds=0.0,
            maxDepthBounds=1.0,
            stencilTestEnable=False,
        )
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_depth_stencil", eid=10), s)
        r = resp["result"]
        assert r["eid"] == 10
        assert r["depthTestEnable"] is True
        assert r["depthWriteEnable"] is True
        assert r["stencilTestEnable"] is False
        assert r["minDepthBounds"] == 0.0
        assert r["maxDepthBounds"] == 1.0

    def test_depth_function_serialized_as_name(self, tmp_path: Path) -> None:
        from mock_renderdoc import CompFunc

        pipe = MockPipeState()
        pipe.depthStencil = DepthStencilState(depthFunction=CompFunc("LessEqual"))
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_depth_stencil", eid=10), s)
        assert resp["result"]["depthFunction"] == "LessEqual"

    def test_no_depth_stencil_attribute(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        del pipe.depthStencil
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_depth_stencil", eid=10), s)
        assert resp["result"] == {"eid": 10}


# ── pipe_msaa ─────────────────────────────────────────────────────────────────


class TestPipeMsaa:
    def test_no_adapter(self) -> None:
        s = DaemonState(capture="t.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(_req("pipe_msaa", eid=10), s)
        assert resp["error"]["code"] == -32002

    def test_happy_path(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        pipe.multisample = MultisampleState(
            rasterSamples=4,
            sampleShadingEnable=True,
            minSampleShading=0.5,
            sampleMask=0xFFFF,
        )
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_msaa", eid=10), s)
        r = resp["result"]
        assert r["eid"] == 10
        assert r["rasterSamples"] == 4
        assert r["sampleShadingEnable"] is True
        assert r["minSampleShading"] == 0.5
        assert r["sampleMask"] == 0xFFFF

    def test_default_single_sample(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_msaa", eid=10), s)
        r = resp["result"]
        assert r["rasterSamples"] == 1

    def test_no_multisample_attribute(self, tmp_path: Path) -> None:
        pipe = MockPipeState()
        del pipe.multisample
        s = _make_state(tmp_path, pipe)
        resp, _ = _handle_request(_req("pipe_msaa", eid=10), s)
        assert resp["result"] == {"eid": 10}
