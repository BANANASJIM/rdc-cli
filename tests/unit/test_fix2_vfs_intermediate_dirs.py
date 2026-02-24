"""Tests for Fix 2: VFS bindings/cbuffer intermediate directories."""

from __future__ import annotations

from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    ConstantBlock,
    MockPipeState,
    ResourceDescription,
    ResourceId,
    ShaderReflection,
    ShaderResource,
)

from rdc.vfs.router import resolve_path
from rdc.vfs.tree_cache import build_vfs_skeleton, populate_draw_subtree


def _make_actions() -> list[ActionDescription]:
    return [
        ActionDescription(
            eventId=1,
            flags=ActionFlags.BeginPass,
            _name="Pass",
            children=[
                ActionDescription(
                    eventId=11,
                    flags=ActionFlags.Drawcall,
                    numIndices=3,
                    _name="Draw",
                ),
            ],
        ),
        ActionDescription(eventId=2, flags=ActionFlags.EndPass, _name="End"),
    ]


def _make_resources() -> list[ResourceDescription]:
    return [ResourceDescription(resourceId=ResourceId(1), name="Res")]


def _make_pipe_with_bindings() -> MockPipeState:
    state = MockPipeState()
    state._shaders[0] = ResourceId(100)  # VS
    state._shaders[4] = ResourceId(200)  # PS
    vs_refl = ShaderReflection(
        readOnlyResources=[
            ShaderResource(name="tex0", fixedBindSetOrSpace=0, fixedBindNumber=0),
            ShaderResource(name="tex1", fixedBindSetOrSpace=1, fixedBindNumber=0),
        ],
        constantBlocks=[
            ConstantBlock(name="ubo0", fixedBindSetOrSpace=0, fixedBindNumber=0),
            ConstantBlock(name="ubo1", fixedBindSetOrSpace=0, fixedBindNumber=1),
        ],
    )
    ps_refl = ShaderReflection(
        readOnlyResources=[
            ShaderResource(name="sampler", fixedBindSetOrSpace=0, fixedBindNumber=1),
        ],
        readWriteResources=[
            ShaderResource(name="storage", fixedBindSetOrSpace=2, fixedBindNumber=0),
        ],
        constantBlocks=[
            ConstantBlock(name="params", fixedBindSetOrSpace=1, fixedBindNumber=0),
        ],
    )
    state._reflections[0] = vs_refl
    state._reflections[4] = ps_refl
    return state


class TestRouterIntermediateDirs:
    def test_cbuffer_set_dir(self) -> None:
        m = resolve_path("/draws/11/cbuffer/0")
        assert m is not None
        assert m.kind == "dir"
        assert m.args == {"eid": 11, "set": 0}

    def test_bindings_set_dir(self) -> None:
        m = resolve_path("/draws/11/bindings/0")
        assert m is not None
        assert m.kind == "dir"
        assert m.args == {"eid": 11, "set": 0}

    def test_cbuffer_leaf_still_works(self) -> None:
        m = resolve_path("/draws/11/cbuffer/0/3")
        assert m is not None
        assert m.kind == "leaf"
        assert m.handler == "cbuffer_decode"
        assert m.args == {"eid": 11, "set": 0, "binding": 3}

    def test_bindings_dir_still_works(self) -> None:
        m = resolve_path("/draws/11/bindings")
        assert m is not None
        assert m.kind == "dir"


class TestPopulateBindings:
    def test_bindings_children_populated(self) -> None:
        skel = build_vfs_skeleton(_make_actions(), _make_resources())
        pipe = _make_pipe_with_bindings()
        populate_draw_subtree(skel, 11, pipe)
        bindings = skel.static["/draws/11/bindings"]
        assert len(bindings.children) > 0
        assert "0" in bindings.children

    def test_bindings_set_nodes_created(self) -> None:
        skel = build_vfs_skeleton(_make_actions(), _make_resources())
        pipe = _make_pipe_with_bindings()
        populate_draw_subtree(skel, 11, pipe)
        # VS has sets 0,1; PS has sets 0,2
        bindings = skel.static["/draws/11/bindings"]
        assert "0" in bindings.children
        assert "1" in bindings.children
        assert "2" in bindings.children

    def test_cbuffer_children_populated(self) -> None:
        skel = build_vfs_skeleton(_make_actions(), _make_resources())
        pipe = _make_pipe_with_bindings()
        populate_draw_subtree(skel, 11, pipe)
        cbuffer = skel.static["/draws/11/cbuffer"]
        assert len(cbuffer.children) > 0

    def test_cbuffer_set_has_binding_children(self) -> None:
        skel = build_vfs_skeleton(_make_actions(), _make_resources())
        pipe = _make_pipe_with_bindings()
        populate_draw_subtree(skel, 11, pipe)
        # Set 0 has bindings 0 and 1 (from VS constantBlocks)
        set_node = skel.static["/draws/11/cbuffer/0"]
        assert "0" in set_node.children
        assert "1" in set_node.children

    def test_cbuffer_binding_is_leaf(self) -> None:
        skel = build_vfs_skeleton(_make_actions(), _make_resources())
        pipe = _make_pipe_with_bindings()
        populate_draw_subtree(skel, 11, pipe)
        leaf = skel.static["/draws/11/cbuffer/0/0"]
        assert leaf.kind == "leaf"

    def test_no_reflections_empty(self) -> None:
        skel = build_vfs_skeleton(_make_actions(), _make_resources())
        pipe = MockPipeState()
        populate_draw_subtree(skel, 11, pipe)
        assert skel.static["/draws/11/bindings"].children == []
        assert skel.static["/draws/11/cbuffer"].children == []

    def test_lru_eviction_cleans_bindings(self) -> None:
        skel = build_vfs_skeleton(_make_actions(), _make_resources())
        skel._lru_capacity = 1
        pipe = _make_pipe_with_bindings()
        populate_draw_subtree(skel, 11, pipe)
        assert len(skel.static["/draws/11/bindings"].children) > 0
        # Evict by populating another draw
        pipe2 = MockPipeState()
        pipe2._shaders[0] = ResourceId(100)
        pipe2._reflections[0] = ShaderReflection()
        # Need another draw eid in the skeleton
        from rdc.vfs.tree_cache import _DRAW_CHILDREN, VfsNode

        skel.static["/draws/99"] = VfsNode("99", "dir", list(_DRAW_CHILDREN))
        skel.static["/draws/99/shader"] = VfsNode("shader", "dir")
        skel.static["/draws/99/bindings"] = VfsNode("bindings", "dir")
        skel.static["/draws/99/cbuffer"] = VfsNode("cbuffer", "dir")
        skel.static["/draws/99/targets"] = VfsNode("targets", "dir")
        populate_draw_subtree(skel, 99, pipe2)
        assert skel.static["/draws/11/bindings"].children == []
        assert skel.static["/draws/11/cbuffer"].children == []
