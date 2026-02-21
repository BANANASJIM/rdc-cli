"""Tests for VFS tree cache and formatter."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    BufferDescription,
    Descriptor,
    MockPipeState,
    ResourceDescription,
    ResourceId,
    ShaderReflection,
    TextureDescription,
)

from rdc.vfs.formatter import render_ls, render_tree_root
from rdc.vfs.tree_cache import VfsTree, build_vfs_skeleton, populate_draw_subtree

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_actions() -> list[ActionDescription]:
    """Build a small action tree: pass with 3 draws + standalone events."""
    return [
        ActionDescription(
            eventId=1,
            flags=ActionFlags.BeginPass,
            _name="ShadowPass",
            children=[
                ActionDescription(
                    eventId=10,
                    flags=ActionFlags.Drawcall,
                    numIndices=300,
                    _name="Draw #10",
                ),
                ActionDescription(
                    eventId=20,
                    flags=ActionFlags.Drawcall | ActionFlags.Indexed,
                    numIndices=600,
                    _name="Draw #20",
                ),
            ],
        ),
        ActionDescription(
            eventId=2,
            flags=ActionFlags.EndPass,
            _name="End ShadowPass",
        ),
        ActionDescription(
            eventId=3,
            flags=ActionFlags.BeginPass,
            _name="GBuffer",
            children=[
                ActionDescription(
                    eventId=30,
                    flags=ActionFlags.Drawcall,
                    numIndices=900,
                    _name="Draw #30",
                ),
            ],
        ),
        ActionDescription(
            eventId=4,
            flags=ActionFlags.EndPass,
            _name="End GBuffer",
        ),
        ActionDescription(
            eventId=50,
            flags=ActionFlags.Dispatch,
            _name="Dispatch #50",
        ),
    ]


def _make_resources() -> list[ResourceDescription]:
    return [
        ResourceDescription(resourceId=ResourceId(5), name="Albedo"),
        ResourceDescription(resourceId=ResourceId(10), name="DepthBuffer"),
    ]


def _make_pipe_state_vs_ps() -> MockPipeState:
    """PipeState with VS (idx=0) and PS (idx=4) active."""
    state = MockPipeState()
    state._shaders[0] = ResourceId(100)  # VS
    state._shaders[4] = ResourceId(200)  # PS
    state._reflections[0] = ShaderReflection()
    state._reflections[4] = ShaderReflection()
    return state


@pytest.fixture
def skeleton() -> VfsTree:
    return build_vfs_skeleton(_make_actions(), _make_resources())


# ---------------------------------------------------------------------------
# Static skeleton tests
# ---------------------------------------------------------------------------


class TestBuildVfsSkeleton:
    def test_root_children(self, skeleton: VfsTree) -> None:
        root = skeleton.static["/"]
        assert root.kind == "dir"
        expected = [
            "capabilities",
            "info",
            "stats",
            "log",
            "events",
            "draws",
            "by-marker",
            "passes",
            "resources",
            "textures",
            "buffers",
            "shaders",
            "counters",
            "current",
        ]
        assert root.children == expected

    def test_top_level_leaves(self, skeleton: VfsTree) -> None:
        for name in ("capabilities", "info", "stats", "log"):
            assert skeleton.static[f"/{name}"].kind == "leaf"

    def test_draws_children(self, skeleton: VfsTree) -> None:
        draws = skeleton.static["/draws"]
        assert draws.kind == "dir"
        # draw eids: 10, 20, 30 and dispatch 50
        assert "10" in draws.children
        assert "20" in draws.children
        assert "30" in draws.children
        assert "50" in draws.children

    def test_draw_node_structure(self, skeleton: VfsTree) -> None:
        node = skeleton.static["/draws/10"]
        assert node.kind == "dir"
        expected = [
            "pipeline",
            "shader",
            "bindings",
            "targets",
            "postvs",
            "cbuffer",
            "vbuffer",
            "ibuffer",
            "descriptors",
        ]
        assert node.children == expected

    def test_draw_pipeline_children(self, skeleton: VfsTree) -> None:
        pipe = skeleton.static["/draws/10/pipeline"]
        assert pipe.kind == "dir"
        expected = [
            "summary",
            "topology",
            "viewport",
            "scissor",
            "blend",
            "stencil",
            "vertex-inputs",
            "samplers",
            "vbuffers",
            "ibuffer",
            "push-constants",
            "rasterizer",
            "depth-stencil",
            "msaa",
        ]
        assert pipe.children == expected

    def test_draw_pipeline_leaves(self, skeleton: VfsTree) -> None:
        assert skeleton.static["/draws/10/pipeline/summary"].kind == "leaf"
        assert skeleton.static["/draws/10/pipeline/topology"].kind == "leaf"
        assert skeleton.static["/draws/10/pipeline/viewport"].kind == "leaf"

    def test_postvs_is_leaf(self, skeleton: VfsTree) -> None:
        assert skeleton.static["/draws/10/postvs"].kind == "leaf"

    def test_draw_shader_empty_initially(self, skeleton: VfsTree) -> None:
        shader = skeleton.static["/draws/10/shader"]
        assert shader.kind == "dir"
        assert shader.children == []

    def test_events_includes_all_eids(self, skeleton: VfsTree) -> None:
        events = skeleton.static["/events"]
        assert events.kind == "dir"
        for eid in ("1", "2", "3", "4", "10", "20", "30", "50"):
            assert eid in events.children
            assert skeleton.static[f"/events/{eid}"].kind == "leaf"

    def test_passes_children(self, skeleton: VfsTree) -> None:
        passes = skeleton.static["/passes"]
        assert passes.kind == "dir"
        assert "ShadowPass" in passes.children
        assert "GBuffer" in passes.children

    def test_pass_structure(self, skeleton: VfsTree) -> None:
        shadow = skeleton.static["/passes/ShadowPass"]
        assert shadow.children == ["info", "draws", "attachments"]
        assert skeleton.static["/passes/ShadowPass/info"].kind == "leaf"
        assert skeleton.static["/passes/ShadowPass/draws"].kind == "dir"

    def test_resources_children(self, skeleton: VfsTree) -> None:
        res = skeleton.static["/resources"]
        assert res.kind == "dir"
        assert "5" in res.children
        assert "10" in res.children

    def test_resource_has_info(self, skeleton: VfsTree) -> None:
        assert skeleton.static["/resources/5"].children == ["info", "usage"]
        assert skeleton.static["/resources/5/info"].kind == "leaf"

    def test_resource_has_usage(self, skeleton: VfsTree) -> None:
        assert skeleton.static["/resources/5/usage"].kind == "leaf"

    def test_current_is_alias(self, skeleton: VfsTree) -> None:
        assert skeleton.static["/current"].kind == "alias"

    def test_placeholder_dirs(self, skeleton: VfsTree) -> None:
        for name in ("by-marker", "shaders"):
            node = skeleton.static[f"/{name}"]
            assert node.kind == "dir"
            assert node.children == []

    def test_textures_buffers_empty_when_not_provided(self, skeleton: VfsTree) -> None:
        """No textures/buffers passed produces empty dirs."""
        assert skeleton.static["/textures"].kind == "dir"
        assert skeleton.static["/textures"].children == []
        assert skeleton.static["/buffers"].kind == "dir"
        assert skeleton.static["/buffers"].children == []

    def test_buffer_decode_nodes(self, skeleton: VfsTree) -> None:
        assert skeleton.static["/draws/10/cbuffer"].kind == "dir"
        assert skeleton.static["/draws/10/vbuffer"].kind == "leaf"
        assert skeleton.static["/draws/10/ibuffer"].kind == "leaf"

    def test_descriptors_in_draw_children(self, skeleton: VfsTree) -> None:
        assert "descriptors" in skeleton.static["/draws/10"].children

    def test_descriptors_is_leaf(self, skeleton: VfsTree) -> None:
        assert skeleton.static["/draws/10/descriptors"].kind == "leaf"

    def test_counters_dir(self, skeleton: VfsTree) -> None:
        node = skeleton.static["/counters"]
        assert node.kind == "dir"
        assert node.children == ["list"]

    def test_counters_list_leaf(self, skeleton: VfsTree) -> None:
        assert skeleton.static["/counters/list"].kind == "leaf"


# ---------------------------------------------------------------------------
# Texture / Buffer skeleton tests
# ---------------------------------------------------------------------------


def _make_typed_resources() -> list[ResourceDescription]:
    return [
        ResourceDescription(resourceId=ResourceId(5), name="Albedo"),
        ResourceDescription(resourceId=ResourceId(10), name="Normal"),
        ResourceDescription(resourceId=ResourceId(20), name="VtxBuf"),
    ]


def _make_textures() -> list[TextureDescription]:
    return [
        TextureDescription(resourceId=ResourceId(5), width=512, height=512, mips=4),
        TextureDescription(resourceId=ResourceId(10), width=256, height=256, mips=1),
    ]


def _make_buffers() -> list[BufferDescription]:
    return [
        BufferDescription(resourceId=ResourceId(20), length=4096),
    ]


class TestTextureBufferSkeleton:
    @pytest.fixture
    def typed_skeleton(self) -> VfsTree:
        return build_vfs_skeleton(
            _make_actions(),
            _make_typed_resources(),
            textures=_make_textures(),
            buffers=_make_buffers(),
        )

    def test_textures_children(self, typed_skeleton: VfsTree) -> None:
        assert typed_skeleton.static["/textures"].children == ["5", "10"]

    def test_texture_node_structure(self, typed_skeleton: VfsTree) -> None:
        node = typed_skeleton.static["/textures/5"]
        assert node.kind == "dir"
        assert node.children == ["info", "image.png", "mips", "data"]

    def test_texture_info_leaf(self, typed_skeleton: VfsTree) -> None:
        assert typed_skeleton.static["/textures/5/info"].kind == "leaf"

    def test_texture_image_leaf_bin(self, typed_skeleton: VfsTree) -> None:
        assert typed_skeleton.static["/textures/5/image.png"].kind == "leaf_bin"

    def test_texture_data_leaf_bin(self, typed_skeleton: VfsTree) -> None:
        assert typed_skeleton.static["/textures/5/data"].kind == "leaf_bin"

    def test_texture_mips_4(self, typed_skeleton: VfsTree) -> None:
        mips = typed_skeleton.static["/textures/5/mips"]
        assert mips.kind == "dir"
        assert mips.children == ["0.png", "1.png", "2.png", "3.png"]

    def test_texture_mip_leaf_bin(self, typed_skeleton: VfsTree) -> None:
        assert typed_skeleton.static["/textures/5/mips/0.png"].kind == "leaf_bin"

    def test_texture_mips_1(self, typed_skeleton: VfsTree) -> None:
        assert typed_skeleton.static["/textures/10/mips"].children == ["0.png"]

    def test_buffers_children(self, typed_skeleton: VfsTree) -> None:
        assert typed_skeleton.static["/buffers"].children == ["20"]

    def test_buffer_node_structure(self, typed_skeleton: VfsTree) -> None:
        node = typed_skeleton.static["/buffers/20"]
        assert node.kind == "dir"
        assert node.children == ["info", "data"]

    def test_buffer_info_leaf(self, typed_skeleton: VfsTree) -> None:
        assert typed_skeleton.static["/buffers/20/info"].kind == "leaf"

    def test_buffer_data_leaf_bin(self, typed_skeleton: VfsTree) -> None:
        assert typed_skeleton.static["/buffers/20/data"].kind == "leaf_bin"

    def test_unknown_resources_excluded(self) -> None:
        """Resources not in textures/buffers lists produce empty dirs."""
        resources = [
            ResourceDescription(resourceId=ResourceId(99), name="Mystery"),
        ]
        tree = build_vfs_skeleton(_make_actions(), resources)
        assert tree.static["/textures"].children == []
        assert tree.static["/buffers"].children == []


# ---------------------------------------------------------------------------
# Draw targets subtree tests
# ---------------------------------------------------------------------------


def _make_pipe_with_targets() -> MockPipeState:
    pipe = MockPipeState(
        output_targets=[
            Descriptor(resource=ResourceId(300)),
            Descriptor(resource=ResourceId(400)),
        ],
        depth_target=Descriptor(resource=ResourceId(500)),
    )
    pipe._shaders[0] = ResourceId(100)  # VS
    pipe._shaders[4] = ResourceId(200)  # PS
    return pipe


class TestDrawTargetsSubtree:
    @pytest.fixture
    def skel(self) -> VfsTree:
        return build_vfs_skeleton(_make_actions(), _make_resources())

    def test_targets_in_draw_children(self, skel: VfsTree) -> None:
        assert "targets" in skel.static["/draws/10"].children

    def test_targets_dir_exists(self, skel: VfsTree) -> None:
        assert skel.static["/draws/10/targets"].kind == "dir"

    def test_targets_populated(self, skel: VfsTree) -> None:
        pipe = _make_pipe_with_targets()
        populate_draw_subtree(skel, 10, pipe)
        assert skel.static["/draws/10/targets"].children == [
            "color0.png",
            "color1.png",
            "depth.png",
        ]

    def test_target_color_leaf_bin(self, skel: VfsTree) -> None:
        pipe = _make_pipe_with_targets()
        populate_draw_subtree(skel, 10, pipe)
        assert skel.static["/draws/10/targets/color0.png"].kind == "leaf_bin"

    def test_target_depth_leaf_bin(self, skel: VfsTree) -> None:
        pipe = _make_pipe_with_targets()
        populate_draw_subtree(skel, 10, pipe)
        assert skel.static["/draws/10/targets/depth.png"].kind == "leaf_bin"

    def test_no_targets(self, skel: VfsTree) -> None:
        pipe = MockPipeState()
        populate_draw_subtree(skel, 10, pipe)
        assert skel.static["/draws/10/targets"].children == []

    def test_color_only_no_depth(self, skel: VfsTree) -> None:
        pipe = MockPipeState(
            output_targets=[Descriptor(resource=ResourceId(300))],
        )
        populate_draw_subtree(skel, 10, pipe)
        assert skel.static["/draws/10/targets"].children == ["color0.png"]

    def test_lru_eviction_cleans_target_nodes(self) -> None:
        skel = build_vfs_skeleton(_make_actions(), _make_resources())
        skel._lru_capacity = 1
        pipe = _make_pipe_with_targets()

        populate_draw_subtree(skel, 10, pipe)
        assert "/draws/10/targets/color0.png" in skel.static

        # Evict eid 10 by populating eid 20
        populate_draw_subtree(skel, 20, pipe)
        assert skel.get_draw_subtree(10) is None
        assert "/draws/10/targets/color0.png" not in skel.static
        assert "/draws/10/targets/depth.png" not in skel.static
        assert skel.static["/draws/10/targets"].children == []
        # Eid 20 targets still present
        assert "/draws/20/targets/color0.png" in skel.static


# ---------------------------------------------------------------------------
# Dynamic subtree tests
# ---------------------------------------------------------------------------


class TestPopulateDrawSubtree:
    def test_discovers_active_stages(self, skeleton: VfsTree) -> None:
        pipe = _make_pipe_state_vs_ps()
        populate_draw_subtree(skeleton, 10, pipe)

        shader = skeleton.static["/draws/10/shader"]
        assert "vs" in shader.children
        assert "ps" in shader.children
        assert len(shader.children) == 2

    def test_stage_node_structure(self, skeleton: VfsTree) -> None:
        pipe = _make_pipe_state_vs_ps()
        populate_draw_subtree(skeleton, 10, pipe)

        ps = skeleton.static["/draws/10/shader/ps"]
        assert ps.kind == "dir"
        assert "disasm" in ps.children
        assert "source" in ps.children
        assert "reflect" in ps.children
        assert "constants" in ps.children

    def test_disasm_is_leaf(self, skeleton: VfsTree) -> None:
        pipe = _make_pipe_state_vs_ps()
        populate_draw_subtree(skeleton, 10, pipe)
        assert skeleton.static["/draws/10/shader/ps/disasm"].kind == "leaf"

    def test_returns_subtree_dict(self, skeleton: VfsTree) -> None:
        pipe = _make_pipe_state_vs_ps()
        subtree = populate_draw_subtree(skeleton, 10, pipe)
        assert "/draws/10/shader" in subtree
        assert "/draws/10/shader/vs" in subtree

    def test_cached_on_second_call(self, skeleton: VfsTree) -> None:
        pipe = _make_pipe_state_vs_ps()
        first = populate_draw_subtree(skeleton, 10, pipe)
        second = populate_draw_subtree(skeleton, 10, pipe)
        assert first is second

    def test_no_active_stages(self, skeleton: VfsTree) -> None:
        pipe = MockPipeState()
        subtree = populate_draw_subtree(skeleton, 20, pipe)
        assert skeleton.static["/draws/20/shader"].children == []
        assert subtree["/draws/20/shader"] == []


# ---------------------------------------------------------------------------
# LRU eviction tests
# ---------------------------------------------------------------------------


class TestLruEviction:
    def test_evicts_least_recently_used(self) -> None:
        tree = VfsTree(_lru_capacity=2)
        tree.set_draw_subtree(10, {"/a": ["x"]})
        tree.set_draw_subtree(20, {"/b": ["y"]})
        tree.set_draw_subtree(30, {"/c": ["z"]})

        assert tree.get_draw_subtree(10) is None
        assert tree.get_draw_subtree(20) is not None
        assert tree.get_draw_subtree(30) is not None

    def test_access_promotes_entry(self) -> None:
        """Accessing an entry prevents its eviction (true LRU)."""
        tree = VfsTree(_lru_capacity=2)
        tree.set_draw_subtree(10, {"/a": ["x"]})
        tree.set_draw_subtree(20, {"/b": ["y"]})
        # Access 10 to promote it
        tree.get_draw_subtree(10)
        # Insert 30 — should evict 20 (least recently used), not 10
        tree.set_draw_subtree(30, {"/c": ["z"]})
        assert tree.get_draw_subtree(10) is not None
        assert tree.get_draw_subtree(20) is None
        assert tree.get_draw_subtree(30) is not None

    def test_capacity_respected(self) -> None:
        tree = VfsTree(_lru_capacity=3)
        for eid in range(10):
            tree.set_draw_subtree(eid, {f"/{eid}": []})
        assert len(tree._draw_subtrees) == 3

    def test_integrated_with_populate(self) -> None:
        skeleton = build_vfs_skeleton(_make_actions(), _make_resources())
        skeleton._lru_capacity = 2
        pipe = _make_pipe_state_vs_ps()

        populate_draw_subtree(skeleton, 10, pipe)
        populate_draw_subtree(skeleton, 20, pipe)
        populate_draw_subtree(skeleton, 30, pipe)

        assert skeleton.get_draw_subtree(10) is None
        assert skeleton.get_draw_subtree(20) is not None
        assert skeleton.get_draw_subtree(30) is not None

    def test_eviction_cleans_static_nodes(self) -> None:
        """LRU eviction must remove dynamic nodes from static dict."""
        skeleton = build_vfs_skeleton(_make_actions(), _make_resources())
        skeleton._lru_capacity = 1
        pipe = _make_pipe_state_vs_ps()

        populate_draw_subtree(skeleton, 10, pipe)
        assert "/draws/10/shader/ps" in skeleton.static
        assert "/draws/10/shader/ps/disasm" in skeleton.static

        # Evict eid 10 by inserting eid 20
        populate_draw_subtree(skeleton, 20, pipe)
        assert skeleton.get_draw_subtree(10) is None
        # Dynamic nodes for eid 10 should be cleaned up
        assert "/draws/10/shader/ps" not in skeleton.static
        assert "/draws/10/shader/ps/disasm" not in skeleton.static
        # Shader dir should have empty children
        assert skeleton.static["/draws/10/shader"].children == []
        # Eid 20 should still have its nodes
        assert "/draws/20/shader/ps" in skeleton.static


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------


class TestRenderLs:
    def test_bare_names(self) -> None:
        children = [
            {"name": "pipeline", "kind": "dir"},
            {"name": "shader", "kind": "dir"},
            {"name": "info", "kind": "leaf"},
        ]
        result = render_ls(children)
        assert result == "pipeline\nshader\ninfo"

    def test_classify(self) -> None:
        children = [
            {"name": "pipeline", "kind": "dir"},
            {"name": "binary", "kind": "leaf_bin"},
            {"name": "current", "kind": "alias"},
            {"name": "info", "kind": "leaf"},
        ]
        result = render_ls(children, classify=True)
        assert result == "pipeline/\nbinary*\ncurrent@\ninfo"

    def test_empty(self) -> None:
        assert render_ls([]) == ""


class TestRenderTreeRoot:
    def test_simple_tree(self) -> None:
        node = {
            "name": "142",
            "kind": "dir",
            "children": [
                {
                    "name": "pipeline",
                    "kind": "dir",
                    "children": [
                        {"name": "summary", "kind": "leaf"},
                        {"name": "ia", "kind": "leaf"},
                        {"name": "rs", "kind": "leaf"},
                        {"name": "om", "kind": "leaf"},
                    ],
                },
                {"name": "shader", "kind": "dir", "children": []},
                {"name": "bindings", "kind": "dir", "children": []},
            ],
        }
        result = render_tree_root("/draws/142", node, max_depth=3)
        lines = result.split("\n")
        assert lines[0] == "/draws/142/"
        assert lines[1] == "\u251c\u2500\u2500 pipeline/"
        assert lines[2] == "\u2502   \u251c\u2500\u2500 summary"
        assert lines[5] == "\u2502   \u2514\u2500\u2500 om"
        assert lines[6] == "\u251c\u2500\u2500 shader/"
        assert lines[7] == "\u2514\u2500\u2500 bindings/"

    def test_max_depth_zero(self) -> None:
        node = {
            "name": "draws",
            "kind": "dir",
            "children": [{"name": "10", "kind": "dir"}],
        }
        result = render_tree_root("/draws", node, max_depth=0)
        assert result == "/draws/"

    def test_leaf_root(self) -> None:
        node = {"name": "info", "kind": "leaf"}
        result = render_tree_root("/info", node, max_depth=1)
        assert result == "/info"

    def test_leaf_bin_suffix(self) -> None:
        node = {
            "name": "vs",
            "kind": "dir",
            "children": [
                {"name": "disasm", "kind": "leaf"},
                {"name": "binary", "kind": "leaf_bin"},
            ],
        }
        result = render_tree_root("/draws/10/shader/vs", node, max_depth=1)
        lines = result.split("\n")
        assert lines[1] == "\u251c\u2500\u2500 disasm"
        assert lines[2] == "\u2514\u2500\u2500 binary*"

    def test_alias_suffix(self) -> None:
        node = {
            "name": "root",
            "kind": "dir",
            "children": [{"name": "current", "kind": "alias"}],
        }
        result = render_tree_root("/", node, max_depth=1)
        lines = result.split("\n")
        assert lines[1] == "\u2514\u2500\u2500 current@"
