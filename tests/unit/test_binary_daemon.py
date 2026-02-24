"""Tests for binary daemon infrastructure: temp dir lifecycle."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import mock_renderdoc as mock_rd
from conftest import rpc_request
from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    BufferDescription,
    Descriptor,
    MockPipeState,
    ResourceDescription,
    ResourceId,
    ShaderStage,
    TextureDescription,
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
    return [
        ResourceDescription(resourceId=ResourceId(1), name="res0"),
    ]


def _make_state_with_temp(tmp_path: Path):
    actions = _build_actions()
    resources = _build_resources()
    controller = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: resources,
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        GetPipelineState=lambda: SimpleNamespace(),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: None,
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
    )
    state = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    state.adapter = RenderDocAdapter(controller=controller, version=(1, 33))
    state.api_name = "Vulkan"
    state.max_eid = 10
    state.vfs_tree = build_vfs_skeleton(actions, resources)
    state.temp_dir = tmp_path
    return state


class TestTempDirLifecycle:
    def test_temp_dir_field_default_none(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        assert state.temp_dir is None

    def test_temp_dir_set_to_path(self, tmp_path: Path):
        state = _make_state_with_temp(tmp_path)
        assert state.temp_dir == tmp_path
        assert state.temp_dir.exists()

    def test_shutdown_cleans_temp_dir(self, tmp_path: Path):
        state = _make_state_with_temp(tmp_path)
        (tmp_path / "test.png").write_bytes(b"fake")
        assert (tmp_path / "test.png").exists()

        resp, running = _handle_request(rpc_request("shutdown", token="abcdef1234567890"), state)
        assert resp["result"]["ok"] is True
        assert running is False
        assert not tmp_path.exists()

    def test_shutdown_with_no_temp_dir(self):
        """Shutdown with temp_dir=None should not crash."""
        state = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
        resp, running = _handle_request(rpc_request("shutdown", token="abcdef1234567890"), state)
        assert resp["result"]["ok"] is True
        assert running is False


# ---------------------------------------------------------------------------
# Handler tests: typed resources + pipe state
# ---------------------------------------------------------------------------


def _build_typed_resources():
    return [
        ResourceDescription(resourceId=ResourceId(42), name="Albedo"),
        ResourceDescription(resourceId=ResourceId(7), name="VtxBuf"),
    ]


def _build_textures():
    return [
        TextureDescription(
            resourceId=ResourceId(42),
            width=512,
            height=512,
            mips=4,
        ),
    ]


def _build_buffers():
    return [
        BufferDescription(
            resourceId=ResourceId(7),
            length=4096,
        ),
    ]


def _assert_has_resource_id(texsave: object) -> None:
    assert hasattr(texsave, "resourceId"), "texsave must have resourceId"


def _make_handler_state(tmp_path: Path):
    """Create DaemonState with typed resources and a pipe state with targets."""
    actions = _build_actions()
    resources = _build_typed_resources()
    textures = _build_textures()
    buffers = _build_buffers()
    pipe = MockPipeState(
        output_targets=[
            Descriptor(resource=ResourceId(300)),
            Descriptor(resource=ResourceId(400)),
        ],
        depth_target=Descriptor(resource=ResourceId(500)),
    )
    pipe._shaders[ShaderStage.Vertex] = ResourceId(100)
    pipe._shaders[ShaderStage.Pixel] = ResourceId(200)

    controller = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: resources,
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        GetPipelineState=lambda: pipe,
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: None,
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
        SaveTexture=lambda texsave, path: (
            _assert_has_resource_id(texsave),
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100),
        ),
        GetTextureData=lambda rid, sub: b"\x00\xff" * 512,
        GetBufferData=lambda rid, offset, length: b"\xab\xcd" * 256,
    )
    state = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
    state.adapter = RenderDocAdapter(controller=controller, version=(1, 33))
    state.api_name = "Vulkan"
    state.max_eid = 10
    state.tex_map = {int(t.resourceId): t for t in textures}
    state.buf_map = {int(b.resourceId): b for b in buffers}
    state.res_names = {int(r.resourceId): r.name for r in resources}
    state.rd = mock_rd
    state.vfs_tree = build_vfs_skeleton(actions, resources, textures, buffers)
    state.temp_dir = tmp_path
    return state


class TestTexInfo:
    def test_happy_path(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("tex_info", {"id": 42}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["id"] == 42
        assert r["name"] == "Albedo"
        assert r["width"] == 512
        assert r["height"] == 512
        assert r["mips"] == 4
        assert "format" in r
        assert "array_size" in r
        assert "type" in r
        assert "byte_size" in r
        assert "dimension" in r
        assert "creation_flags" in r

    def test_not_found(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("tex_info", {"id": 999}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001
        assert "999" in resp["error"]["message"]

    def test_no_adapter(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
        resp, _ = _handle_request(
            rpc_request("tex_info", {"id": 42}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32002


class TestTexExport:
    def test_happy_path_mip0(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("tex_export", {"id": 42, "mip": 0}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert "path" in r
        assert r["size"] > 0
        assert Path(r["path"]).exists()

    def test_happy_path_mip2(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("tex_export", {"id": 42, "mip": 2}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert "path" in r
        assert "mip2" in r["path"]

    def test_not_found(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("tex_export", {"id": 999}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001

    def test_mip_out_of_range(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("tex_export", {"id": 42, "mip": 10}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001
        assert "mip" in resp["error"]["message"]

    def test_no_temp_dir(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
        state.adapter = RenderDocAdapter(
            controller=SimpleNamespace(GetResources=lambda: []), version=(1, 33)
        )
        state.rd = mock_rd
        resp, _ = _handle_request(
            rpc_request("tex_export", {"id": 42}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32002
        assert "temp" in resp["error"]["message"]


class TestTexRaw:
    def test_happy_path(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("tex_raw", {"id": 42}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert "path" in r
        assert r["size"] > 0
        assert Path(r["path"]).exists()

    def test_not_found(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("tex_raw", {"id": 999}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001

    def test_no_temp_dir(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
        state.adapter = RenderDocAdapter(
            controller=SimpleNamespace(GetResources=lambda: []), version=(1, 33)
        )
        state.rd = mock_rd
        resp, _ = _handle_request(
            rpc_request("tex_raw", {"id": 42}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32002
        assert "temp" in resp["error"]["message"]


class TestBufInfo:
    def test_happy_path(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("buf_info", {"id": 7}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert r["id"] == 7
        assert r["name"] == "VtxBuf"
        assert "length" in r
        assert "creation_flags" in r
        assert "gpu_address" in r

    def test_not_found(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("buf_info", {"id": 999}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001


class TestBufRaw:
    def test_happy_path(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("buf_raw", {"id": 7}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert "path" in r
        assert r["size"] > 0
        assert Path(r["path"]).exists()

    def test_not_found(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("buf_raw", {"id": 999}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001

    def test_no_temp_dir(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="abcdef1234567890")
        state.adapter = RenderDocAdapter(
            controller=SimpleNamespace(GetResources=lambda: []), version=(1, 33)
        )
        resp, _ = _handle_request(
            rpc_request("buf_raw", {"id": 7}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32002


class TestRtExport:
    def test_happy_path(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("rt_export", {"eid": 10, "target": 0}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert "path" in r
        assert r["size"] > 0
        assert Path(r["path"]).exists()

    def test_no_color_targets(self, tmp_path):
        state = _make_handler_state(tmp_path)
        pipe = MockPipeState()
        state.adapter = RenderDocAdapter(
            controller=SimpleNamespace(
                GetRootActions=lambda: _build_actions(),
                GetResources=lambda: _build_typed_resources(),
                GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
                GetPipelineState=lambda: pipe,
                SetFrameEvent=lambda eid, force: None,
                Shutdown=lambda: None,
            ),
            version=(1, 33),
        )
        resp, _ = _handle_request(
            rpc_request("rt_export", {"eid": 10, "target": 0}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001
        assert "no color targets" in resp["error"]["message"]

    def test_target_out_of_range(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("rt_export", {"eid": 10, "target": 5}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001
        assert "out of range" in resp["error"]["message"]

    def test_eid_out_of_range(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("rt_export", {"eid": 99999, "target": 0}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32002


class TestRtDepth:
    def test_happy_path(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("rt_depth", {"eid": 10}, token="abcdef1234567890"), state
        )
        r = resp["result"]
        assert "path" in r
        assert r["size"] > 0
        assert Path(r["path"]).exists()

    def test_no_depth_target(self, tmp_path):
        state = _make_handler_state(tmp_path)
        pipe = MockPipeState(
            output_targets=[Descriptor(resource=ResourceId(300))],
        )
        state.adapter = RenderDocAdapter(
            controller=SimpleNamespace(
                GetRootActions=lambda: _build_actions(),
                GetResources=lambda: _build_typed_resources(),
                GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
                GetPipelineState=lambda: pipe,
                SetFrameEvent=lambda eid, force: None,
                Shutdown=lambda: None,
                SaveTexture=lambda texsave, path: Path(path).write_bytes(
                    b"\x89PNG" + b"\x00" * 100
                ),
            ),
            version=(1, 33),
        )
        resp, _ = _handle_request(
            rpc_request("rt_depth", {"eid": 10}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32001
        assert "no depth target" in resp["error"]["message"]

    def test_eid_out_of_range(self, tmp_path):
        state = _make_handler_state(tmp_path)
        resp, _ = _handle_request(
            rpc_request("rt_depth", {"eid": 99999}, token="abcdef1234567890"), state
        )
        assert resp["error"]["code"] == -32002
