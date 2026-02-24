"""Tests for Phase 2.6 shader API fixes and VFS directory population."""

from __future__ import annotations

import mock_renderdoc as rd
from conftest import make_daemon_state, rpc_request

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request
from rdc.vfs.tree_cache import build_vfs_skeleton

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state_with_ps() -> DaemonState:
    """DaemonState with a PS shader bound (ResourceId 101, disasm 'SPIR-V ...')."""
    ctrl = rd.MockReplayController()
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        entryPoint="main_ps",
    )
    ctrl._disasm_text[101] = "SPIR-V code here"
    ctrl._actions = [rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)]
    return make_daemon_state(ctrl=ctrl, capture="x.rdc")


# ---------------------------------------------------------------------------
# Issue 4: shader_source
# ---------------------------------------------------------------------------


def test_shader_source_uses_disassemble_shader() -> None:
    state = _make_state_with_ps()
    resp, running = _handle_request(rpc_request("shader_source", {"eid": 10, "stage": "ps"}), state)
    assert running
    r = resp["result"]
    assert r["source"] == "SPIR-V code here"
    assert r["has_debug_info"] is False
    assert r["files"] == []


def test_shader_source_no_reflection_returns_empty() -> None:
    state = _make_state_with_ps()
    # VS has no reflection bound
    resp, running = _handle_request(rpc_request("shader_source", {"eid": 10, "stage": "vs"}), state)
    assert running
    r = resp["result"]
    assert r["source"] == ""
    assert r["has_debug_info"] is False
    assert r["files"] == []


def test_shader_source_with_debug_info_returns_files() -> None:
    """When debugInfo.files is non-empty, return files and has_debug_info=True."""
    ctrl = rd.MockReplayController()
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        entryPoint="main_ps",
        debugInfo=rd.ShaderDebugInfo(
            files=[rd.SourceFile(filename="main.hlsl", contents="void main() {}")]
        ),
    )
    ctrl._disasm_text[101] = "SPIR-V code here"
    ctrl._actions = [rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)]

    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 100

    resp, running = _handle_request(rpc_request("shader_source", {"eid": 10, "stage": "ps"}), state)
    assert running
    r = resp["result"]
    assert r["has_debug_info"] is True
    assert len(r["files"]) == 1
    assert r["files"][0]["filename"] == "main.hlsl"
    assert r["files"][0]["source"] == "void main() {}"
    assert r["source"] == ""


def test_shader_source_with_multiple_debug_files() -> None:
    """Multiple debug files are all returned."""
    ctrl = rd.MockReplayController()
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        entryPoint="main_ps",
        debugInfo=rd.ShaderDebugInfo(
            files=[
                rd.SourceFile(filename="main.hlsl", contents="// main"),
                rd.SourceFile(filename="utils.hlsl", contents="// utils"),
            ]
        ),
    )
    ctrl._actions = [rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)]

    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 100

    resp, _ = _handle_request(rpc_request("shader_source", {"eid": 10, "stage": "ps"}), state)
    r = resp["result"]
    assert r["has_debug_info"] is True
    assert len(r["files"]) == 2
    filenames = {f["filename"] for f in r["files"]}
    assert filenames == {"main.hlsl", "utils.hlsl"}


def test_shader_source_compute_uses_compute_pipeline() -> None:
    ctrl = rd.MockReplayController()
    cs_id = rd.ResourceId(200)
    ctrl._pipe_state._shaders[rd.ShaderStage.Compute] = cs_id
    ctrl._pipe_state._reflections[rd.ShaderStage.Compute] = rd.ShaderReflection(
        resourceId=cs_id,
        entryPoint="main_cs",
    )
    ctrl._disasm_text[200] = "CS SPIR-V"
    ctrl._actions = [rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Dispatch)]

    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 100

    calls: list[tuple] = []
    orig = ctrl.DisassembleShader

    def _spy(pipeline: rd.ResourceId, refl: rd.ShaderReflection, target: str) -> str:
        calls.append((pipeline, refl, target))
        return orig(pipeline, refl, target)

    ctrl.DisassembleShader = _spy  # type: ignore[method-assign]

    resp, _ = _handle_request(rpc_request("shader_source", {"eid": 10, "stage": "cs"}), state)
    assert resp["result"]["source"] == "CS SPIR-V"
    assert calls, "DisassembleShader not called"
    pipeline_used = calls[0][0]
    # compute pipeline = ResourceId(2) per MockPipeState.GetComputePipelineObject
    assert int(pipeline_used) == 2


# ---------------------------------------------------------------------------
# Issue 4: shader_disasm
# ---------------------------------------------------------------------------


def test_shader_disasm_uses_disassemble_shader() -> None:
    state = _make_state_with_ps()
    resp, running = _handle_request(rpc_request("shader_disasm", {"eid": 10, "stage": "ps"}), state)
    assert running
    r = resp["result"]
    assert r["disasm"] == "SPIR-V code here"
    assert r["target"] == "SPIR-V"


def test_shader_disasm_with_explicit_target() -> None:
    state = _make_state_with_ps()
    calls: list[str] = []
    ctrl = state.adapter.controller
    orig = ctrl.DisassembleShader

    def _spy(pipeline: rd.ResourceId, refl: rd.ShaderReflection, target: str) -> str:
        calls.append(target)
        return orig(pipeline, refl, target)

    ctrl.DisassembleShader = _spy  # type: ignore[method-assign]

    resp, running = _handle_request(
        rpc_request("shader_disasm", {"eid": 10, "stage": "ps", "target": "GLSL"}), state
    )
    assert running
    assert resp["result"]["target"] == "GLSL"
    assert calls == ["GLSL"]


def test_shader_disasm_no_reflection_returns_empty() -> None:
    state = _make_state_with_ps()
    resp, running = _handle_request(rpc_request("shader_disasm", {"eid": 10, "stage": "vs"}), state)
    assert running
    r = resp["result"]
    assert r["disasm"] == ""


# ---------------------------------------------------------------------------
# shader_constants structured variables
# ---------------------------------------------------------------------------


def _make_state_with_cbuffer() -> DaemonState:
    """DaemonState with PS shader + one cbuffer containing a variable."""
    ctrl = rd.MockReplayController()
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._entry_points[rd.ShaderStage.Pixel] = "main_ps"
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        entryPoint="main_ps",
        constantBlocks=[rd.ConstantBlock(name="Globals", fixedBindNumber=0, byteSize=64)],
    )
    ctrl._pipe_state._cbuffer_descriptors[(rd.ShaderStage.Pixel, 0)] = rd.Descriptor(
        resource=rd.ResourceId(500),
        byteOffset=0,
        byteSize=64,
    )
    ctrl._cbuffer_variables[(rd.ShaderStage.Pixel, 0)] = [
        rd.ShaderVariable(
            name="g_Color",
            type="float4",
            rows=1,
            columns=4,
            value=rd.ShaderValue(f32v=[1.0, 0.5, 0.0, 1.0] + [0.0] * 12),
        ),
    ]
    ctrl._actions = [rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)]
    return make_daemon_state(ctrl=ctrl, capture="x.rdc")


def test_shader_constants_returns_structured_variables() -> None:
    state = _make_state_with_cbuffer()
    resp, running = _handle_request(
        rpc_request("shader_constants", {"eid": 10, "stage": "ps"}), state
    )
    assert running
    r = resp["result"]
    assert r["constants"][0]["name"] == "Globals"
    assert len(r["constants"][0]["variables"]) == 1
    v = r["constants"][0]["variables"][0]
    assert v["name"] == "g_Color"
    assert v["type"] == "float4"
    assert v["value"] == [1.0, 0.5, 0.0, 1.0]
    assert "data" not in r["constants"][0]


def test_shader_constants_struct_variable_recurses() -> None:
    """Struct ShaderVariable with members recurses into children."""
    ctrl = rd.MockReplayController()
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._entry_points[rd.ShaderStage.Pixel] = "main_ps"
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        entryPoint="main_ps",
        constantBlocks=[rd.ConstantBlock(name="Params", fixedBindNumber=0)],
    )
    ctrl._pipe_state._cbuffer_descriptors[(rd.ShaderStage.Pixel, 0)] = rd.Descriptor(
        resource=rd.ResourceId(500),
    )
    child_a = rd.ShaderVariable(
        name="x",
        type="float",
        rows=1,
        columns=1,
        value=rd.ShaderValue(f32v=[3.14] + [0.0] * 15),
    )
    child_b = rd.ShaderVariable(
        name="y",
        type="float",
        rows=1,
        columns=1,
        value=rd.ShaderValue(f32v=[2.71] + [0.0] * 15),
    )
    parent = rd.ShaderVariable(name="s", type="struct", members=[child_a, child_b])
    ctrl._cbuffer_variables[(rd.ShaderStage.Pixel, 0)] = [parent]
    ctrl._actions = [rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)]

    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 100

    resp, _ = _handle_request(rpc_request("shader_constants", {"eid": 10, "stage": "ps"}), state)
    r = resp["result"]
    v = r["constants"][0]["variables"][0]
    assert v["name"] == "s"
    assert v["value"] is None
    assert len(v["members"]) == 2
    assert v["members"][0]["name"] == "x"
    assert v["members"][0]["value"] == [3.14]
    assert v["members"][1]["name"] == "y"
    assert v["members"][1]["value"] == [2.71]


def test_shader_constants_empty_cbuffer() -> None:
    """Cbuffer with no variables returns empty list."""
    ctrl = rd.MockReplayController()
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._entry_points[rd.ShaderStage.Pixel] = "main_ps"
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        entryPoint="main_ps",
        constantBlocks=[rd.ConstantBlock(name="Empty", fixedBindNumber=0)],
    )
    ctrl._pipe_state._cbuffer_descriptors[(rd.ShaderStage.Pixel, 0)] = rd.Descriptor(
        resource=rd.ResourceId(500),
    )
    # No _cbuffer_variables entry -> returns []
    ctrl._actions = [rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)]

    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 100

    resp, _ = _handle_request(rpc_request("shader_constants", {"eid": 10, "stage": "ps"}), state)
    r = resp["result"]
    assert r["constants"][0]["variables"] == []


def test_shader_constants_multiple_cbuffers() -> None:
    """Multiple constant blocks are each enumerated."""
    ctrl = rd.MockReplayController()
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._entry_points[rd.ShaderStage.Pixel] = "main_ps"
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        entryPoint="main_ps",
        constantBlocks=[
            rd.ConstantBlock(name="CB0", fixedBindNumber=0),
            rd.ConstantBlock(name="CB1", fixedBindNumber=1),
        ],
    )
    for i in range(2):
        ctrl._pipe_state._cbuffer_descriptors[(rd.ShaderStage.Pixel, i)] = rd.Descriptor(
            resource=rd.ResourceId(500 + i),
        )
    ctrl._cbuffer_variables[(rd.ShaderStage.Pixel, 0)] = [
        rd.ShaderVariable(
            name="a", type="float", rows=1, columns=1, value=rd.ShaderValue(f32v=[1.0] + [0.0] * 15)
        ),
    ]
    ctrl._cbuffer_variables[(rd.ShaderStage.Pixel, 1)] = [
        rd.ShaderVariable(
            name="b", type="float", rows=1, columns=1, value=rd.ShaderValue(f32v=[2.0] + [0.0] * 15)
        ),
    ]
    ctrl._actions = [rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)]

    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 100

    resp, _ = _handle_request(rpc_request("shader_constants", {"eid": 10, "stage": "ps"}), state)
    r = resp["result"]
    assert len(r["constants"]) == 2
    assert r["constants"][0]["name"] == "CB0"
    assert r["constants"][0]["variables"][0]["name"] == "a"
    assert r["constants"][1]["name"] == "CB1"
    assert r["constants"][1]["variables"][0]["name"] == "b"


def test_shader_constants_calls_get_cbuffer_variable_contents() -> None:
    """GetCBufferVariableContents is called (not GetConstantBuffer)."""
    state = _make_state_with_cbuffer()
    ctrl = state.adapter.controller
    calls: list[tuple] = []
    orig = ctrl.GetCBufferVariableContents

    def _spy(*args: object) -> list:
        calls.append(args)
        return orig(*args)

    ctrl.GetCBufferVariableContents = _spy  # type: ignore[method-assign]

    resp, _ = _handle_request(rpc_request("shader_constants", {"eid": 10, "stage": "ps"}), state)
    assert "result" in resp
    assert len(calls) == 1
    assert not hasattr(ctrl, "GetConstantBuffer")


# ---------------------------------------------------------------------------
# Issue 5: /shaders triggers cache build
# ---------------------------------------------------------------------------


def _make_state_with_vfs() -> DaemonState:
    """State with VFS tree and a single draw action + PS shader."""
    ctrl = rd.MockReplayController()
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        entryPoint="main_ps",
    )
    ctrl._disasm_text[101] = "SPIR-V shader"
    draw = rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)
    ctrl._actions = [draw]
    return make_daemon_state(ctrl=ctrl, capture="x.rdc", vfs_tree=build_vfs_skeleton([draw], []))


def test_vfs_ls_shaders_triggers_cache_build() -> None:
    state = _make_state_with_vfs()
    assert not state._shader_cache_built

    resp, running = _handle_request(rpc_request("vfs_ls", {"path": "/shaders"}), state)
    assert running
    assert "result" in resp
    assert state._shader_cache_built
    children = [c["name"] for c in resp["result"]["children"]]
    assert "101" in children


def test_vfs_ls_shaders_no_double_build() -> None:
    state = _make_state_with_vfs()
    _handle_request(rpc_request("vfs_ls", {"path": "/shaders"}), state)
    assert state._shader_cache_built

    build_count = [0]
    orig = state.adapter.controller.DisassembleShader

    def _counted(*args: object) -> str:
        build_count[0] += 1
        return orig(*args)  # type: ignore[arg-type]

    state.adapter.controller.DisassembleShader = _counted  # type: ignore[method-assign]
    _handle_request(rpc_request("vfs_ls", {"path": "/shaders"}), state)
    assert build_count[0] == 0, "Cache rebuilt on second call"


def test_vfs_tree_shaders_triggers_cache_build() -> None:
    state = _make_state_with_vfs()
    assert not state._shader_cache_built

    resp, running = _handle_request(
        rpc_request("vfs_tree", {"path": "/shaders", "depth": 1}), state
    )
    assert running
    assert "result" in resp
    assert state._shader_cache_built


# ---------------------------------------------------------------------------
# Issue 5b: /passes/*/draws/ populated
# ---------------------------------------------------------------------------


def _build_pass_actions() -> list[rd.ActionDescription]:
    """Single render pass containing two draws (EID 42 and 43)."""
    draw1 = rd.ActionDescription(eventId=42, flags=rd.ActionFlags.Drawcall, _name="Draw1")
    draw2 = rd.ActionDescription(eventId=43, flags=rd.ActionFlags.Drawcall, _name="Draw2")
    pass_begin = rd.ActionDescription(
        eventId=10,
        flags=rd.ActionFlags.BeginPass | rd.ActionFlags.PassBoundary,
        _name="MainPass",
        children=[draw1, draw2],
    )
    pass_end = rd.ActionDescription(
        eventId=50,
        flags=rd.ActionFlags.EndPass | rd.ActionFlags.PassBoundary,
        _name="EndPass",
    )
    return [pass_begin, pass_end]


def test_passes_draws_populated() -> None:
    actions = _build_pass_actions()
    tree = build_vfs_skeleton(actions, [])
    pass_names = tree.static["/passes"].children
    assert len(pass_names) == 1
    pass_name = pass_names[0]

    draws_node = tree.static.get(f"/passes/{pass_name}/draws")
    assert draws_node is not None
    assert "42" in draws_node.children
    assert "43" in draws_node.children


def test_passes_draws_alias_nodes_exist() -> None:
    actions = _build_pass_actions()
    tree = build_vfs_skeleton(actions, [])
    pass_name = tree.static["/passes"].children[0]

    node_42 = tree.static.get(f"/passes/{pass_name}/draws/42")
    assert node_42 is not None
    assert node_42.kind == "alias"

    node_43 = tree.static.get(f"/passes/{pass_name}/draws/43")
    assert node_43 is not None
    assert node_43.kind == "alias"


def test_passes_draws_excludes_out_of_range() -> None:
    """Draw at EID 300 (outside pass range) must not appear under pass draws."""
    actions = _build_pass_actions()
    dispatch_outside = rd.ActionDescription(
        eventId=300, flags=rd.ActionFlags.Dispatch, _name="OutsideDispatch"
    )
    actions.append(dispatch_outside)
    tree = build_vfs_skeleton(actions, [])
    pass_name = tree.static["/passes"].children[0]
    draws_node = tree.static[f"/passes/{pass_name}/draws"]
    assert "300" not in draws_node.children


def test_passes_draws_empty_when_no_draws_in_pass() -> None:
    pass_begin = rd.ActionDescription(
        eventId=10,
        flags=rd.ActionFlags.BeginPass | rd.ActionFlags.PassBoundary,
        _name="EmptyPass",
    )
    pass_end = rd.ActionDescription(
        eventId=11,
        flags=rd.ActionFlags.EndPass | rd.ActionFlags.PassBoundary,
        _name="EndPass",
    )
    marker = rd.ActionDescription(
        eventId=5,
        flags=rd.ActionFlags.SetMarker,
        _name="Marker",
    )
    actions = [pass_begin, marker, pass_end]
    tree = build_vfs_skeleton(actions, [])
    # No pass emitted since window has no draws
    assert tree.static["/passes"].children == []


def test_vfs_ls_passes_draws_via_daemon() -> None:
    """vfs_ls on /passes/<name>/draws returns the draw EIDs."""
    from types import SimpleNamespace

    actions = _build_pass_actions()
    ctrl = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: [],
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        GetPipelineState=lambda: rd.MockPipeState(),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: rd.StructuredFile(),
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
    )
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.api_name = "Vulkan"
    state.max_eid = 300
    state.vfs_tree = build_vfs_skeleton(actions, [])

    pass_name = state.vfs_tree.static["/passes"].children[0]
    resp, running = _handle_request(
        rpc_request("vfs_ls", {"path": f"/passes/{pass_name}/draws"}), state
    )
    assert running
    assert "result" in resp
    child_names = {c["name"] for c in resp["result"]["children"]}
    assert "42" in child_names
    assert "43" in child_names
