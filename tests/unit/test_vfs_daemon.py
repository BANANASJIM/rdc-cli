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
    BufferDescription,
    MockPipeState,
    ResourceDescription,
    ResourceFormat,
    ResourceId,
    SDBasic,
    SDChunk,
    SDData,
    SDObject,
    ShaderReflection,
    ShaderResource,
    ShaderStage,
    StructuredFile,
    TextureDescription,
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


def _make_state_with_resources(pipe_state=None):
    """Build state with textures, buffers, and resource maps populated."""
    actions = _build_actions()
    sf = _build_sf()
    resources = [
        ResourceDescription(resourceId=ResourceId(100), name="tex0"),
        ResourceDescription(resourceId=ResourceId(200), name="buf0"),
    ]
    tex = TextureDescription(
        resourceId=ResourceId(100),
        width=1920,
        height=1080,
        format=ResourceFormat(name="R8G8B8A8_UNORM"),
    )
    buf = BufferDescription(resourceId=ResourceId(200), length=4096)
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
    state.vfs_tree = build_vfs_skeleton(
        actions,
        resources,
        textures=[tex],
        buffers=[buf],
        sf=sf,
    )
    state.tex_map = {100: tex}
    state.buf_map = {200: buf}
    state.res_names = {100: "tex0", 200: "buf0"}
    state.res_types = {100: "Texture2D", 200: "Buffer"}
    state.res_rid_map = {
        100: SimpleNamespace(byteSize=8294400),
        200: SimpleNamespace(byteSize=4096),
    }
    return state


class TestVfsLsLong:
    def test_long_false_unchanged(self):
        """long=False returns existing format without columns."""
        resp, _ = _handle_request(_req("vfs_ls", path="/draws"), _make_state())
        result = resp["result"]
        assert "columns" not in result
        assert "long" not in result
        for c in result["children"]:
            assert set(c.keys()) == {"name", "kind"}

    def test_long_passes(self):
        state = _make_state()
        resp, _ = _handle_request(_req("vfs_ls", path="/passes", long=True), state)
        result = resp["result"]
        assert result["long"] is True
        assert result["columns"] == ["NAME", "DRAWS", "DISPATCHES", "TRIANGLES"]
        assert len(result["children"]) > 0
        for c in result["children"]:
            assert "name" in c
            assert "draws" in c
            assert "dispatches" in c
            assert "triangles" in c

    def test_long_draws(self):
        state = _make_state()
        resp, _ = _handle_request(_req("vfs_ls", path="/draws", long=True), state)
        result = resp["result"]
        assert result["long"] is True
        assert result["columns"] == ["EID", "NAME", "TYPE", "TRIANGLES", "INSTANCES"]
        children = result["children"]
        assert len(children) == 2
        draw42 = next(c for c in children if c["name"] == "42")
        assert draw42["eid"] == 42
        assert draw42["type"] in ("Draw", "DrawIndexed")
        assert isinstance(draw42["triangles"], int)
        assert isinstance(draw42["instances"], int)

    def test_long_events(self):
        state = _make_state()
        resp, _ = _handle_request(_req("vfs_ls", path="/events", long=True), state)
        result = resp["result"]
        assert result["columns"] == ["EID", "NAME", "TYPE"]
        assert len(result["children"]) > 0
        for c in result["children"]:
            assert "eid" in c
            assert "type" in c

    def test_long_resources(self):
        state = _make_state_with_resources()
        resp, _ = _handle_request(_req("vfs_ls", path="/resources", long=True), state)
        result = resp["result"]
        assert result["columns"] == ["ID", "NAME", "TYPE", "SIZE"]
        children = result["children"]
        rid100 = next(c for c in children if c["name"] == "100")
        assert rid100["id"] == 100
        assert rid100["type"] == "Texture2D"
        assert rid100["size"] == 8294400

    def test_long_textures(self):
        state = _make_state_with_resources()
        resp, _ = _handle_request(_req("vfs_ls", path="/textures", long=True), state)
        result = resp["result"]
        assert result["columns"] == ["ID", "NAME", "WIDTH", "HEIGHT", "FORMAT"]
        children = result["children"]
        assert len(children) == 1
        tex = children[0]
        assert tex["width"] == 1920
        assert tex["height"] == 1080
        assert tex["format"] == "R8G8B8A8_UNORM"

    def test_long_buffers(self):
        state = _make_state_with_resources()
        resp, _ = _handle_request(_req("vfs_ls", path="/buffers", long=True), state)
        result = resp["result"]
        assert result["columns"] == ["ID", "NAME", "LENGTH"]
        children = result["children"]
        assert len(children) == 1
        assert children[0]["length"] == 4096

    def test_long_shaders(self):
        pipe = _make_pipe_with_shaders()
        refl_vs = ShaderReflection(
            resourceId=ResourceId(1),
            entryPoint="vs_main",
            readOnlyResources=[ShaderResource(), ShaderResource()],
            readWriteResources=[ShaderResource()],
        )
        refl_ps = ShaderReflection(
            resourceId=ResourceId(2),
            entryPoint="ps_main",
            readOnlyResources=[ShaderResource()],
        )
        pipe._reflections[ShaderStage.Vertex] = refl_vs
        pipe._reflections[ShaderStage.Pixel] = refl_ps
        state = _make_state(pipe_state=pipe)
        controller = state.adapter.controller
        controller.DisassembleShader = lambda p, r, t: "; disasm"
        controller.GetDisassemblyTargets = lambda verbose=False: ["SPIR-V"]
        resp, _ = _handle_request(_req("vfs_ls", path="/shaders", long=True), state)
        result = resp["result"]
        assert result["columns"] == ["ID", "STAGES", "ENTRY", "INPUTS", "OUTPUTS"]
        children = result["children"]
        assert len(children) == 2
        sid1 = next(c for c in children if c["id"] == 1)
        assert "vs" in sid1["stages"]
        assert sid1["inputs"] == 2
        assert sid1["outputs"] == 1

    def test_long_other_dir(self):
        state = _make_state()
        resp, _ = _handle_request(_req("vfs_ls", path="/counters", long=True), state)
        result = resp["result"]
        assert result["columns"] == ["NAME", "TYPE"]
        for c in result["children"]:
            assert "name" in c
            assert "type" in c

    def test_long_not_found_returns_error(self):
        state = _make_state()
        resp, _ = _handle_request(_req("vfs_ls", path="/nonexistent", long=True), state)
        assert resp["error"]["code"] == -32001

    def test_long_no_adapter_returns_error(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(_req("vfs_ls", path="/draws", long=True), state)
        assert resp["error"]["code"] == -32002

    def test_long_draws_triangles_computed(self):
        """Triangle count = (num_indices // 3) * num_instances."""
        state = _make_state()
        resp, _ = _handle_request(_req("vfs_ls", path="/draws", long=True), state)
        draw42 = next(c for c in resp["result"]["children"] if c["name"] == "42")
        # 3600 indices / 3 = 1200 triangles * 1 instance = 1200
        assert draw42["triangles"] == 1200

    def test_long_draws_type_str(self):
        """Draw type string uses _action_type_str."""
        state = _make_state()
        resp, _ = _handle_request(_req("vfs_ls", path="/draws", long=True), state)
        draw42 = next(c for c in resp["result"]["children"] if c["name"] == "42")
        assert draw42["type"] == "DrawIndexed"
        dispatch300 = next(c for c in resp["result"]["children"] if c["name"] == "300")
        assert dispatch300["type"] == "Dispatch"
