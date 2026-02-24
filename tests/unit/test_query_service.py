"""Tests for query_service action tree traversal and stats aggregation."""

from __future__ import annotations

from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    APIEvent,
)

from rdc.services.query_service import (
    _build_pass_list,
    _friendly_pass_name,
    aggregate_stats,
    filter_by_pass,
    filter_by_pattern,
    filter_by_type,
    find_action_by_eid,
    get_pass_detail,
    get_top_draws,
    pipeline_row,
    walk_actions,
)


def _build_action_tree():
    shadow_begin = ActionDescription(
        eventId=10,
        flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
        _name="Shadow",
    )
    shadow_draw1 = ActionDescription(
        eventId=42,
        flags=ActionFlags.Drawcall | ActionFlags.Indexed,
        numIndices=3600,
        numInstances=1,
        _name="vkCmdDrawIndexed",
        events=[APIEvent(eventId=42, chunkIndex=0)],
    )
    shadow_draw2 = ActionDescription(
        eventId=45,
        flags=ActionFlags.Drawcall | ActionFlags.Indexed,
        numIndices=2400,
        numInstances=1,
        _name="vkCmdDrawIndexed",
        events=[APIEvent(eventId=45, chunkIndex=1)],
    )
    shadow_marker = ActionDescription(
        eventId=41,
        flags=ActionFlags.NoFlags,
        _name="Shadow/Terrain",
        children=[shadow_draw1, shadow_draw2],
    )
    shadow_end = ActionDescription(
        eventId=50,
        flags=ActionFlags.EndPass | ActionFlags.PassBoundary,
        _name="EndPass",
    )
    gbuffer_begin = ActionDescription(
        eventId=90,
        flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
        _name="GBuffer",
    )
    gbuffer_draw1 = ActionDescription(
        eventId=98,
        flags=ActionFlags.Drawcall | ActionFlags.Indexed,
        numIndices=3600,
        numInstances=1,
        _name="vkCmdDrawIndexed",
    )
    gbuffer_draw2 = ActionDescription(
        eventId=142,
        flags=ActionFlags.Drawcall | ActionFlags.Indexed,
        numIndices=10800,
        numInstances=1,
        _name="vkCmdDrawIndexed",
    )
    gbuffer_clear = ActionDescription(eventId=91, flags=ActionFlags.Clear, _name="vkCmdClear")
    gbuffer_marker = ActionDescription(
        eventId=97,
        flags=ActionFlags.NoFlags,
        _name="GBuffer/Floor",
        children=[gbuffer_draw1, gbuffer_draw2],
    )
    gbuffer_end = ActionDescription(
        eventId=200,
        flags=ActionFlags.EndPass | ActionFlags.PassBoundary,
        _name="EndPass",
    )
    dispatch = ActionDescription(eventId=300, flags=ActionFlags.Dispatch, _name="vkCmdDispatch")
    copy = ActionDescription(eventId=400, flags=ActionFlags.Copy, _name="vkCmdCopyBuffer")
    non_indexed = ActionDescription(
        eventId=500,
        flags=ActionFlags.Drawcall,
        numIndices=6,
        numInstances=1,
        _name="vkCmdDraw",
    )
    return [
        shadow_begin,
        shadow_marker,
        shadow_end,
        gbuffer_begin,
        gbuffer_clear,
        gbuffer_marker,
        gbuffer_end,
        dispatch,
        copy,
        non_indexed,
    ]


class TestWalkActions:
    def test_flatten_all(self):
        flat = walk_actions(_build_action_tree())
        eids = [a.eid for a in flat]
        assert 42 in eids and 142 in eids and 300 in eids

    def test_pass_assignment(self):
        by_eid = {a.eid: a for a in walk_actions(_build_action_tree())}
        assert by_eid[42].pass_name == "Shadow"
        assert by_eid[98].pass_name == "GBuffer"
        assert by_eid[300].pass_name == "-"

    def test_parent_marker(self):
        by_eid = {a.eid: a for a in walk_actions(_build_action_tree())}
        assert by_eid[42].parent_marker == "Shadow/Terrain"
        assert by_eid[98].parent_marker == "GBuffer/Floor"

    def test_depth(self):
        by_eid = {a.eid: a for a in walk_actions(_build_action_tree())}
        assert by_eid[10].depth == 0
        assert by_eid[42].depth == 1


class TestFilterByType:
    def test_draws(self):
        assert len(filter_by_type(walk_actions(_build_action_tree()), "draw")) == 5

    def test_dispatches(self):
        assert len(filter_by_type(walk_actions(_build_action_tree()), "dispatch")) == 1

    def test_clears(self):
        assert len(filter_by_type(walk_actions(_build_action_tree()), "clear")) == 1

    def test_copies(self):
        assert len(filter_by_type(walk_actions(_build_action_tree()), "copy")) == 1

    def test_unknown(self):
        assert filter_by_type(walk_actions(_build_action_tree()), "banana") == []


class TestFilterByPass:
    def test_shadow(self):
        shadow = filter_by_pass(walk_actions(_build_action_tree()), "Shadow")
        assert 42 in {a.eid for a in shadow}

    def test_case_insensitive(self):
        assert len(filter_by_pass(walk_actions(_build_action_tree()), "gbuffer")) > 0

    def test_nonexistent(self):
        assert filter_by_pass(walk_actions(_build_action_tree()), "Nope") == []


class TestFilterByPattern:
    def test_glob(self):
        assert len(filter_by_pattern(walk_actions(_build_action_tree()), "vkCmdDraw*")) >= 4

    def test_no_match(self):
        assert filter_by_pattern(walk_actions(_build_action_tree()), "ZZZ*") == []


class TestFindActionByEid:
    def test_top_level(self):
        assert find_action_by_eid(_build_action_tree(), 300).eventId == 300

    def test_nested(self):
        assert find_action_by_eid(_build_action_tree(), 142).eventId == 142

    def test_not_found(self):
        assert find_action_by_eid(_build_action_tree(), 99999) is None


class TestAggregateStats:
    def test_draw_counts(self):
        s = aggregate_stats(walk_actions(_build_action_tree()))
        assert s.total_draws == 5 and s.indexed_draws == 4 and s.non_indexed_draws == 1

    def test_dispatch(self):
        assert aggregate_stats(walk_actions(_build_action_tree())).dispatches == 1

    def test_clear(self):
        assert aggregate_stats(walk_actions(_build_action_tree())).clears == 1

    def test_copy(self):
        assert aggregate_stats(walk_actions(_build_action_tree())).copies == 1

    def test_per_pass(self):
        names = {p.name for p in aggregate_stats(walk_actions(_build_action_tree())).per_pass}
        assert "Shadow" in names and "GBuffer" in names

    def test_per_pass_draws(self):
        by = {p.name: p for p in aggregate_stats(walk_actions(_build_action_tree())).per_pass}
        assert by["Shadow"].draws == 2 and by["GBuffer"].draws == 2

    def test_triangles(self):
        assert aggregate_stats(walk_actions(_build_action_tree())).total_triangles > 0

    def test_empty(self):
        s = aggregate_stats([])
        assert s.total_draws == 0 and s.per_pass == []


class TestGetTopDraws:
    def test_sorted(self):
        top = get_top_draws(walk_actions(_build_action_tree()), limit=3)
        tris = [(a.num_indices // 3) * a.num_instances for a in top]
        assert tris == sorted(tris, reverse=True)

    def test_top_is_largest(self):
        assert get_top_draws(walk_actions(_build_action_tree()), limit=1)[0].eid == 142


def _build_pass_tree() -> list[ActionDescription]:
    """Hierarchical pass tree: draws are children of BeginPass nodes."""
    shadow_begin = ActionDescription(
        eventId=10, flags=ActionFlags.BeginPass | ActionFlags.PassBoundary, _name="Shadow"
    )
    shadow_begin.children = [
        ActionDescription(
            eventId=42,
            flags=ActionFlags.Drawcall | ActionFlags.Indexed,
            numIndices=3600,
            numInstances=1,
            _name="draw1",
        ),
        ActionDescription(
            eventId=55,
            flags=ActionFlags.Drawcall | ActionFlags.Indexed,
            numIndices=2400,
            numInstances=1,
            _name="draw2",
        ),
    ]
    shadow_end = ActionDescription(
        eventId=60, flags=ActionFlags.EndPass | ActionFlags.PassBoundary, _name="EndPass"
    )
    gbuffer_begin = ActionDescription(
        eventId=90, flags=ActionFlags.BeginPass | ActionFlags.PassBoundary, _name="GBuffer"
    )
    gbuffer_begin.children = [
        ActionDescription(
            eventId=98,
            flags=ActionFlags.Drawcall | ActionFlags.Indexed,
            numIndices=3600,
            numInstances=1,
            _name="draw3",
        ),
    ]
    gbuffer_end = ActionDescription(
        eventId=200, flags=ActionFlags.EndPass | ActionFlags.PassBoundary, _name="EndPass"
    )
    return [shadow_begin, shadow_end, gbuffer_begin, gbuffer_end]


class TestGetPassDetail:
    def test_by_index(self):
        result = get_pass_detail(_build_pass_tree(), None, 0)
        assert result is not None
        assert result["name"] == "Shadow"
        assert result["begin_eid"] == 10
        assert result["draws"] == 2

    def test_by_name(self):
        result = get_pass_detail(_build_pass_tree(), None, "GBuffer")
        assert result is not None
        assert result["name"] == "GBuffer"

    def test_by_name_case_insensitive(self):
        assert get_pass_detail(_build_pass_tree(), None, "gbuffer") is not None

    def test_index_out_of_range(self):
        assert get_pass_detail(_build_pass_tree(), None, 999) is None

    def test_name_not_found(self):
        assert get_pass_detail(_build_pass_tree(), None, "NoSuch") is None

    def test_empty_actions(self):
        assert get_pass_detail([], None, 0) is None

    def test_end_eid_includes_children(self):
        result = get_pass_detail(_build_pass_tree(), None, 0)
        assert result is not None
        assert result["end_eid"] >= 50

    def test_triangles_counted(self):
        result = get_pass_detail(_build_pass_tree(), None, 0)
        assert result is not None
        # shadow has draws with numIndices=3600 and 2400 → 1200+800 tris
        assert result["triangles"] == 2000


# ---------------------------------------------------------------------------
# Fix 2: filter_by_pass EID-range path
# ---------------------------------------------------------------------------


def _build_eid_range_tree() -> list[ActionDescription]:
    """Flat-sibling tree: BeginPass / draws / EndPass."""
    begin = ActionDescription(
        eventId=3,
        flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
        _name="vkCmdBeginRenderPass(C=Load)",
    )
    draw1 = ActionDescription(eventId=5, flags=ActionFlags.Drawcall, numIndices=3, _name="draw1")
    draw2 = ActionDescription(eventId=7, flags=ActionFlags.Drawcall, numIndices=3, _name="draw2")
    draw3 = ActionDescription(eventId=9, flags=ActionFlags.Drawcall, numIndices=3, _name="draw3")
    end = ActionDescription(
        eventId=10,
        flags=ActionFlags.EndPass | ActionFlags.PassBoundary,
        _name="EndPass",
    )
    return [begin, draw1, draw2, draw3, end]


def _build_marker_tree() -> list[ActionDescription]:
    """Tree with marker group inside BeginPass children."""
    begin = ActionDescription(
        eventId=3,
        flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
        _name="vkCmdBeginRenderPass(C=Load)",
    )
    draw = ActionDescription(eventId=5, flags=ActionFlags.Drawcall, numIndices=3, _name="draw")
    marker = ActionDescription(
        eventId=4,
        flags=ActionFlags.PushMarker,
        _name="Opaque objects",
        children=[draw],
    )
    begin.children = [marker]
    end = ActionDescription(
        eventId=10,
        flags=ActionFlags.EndPass | ActionFlags.PassBoundary,
        _name="EndPass",
    )
    return [begin, end]


class TestFilterByPassEidRange:
    def test_eid_range_semantic_name(self) -> None:
        actions = _build_eid_range_tree()
        flat = walk_actions(actions)
        draws = [a for a in flat if a.flags & 0x0002]
        # _build_pass_list produces "Colour Pass #1 (1 Target)" for single-color markerless pass
        result = filter_by_pass(draws, "Colour Pass #1 (1 Target)", actions=actions)
        assert len(result) == 3
        assert {a.eid for a in result} == {5, 7, 9}

    def test_eid_range_marker_name(self) -> None:
        actions = _build_marker_tree()
        flat = walk_actions(actions)
        draws = [a for a in flat if a.flags & 0x0002]
        result = filter_by_pass(draws, "Opaque objects", actions=actions)
        assert len(result) == 1
        assert result[0].eid == 5

    def test_name_not_found_fallback_empty(self) -> None:
        actions = _build_eid_range_tree()
        flat = walk_actions(actions)
        result = filter_by_pass(flat, "NonExistent", actions=actions)
        assert result == []

    def test_name_not_found_fallback_uses_pass_name(self) -> None:
        # fallback to a.pass_name when not found in _build_pass_list
        actions = _build_eid_range_tree()
        flat = walk_actions(actions)
        # pass_name is assigned from BeginPass name during walk
        # "vkCmdBeginRenderPass(C=Load)" won't match, so fallback triggers
        # Inject a FlatAction with matching pass_name to verify fallback works
        from rdc.services.query_service import FlatAction

        extra = FlatAction(eid=99, name="fake", flags=0x0002, pass_name="legacy-pass")
        result = filter_by_pass(flat + [extra], "legacy-pass", actions=actions)
        assert len(result) == 1
        assert result[0].eid == 99

    def test_no_actions_legacy_path(self) -> None:
        flat = walk_actions(_build_action_tree())
        result = filter_by_pass(flat, "Shadow")
        assert len(result) > 0
        assert all(a.pass_name == "Shadow" for a in result)


# ---------------------------------------------------------------------------
# Fix 4: _friendly_pass_name helper
# ---------------------------------------------------------------------------


class TestFriendlyPassName:
    def test_single_color_no_depth(self) -> None:
        assert _friendly_pass_name("vkCmdBeginRenderPass(C=Load)", 0) == "Colour Pass #1 (1 Target)"

    def test_multi_color_with_depth(self) -> None:
        assert (
            _friendly_pass_name("vkCmdBeginRenderPass(C=Load, C=Clear, D=Clear)", 2)
            == "Colour Pass #3 (2 Targets + Depth)"
        )

    def test_depth_only(self) -> None:
        assert _friendly_pass_name("vkCmdBeginRenderPass(D=Clear)", 0) == "Colour Pass #1 (Depth)"

    def test_unknown_api_no_crash(self) -> None:
        assert _friendly_pass_name("UnknownPassType()", 0) == "Colour Pass #1"

    def test_index_one_based(self) -> None:
        assert _friendly_pass_name("vkCmdBeginRenderPass(C=Load)", 2).startswith("Colour Pass #3")

    def test_always_returns_nonempty_string(self) -> None:
        assert len(_friendly_pass_name("", 0)) > 0


class TestBuildPassListFriendlyNames:
    def test_friendly_name_no_markers(self) -> None:
        """Markerless flat-sibling tree: name should be friendly, not raw API string."""
        begin = ActionDescription(
            eventId=1,
            flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
            _name="vkCmdBeginRenderPass(C=Load, D=Clear)",
        )
        draw = ActionDescription(eventId=2, flags=ActionFlags.Drawcall, numIndices=3, _name="d")
        end = ActionDescription(
            eventId=3, flags=ActionFlags.EndPass | ActionFlags.PassBoundary, _name="EndPass"
        )
        passes = _build_pass_list([begin, draw, end])
        assert len(passes) == 1
        assert passes[0]["name"] == "Colour Pass #1 (1 Target + Depth)"
        assert not passes[0]["name"].startswith("vkCmd")

    def test_friendly_name_children_no_markers(self) -> None:
        """Children-of-BeginPass with no marker groups: name should be friendly."""
        begin = ActionDescription(
            eventId=1,
            flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
            _name="vkCmdBeginRenderPass(C=Clear, C=Load)",
        )
        begin.children = [
            ActionDescription(eventId=2, flags=ActionFlags.Drawcall, numIndices=3, _name="d"),
        ]
        end = ActionDescription(
            eventId=3, flags=ActionFlags.EndPass | ActionFlags.PassBoundary, _name="EndPass"
        )
        passes = _build_pass_list([begin, end])
        assert len(passes) == 1
        assert passes[0]["name"] == "Colour Pass #1 (2 Targets)"
        assert not passes[0]["name"].startswith("vkCmd")

    def test_preserves_marker_group_name(self) -> None:
        """Marker groups inside BeginPass use marker name, not friendly pass name."""
        begin = ActionDescription(
            eventId=1,
            flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
            _name="vkCmdBeginRenderPass(C=Load)",
        )
        draw = ActionDescription(eventId=3, flags=ActionFlags.Drawcall, numIndices=3, _name="d")
        marker = ActionDescription(
            eventId=2,
            flags=ActionFlags.PushMarker,
            _name="Opaque objects",
            children=[draw],
        )
        begin.children = [marker]
        end = ActionDescription(
            eventId=4, flags=ActionFlags.EndPass | ActionFlags.PassBoundary, _name="EndPass"
        )
        passes = _build_pass_list([begin, end])
        assert len(passes) == 1
        assert passes[0]["name"] == "Opaque objects"

    def test_multi_pass_indices_increment(self) -> None:
        """Two markerless passes produce Colour Pass #1 and Colour Pass #2."""

        def _mk_pass(begin_eid: int, draw_eid: int, end_eid: int, api_name: str) -> list:
            b = ActionDescription(
                eventId=begin_eid,
                flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
                _name=api_name,
            )
            d = ActionDescription(
                eventId=draw_eid, flags=ActionFlags.Drawcall, numIndices=3, _name="d"
            )
            e = ActionDescription(
                eventId=end_eid, flags=ActionFlags.EndPass | ActionFlags.PassBoundary, _name="End"
            )
            return [b, d, e]

        actions = _mk_pass(1, 2, 3, "vkCmdBeginRenderPass(C=Load)") + _mk_pass(
            10, 11, 12, "vkCmdBeginRenderPass(C=Load)"
        )
        passes = _build_pass_list(actions)
        assert len(passes) == 2
        assert passes[0]["name"] == "Colour Pass #1 (1 Target)"
        assert passes[1]["name"] == "Colour Pass #2 (1 Target)"


# ---------------------------------------------------------------------------
# Fix 5: topology enum name
# ---------------------------------------------------------------------------


class TestPipelineRowTopology:
    def test_topology_enum_name(self) -> None:
        """Object with .name attribute → use name string."""

        class _FakeTopology:
            name = "TriangleList"

        pipe = type(
            "P",
            (),
            {
                "GetPrimitiveTopology": lambda self: _FakeTopology(),
                "GetGraphicsPipelineObject": lambda self: 0,
                "GetComputePipelineObject": lambda self: 0,
            },
        )()
        row = pipeline_row(10, "Vulkan", pipe)
        assert row["topology"] == "TriangleList"

    def test_topology_int_fallback(self) -> None:
        """Plain int (no .name) → str(value)."""
        pipe = type(
            "P",
            (),
            {
                "GetPrimitiveTopology": lambda self: 3,
                "GetGraphicsPipelineObject": lambda self: 0,
                "GetComputePipelineObject": lambda self: 0,
            },
        )()
        row = pipeline_row(10, "Vulkan", pipe)
        assert row["topology"] == "3"

    def test_topology_intenum(self) -> None:
        """IntEnum value → .name attribute gives enum member name."""
        from enum import IntEnum

        class MockTopology(IntEnum):
            TriangleList = 3

        pipe = type(
            "P",
            (),
            {
                "GetPrimitiveTopology": lambda self: MockTopology.TriangleList,
                "GetGraphicsPipelineObject": lambda self: 0,
                "GetComputePipelineObject": lambda self: 0,
            },
        )()
        row = pipeline_row(10, "Vulkan", pipe)
        assert row["topology"] == "TriangleList"
