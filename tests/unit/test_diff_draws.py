"""Tests for draw call comparison and renderers."""

from __future__ import annotations

import json

import pytest

from rdc.diff.alignment import DrawRecord
from rdc.diff.draws import (
    DiffStatus,
    DrawDiffRow,
    compare_draw_pair,
    diff_draws,
    render_json,
    render_shortstat,
    render_unified,
)


def _rec(
    eid: int = 1,
    draw_type: str = "DrawIndexed",
    marker_path: str = "GBuffer/Floor",
    triangles: int = 100,
    instances: int = 1,
    pass_name: str = "pass0",
    shader_hash: str = "abc123",
    topology: str = "TriangleList",
) -> DrawRecord:
    return DrawRecord(
        eid=eid,
        draw_type=draw_type,
        marker_path=marker_path,
        triangles=triangles,
        instances=instances,
        pass_name=pass_name,
        shader_hash=shader_hash,
        topology=topology,
    )


# ---------------------------------------------------------------------------
# Tests #27-36: compare_draw_pair
# ---------------------------------------------------------------------------


class TestCompareDrawPair:
    def test_equal(self) -> None:
        a = _rec(eid=1, triangles=100, instances=1)
        b = _rec(eid=2, triangles=100, instances=1)
        row = compare_draw_pair(a, b)
        assert row.status == DiffStatus.EQUAL

    def test_triangles_differ(self) -> None:
        a = _rec(triangles=100)
        b = _rec(triangles=200)
        row = compare_draw_pair(a, b)
        assert row.status == DiffStatus.MODIFIED

    def test_instances_differ(self) -> None:
        a = _rec(instances=1)
        b = _rec(instances=5)
        row = compare_draw_pair(a, b)
        assert row.status == DiffStatus.MODIFIED

    def test_type_differ(self) -> None:
        a = _rec(draw_type="Draw")
        b = _rec(draw_type="DrawIndexed")
        row = compare_draw_pair(a, b)
        assert row.status == DiffStatus.MODIFIED

    def test_added(self) -> None:
        b = _rec(eid=10)
        row = compare_draw_pair(None, b)
        assert row.status == DiffStatus.ADDED
        assert row.eid_a is None
        assert row.eid_b == 10

    def test_deleted(self) -> None:
        a = _rec(eid=5)
        row = compare_draw_pair(a, None)
        assert row.status == DiffStatus.DELETED
        assert row.eid_a == 5
        assert row.eid_b is None

    def test_confidence_default_high(self) -> None:
        row = compare_draw_pair(_rec(), _rec())
        assert row.confidence == "high"

    def test_added_fields(self) -> None:
        b = _rec(eid=10, marker_path="X", draw_type="Draw", triangles=50, instances=3)
        row = compare_draw_pair(None, b)
        assert row.marker == "X"
        assert row.draw_type == "Draw"
        assert row.triangles_b == 50
        assert row.instances_b == 3
        assert row.triangles_a is None
        assert row.instances_a is None

    def test_deleted_fields(self) -> None:
        a = _rec(eid=5, marker_path="Y", draw_type="DrawIndexed", triangles=200, instances=2)
        row = compare_draw_pair(a, None)
        assert row.marker == "Y"
        assert row.triangles_a == 200
        assert row.instances_a == 2
        assert row.triangles_b is None
        assert row.instances_b is None

    def test_both_none_raises(self) -> None:
        with pytest.raises(ValueError, match="both a and b are None"):
            compare_draw_pair(None, None)


# ---------------------------------------------------------------------------
# Tests #37-44: diff_draws integration
# ---------------------------------------------------------------------------


class TestDiffDraws:
    def test_identical(self) -> None:
        a = [_rec(eid=1, marker_path="A"), _rec(eid=2, marker_path="B")]
        b = [_rec(eid=10, marker_path="A"), _rec(eid=20, marker_path="B")]
        rows = diff_draws(a, b)
        assert all(r.status == DiffStatus.EQUAL for r in rows)

    def test_added(self) -> None:
        a = [_rec(eid=1, marker_path="A")]
        b = [_rec(eid=10, marker_path="A"), _rec(eid=20, marker_path="B")]
        rows = diff_draws(a, b)
        statuses = [r.status for r in rows]
        assert DiffStatus.ADDED in statuses

    def test_deleted(self) -> None:
        a = [_rec(eid=1, marker_path="A"), _rec(eid=2, marker_path="B")]
        b = [_rec(eid=10, marker_path="B")]
        rows = diff_draws(a, b)
        statuses = [r.status for r in rows]
        assert DiffStatus.DELETED in statuses

    def test_modified(self) -> None:
        a = [_rec(eid=1, marker_path="A", triangles=100)]
        b = [_rec(eid=10, marker_path="A", triangles=200)]
        rows = diff_draws(a, b)
        assert rows[0].status == DiffStatus.MODIFIED

    def test_all_different(self) -> None:
        a = [_rec(eid=1, marker_path="A")]
        b = [_rec(eid=10, marker_path="B")]
        rows = diff_draws(a, b)
        assert len(rows) == 2
        statuses = {r.status for r in rows}
        assert DiffStatus.DELETED in statuses
        assert DiffStatus.ADDED in statuses

    def test_empty_a(self) -> None:
        b = [_rec(eid=10, marker_path="A")]
        rows = diff_draws([], b)
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.ADDED

    def test_empty_b(self) -> None:
        a = [_rec(eid=1, marker_path="A")]
        rows = diff_draws(a, [])
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.DELETED

    def test_both_empty(self) -> None:
        assert diff_draws([], []) == []

    def test_fallback_confidence(self) -> None:
        a = [_rec(eid=1, marker_path="-", draw_type="Draw", shader_hash="x", topology="T")]
        b = [_rec(eid=2, marker_path="-", draw_type="Draw", shader_hash="x", topology="T")]
        rows = diff_draws(a, b)
        assert rows[0].confidence in ("medium", "low")


# ---------------------------------------------------------------------------
# Tests #45-51: render_unified
# ---------------------------------------------------------------------------


class TestRenderUnified:
    def test_header(self) -> None:
        output = render_unified([], "a.rdc", "b.rdc")
        assert output.startswith("--- a/a.rdc\n+++ b/b.rdc")

    def test_equal_line(self) -> None:
        row = DrawDiffRow(
            status=DiffStatus.EQUAL,
            eid_a=100,
            eid_b=100,
            marker="GBuffer/Floor",
            draw_type="DrawIndexed",
            triangles_a=1000,
            triangles_b=1000,
            instances_a=1,
            instances_b=1,
            confidence="high",
        )
        output = render_unified([row], "a.rdc", "b.rdc")
        lines = output.split("\n")
        assert lines[2].startswith(" EID=100")

    def test_deleted_line(self) -> None:
        row = DrawDiffRow(
            status=DiffStatus.DELETED,
            eid_a=200,
            eid_b=None,
            marker="GBuffer/Wall",
            draw_type="DrawIndexed",
            triangles_a=500,
            triangles_b=None,
            instances_a=1,
            instances_b=None,
            confidence="high",
        )
        output = render_unified([row], "a.rdc", "b.rdc")
        lines = output.split("\n")
        assert lines[2].startswith("-EID=200")

    def test_added_line(self) -> None:
        row = DrawDiffRow(
            status=DiffStatus.ADDED,
            eid_a=None,
            eid_b=300,
            marker="Lighting/Sun",
            draw_type="Draw",
            triangles_a=None,
            triangles_b=6,
            instances_a=None,
            instances_b=1,
            confidence="high",
        )
        output = render_unified([row], "a.rdc", "b.rdc")
        lines = output.split("\n")
        assert lines[2].startswith("+EID=300")

    def test_modified_two_lines(self) -> None:
        row = DrawDiffRow(
            status=DiffStatus.MODIFIED,
            eid_a=200,
            eid_b=201,
            marker="GBuffer/Wall",
            draw_type="DrawIndexed",
            triangles_a=500,
            triangles_b=600,
            instances_a=1,
            instances_b=1,
            confidence="high",
        )
        output = render_unified([row], "a.rdc", "b.rdc")
        lines = output.split("\n")
        assert lines[2].startswith("-EID=200")
        assert lines[3].startswith("+EID=201")

    def test_mixed_output(self) -> None:
        rows = [
            DrawDiffRow(
                DiffStatus.EQUAL, 100, 100, "GBuffer/Floor", "DrawIndexed", 1000, 1000, 1, 1, "high"
            ),
            DrawDiffRow(
                DiffStatus.MODIFIED, 200, 201, "GBuffer/Wall", "DrawIndexed", 500, 600, 1, 1, "high"
            ),
            DrawDiffRow(
                DiffStatus.ADDED,
                None,
                300,
                "Lighting/Sun",
                "Draw",
                None,
                6,
                None,
                1,
                "high",
            ),
        ]
        output = render_unified(rows, "a.rdc", "b.rdc")
        lines = output.split("\n")
        # header + equal + modified(2) + added = 6 lines
        assert len(lines) == 6

    def test_empty_rows(self) -> None:
        output = render_unified([], "a.rdc", "b.rdc")
        assert output == "--- a/a.rdc\n+++ b/b.rdc"


# ---------------------------------------------------------------------------
# Tests #52-54: render_shortstat
# ---------------------------------------------------------------------------


class TestRenderShortstat:
    def test_all_equal(self) -> None:
        rows = [
            DrawDiffRow(DiffStatus.EQUAL, 1, 1, "A", "Draw", 10, 10, 1, 1, "high"),
            DrawDiffRow(DiffStatus.EQUAL, 2, 2, "B", "Draw", 10, 10, 1, 1, "high"),
        ]
        assert render_shortstat(rows) == "0 added, 0 deleted, 0 modified, 2 unchanged"

    def test_mixed(self) -> None:
        rows = [
            DrawDiffRow(DiffStatus.ADDED, None, 1, "A", "Draw", None, 10, None, 1, "high"),
            DrawDiffRow(DiffStatus.DELETED, 2, None, "B", "Draw", 10, None, 1, None, "high"),
            DrawDiffRow(DiffStatus.MODIFIED, 3, 3, "C", "Draw", 10, 20, 1, 1, "high"),
            DrawDiffRow(DiffStatus.EQUAL, 4, 4, "D", "Draw", 10, 10, 1, 1, "high"),
        ]
        assert render_shortstat(rows) == "1 added, 1 deleted, 1 modified, 1 unchanged"

    def test_empty(self) -> None:
        assert render_shortstat([]) == "0 added, 0 deleted, 0 modified, 0 unchanged"


# ---------------------------------------------------------------------------
# Tests #55-58: render_json
# ---------------------------------------------------------------------------


class TestRenderJson:
    def test_schema(self) -> None:
        row = DrawDiffRow(DiffStatus.EQUAL, 1, 1, "A", "Draw", 10, 10, 1, 1, "high")
        data = json.loads(render_json([row]))
        assert isinstance(data, list)
        assert len(data) == 1
        obj = data[0]
        assert obj["status"] == "="
        assert obj["eid_a"] == 1
        assert obj["draw_type"] == "Draw"
        assert obj["confidence"] == "high"

    def test_nulls_for_added(self) -> None:
        row = DrawDiffRow(DiffStatus.ADDED, None, 10, "X", "Draw", None, 50, None, 1, "high")
        data = json.loads(render_json([row]))
        assert data[0]["eid_a"] is None
        assert data[0]["triangles_a"] is None

    def test_valid_json(self) -> None:
        rows = [
            DrawDiffRow(DiffStatus.EQUAL, 1, 1, "A", "Draw", 10, 10, 1, 1, "high"),
            DrawDiffRow(DiffStatus.ADDED, None, 2, "B", "Draw", None, 20, None, 1, "high"),
        ]
        parsed = json.loads(render_json(rows))
        assert len(parsed) == 2

    def test_empty(self) -> None:
        data = json.loads(render_json([]))
        assert data == []
