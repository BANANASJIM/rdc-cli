"""Tests for VFS daemon handlers: vfs_ls and vfs_tree."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    APIEvent,
    MockPipeState,
    ResourceDescription,
    ResourceId,
    SDBasic,
    SDChunk,
    SDData,
    SDObject,
    ShaderStage,
    StructuredFile,
)

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request
from rdc.vfs.tree_cache import build_vfs_skeleton


def _build_actions():
    shadow_begin = ActionDescription(
        eventId=10,
        flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
        _name="Shadow",
    )
    draw1 = ActionDescription(
        eventId=42,
        flags=ActionFlags.Drawcall | ActionFlags.Indexed,
        numIndices=3600,
        numInstances=1,
        _name="vkCmdDrawIndexed",
        events=[APIEvent(eventId=42, chunkIndex=0)],
    )
    shadow_marker = ActionDescription(
        eventId=41,
        flags=ActionFlags.NoFlags,
        _name="Shadow/Terrain",
        children=[draw1],
    )
    shadow_end = ActionDescription(
        eventId=50,
        flags=ActionFlags.EndPass | ActionFlags.PassBoundary,
        _name="EndPass",
    )
    dispatch = ActionDescription(eventId=300, flags=ActionFlags.Dispatch, _name="vkCmdDispatch")
    return [shadow_begin, shadow_marker, shadow_end, dispatch]


def _build_sf():
    return StructuredFile(
        chunks=[
            SDChunk(
                name="vkCmdDrawIndexed",
                children=[
                    SDObject(name="indexCount", data=SDData(basic=SDBasic(value=3600))),
                    SDObject(name="instanceCount", data=SDData(basic=SDBasic(value=1))),
                ],
            ),
        ]
    )


def _build_resources():
    return [
        ResourceDescription(resourceId=ResourceId(100), name="tex0"),
        ResourceDescription(resourceId=ResourceId(200), name="buf0"),
    ]


def _make_pipe_with_shaders():
    """Build a MockPipeState that reports active VS and PS stages."""
    pipe = MockPipeState()
    pipe._shaders[ShaderStage.Vertex] = ResourceId(1)
    pipe._shaders[ShaderStage.Pixel] = ResourceId(2)
    return pipe


def _make_state(pipe_state=None):
    actions = _build_actions()
    sf = _build_sf()
    resources = _build_resources()
    pipe = pipe_state or MockPipeState()
    controller = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: resources,
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        GetPipelineState=lambda: pipe,
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: sf,
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
    )
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=controller, version=(1, 33))
    state.structured_file = sf
    state.api_name = "Vulkan"
    state.max_eid = 300
    state.vfs_tree = build_vfs_skeleton(actions, resources, sf=sf)
    return state


def _req(method, **params):
    p = {"_token": "tok"}
    p.update(params)
    return {"id": 1, "method": method, "params": p}


class TestVfsLs:
    def test_root(self):
        resp, _ = _handle_request(_req("vfs_ls", path="/"), _make_state())
        result = resp["result"]
        assert result["path"] == "/"
        assert result["kind"] == "dir"
        names = [c["name"] for c in result["children"]]
        assert "draws" in names
        assert "events" in names
        assert "resources" in names
        assert "current" in names

    def test_draws_dir(self):
        resp, _ = _handle_request(_req("vfs_ls", path="/draws"), _make_state())
        result = resp["result"]
        names = [c["name"] for c in result["children"]]
        assert "42" in names
        assert "300" in names

    def test_draw_eid(self):
        resp, _ = _handle_request(_req("vfs_ls", path="/draws/42"), _make_state())
        result = resp["result"]
        names = [c["name"] for c in result["children"]]
        assert "pipeline" in names
        assert "shader" in names
        assert "bindings" in names

    def test_draw_shader_dynamic_populate(self):
        pipe = _make_pipe_with_shaders()
        state = _make_state(pipe_state=pipe)
        resp, _ = _handle_request(_req("vfs_ls", path="/draws/42/shader"), state)
        result = resp["result"]
        names = [c["name"] for c in result["children"]]
        assert "vs" in names
        assert "ps" in names
        assert "hs" not in names

    def test_nonexistent_path(self):
        resp, _ = _handle_request(_req("vfs_ls", path="/nonexistent"), _make_state())
        assert resp["error"]["code"] == -32001
        assert "not found" in resp["error"]["message"]

    def test_current_no_eid(self):
        state = _make_state()
        state.current_eid = 0
        resp, _ = _handle_request(_req("vfs_ls", path="/current"), state)
        assert resp["error"]["code"] == -32002

    def test_no_adapter(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(_req("vfs_ls", path="/"), state)
        assert resp["error"]["code"] == -32002

    def test_current_resolves(self):
        pipe = _make_pipe_with_shaders()
        state = _make_state(pipe_state=pipe)
        state.current_eid = 42
        resp, _ = _handle_request(_req("vfs_ls", path="/current"), state)
        result = resp["result"]
        assert result["path"] == "/draws/42"
        names = [c["name"] for c in result["children"]]
        assert "pipeline" in names


class TestVfsTree:
    def test_root_depth1(self):
        resp, _ = _handle_request(_req("vfs_tree", path="/", depth=1), _make_state())
        result = resp["result"]
        assert result["path"] == "/"
        tree = result["tree"]
        assert tree["name"] == "/"
        assert tree["kind"] == "dir"
        names = [c["name"] for c in tree["children"]]
        assert "draws" in names
        # depth=1: children of root shown but their children are empty
        draws_node = next(c for c in tree["children"] if c["name"] == "draws")
        assert draws_node["children"] == []

    def test_draw_eid_depth2(self):
        resp, _ = _handle_request(_req("vfs_tree", path="/draws/42", depth=2), _make_state())
        result = resp["result"]
        tree = result["tree"]
        assert tree["name"] == "42"
        names = [c["name"] for c in tree["children"]]
        assert "pipeline" in names
        pipe_node = next(c for c in tree["children"] if c["name"] == "pipeline")
        pipe_children = [c["name"] for c in pipe_node["children"]]
        assert "summary" in pipe_children

    def test_depth_zero(self):
        resp, _ = _handle_request(_req("vfs_tree", path="/", depth=0), _make_state())
        assert resp["error"]["code"] == -32602
        assert "depth must be 1-8" in resp["error"]["message"]

    def test_depth_nine(self):
        resp, _ = _handle_request(_req("vfs_tree", path="/", depth=9), _make_state())
        assert resp["error"]["code"] == -32602
        assert "depth must be 1-8" in resp["error"]["message"]

    def test_nonexistent_path(self):
        resp, _ = _handle_request(_req("vfs_tree", path="/nonexistent", depth=1), _make_state())
        assert resp["error"]["code"] == -32001

    def test_no_adapter(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(_req("vfs_tree", path="/", depth=1), state)
        assert resp["error"]["code"] == -32002

    def test_current_resolves(self):
        state = _make_state()
        state.current_eid = 42
        resp, _ = _handle_request(_req("vfs_tree", path="/current", depth=1), state)
        result = resp["result"]
        assert result["path"] == "/draws/42"

    def test_current_no_eid(self):
        state = _make_state()
        state.current_eid = 0
        resp, _ = _handle_request(_req("vfs_tree", path="/current", depth=1), state)
        assert resp["error"]["code"] == -32002


class TestVfsDynamicPopulateChildPath:
    """Verify dynamic populate triggers on child paths under /draws/<eid>/shader."""

    def test_ls_shader_child_triggers_populate(self):
        """vfs_ls on /draws/<eid>/shader/ps should auto-populate without prior ls on /shader."""
        pipe = _make_pipe_with_shaders()
        state = _make_state(pipe_state=pipe)
        resp, _ = _handle_request(_req("vfs_ls", path="/draws/42/shader/ps"), state)
        result = resp["result"]
        assert result["kind"] == "dir"
        names = [c["name"] for c in result["children"]]
        assert "disasm" in names
        assert "source" in names

    def test_tree_shader_triggers_populate(self):
        """vfs_tree on /draws/<eid>/shader should trigger populate."""
        pipe = _make_pipe_with_shaders()
        state = _make_state(pipe_state=pipe)
        resp, _ = _handle_request(_req("vfs_tree", path="/draws/42/shader", depth=2), state)
        result = resp["result"]
        tree = result["tree"]
        names = [c["name"] for c in tree["children"]]
        assert "vs" in names
        assert "ps" in names

    def test_tree_draw_parent_populates_shader_subtree(self):
        """vfs_tree on /draws/<eid> with depth>=2 must populate shader children."""
        pipe = _make_pipe_with_shaders()
        state = _make_state(pipe_state=pipe)
        resp, _ = _handle_request(_req("vfs_tree", path="/draws/42", depth=3), state)
        tree = resp["result"]["tree"]
        shader_node = next(c for c in tree["children"] if c["name"] == "shader")
        stage_names = [c["name"] for c in shader_node["children"]]
        assert "vs" in stage_names
        assert "ps" in stage_names
