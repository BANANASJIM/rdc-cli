"""Tests for query_service action tree traversal and stats aggregation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    APIEvent,
)

from rdc.services.query_service import (
    aggregate_stats,
    filter_by_pass,
    filter_by_pattern,
    filter_by_type,
    find_action_by_eid,
    get_top_draws,
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
