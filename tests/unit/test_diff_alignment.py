"""Tests for draw call alignment module."""

from __future__ import annotations

from rdc.diff.alignment import (
    DrawRecord,
    align_draws,
    has_markers,
    lcs_align,
    make_fallback_keys,
    make_match_keys,
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
# Tests #1-2: DrawRecord construction
# ---------------------------------------------------------------------------


class TestDrawRecord:
    def test_construction(self) -> None:
        r = _rec(eid=10, draw_type="Draw", marker_path="Shadow/Caster", triangles=500)
        assert r.eid == 10
        assert r.draw_type == "Draw"
        assert r.marker_path == "Shadow/Caster"
        assert r.triangles == 500
        assert r.instances == 1

    def test_missing_marker_defaults_to_dash(self) -> None:
        r = _rec(marker_path="-")
        assert r.marker_path == "-"


# ---------------------------------------------------------------------------
# Tests #3-6: has_markers
# ---------------------------------------------------------------------------


class TestHasMarkers:
    def test_all_present(self) -> None:
        assert has_markers([_rec(marker_path="A"), _rec(marker_path="B")]) is True

    def test_all_absent(self) -> None:
        assert has_markers([_rec(marker_path="-"), _rec(marker_path="-")]) is False

    def test_mixed(self) -> None:
        assert has_markers([_rec(marker_path="-"), _rec(marker_path="A")]) is True

    def test_empty(self) -> None:
        assert has_markers([]) is False


# ---------------------------------------------------------------------------
# Tests #7-10: make_match_keys
# ---------------------------------------------------------------------------


class TestMakeMatchKeys:
    def test_unique_pairs(self) -> None:
        records = [
            _rec(marker_path="A", draw_type="Draw"),
            _rec(marker_path="B", draw_type="DrawIndexed"),
        ]
        keys = make_match_keys(records)
        assert keys == [("A", "Draw", 0), ("B", "DrawIndexed", 0)]

    def test_repeated_markers(self) -> None:
        records = [
            _rec(marker_path="GBuffer/Object", draw_type="DrawIndexed"),
            _rec(marker_path="GBuffer/Object", draw_type="DrawIndexed"),
            _rec(marker_path="GBuffer/Object", draw_type="DrawIndexed"),
        ]
        keys = make_match_keys(records)
        assert keys == [
            ("GBuffer/Object", "DrawIndexed", 0),
            ("GBuffer/Object", "DrawIndexed", 1),
            ("GBuffer/Object", "DrawIndexed", 2),
        ]

    def test_mixed_types_same_marker(self) -> None:
        records = [
            _rec(marker_path="Pass", draw_type="Draw"),
            _rec(marker_path="Pass", draw_type="DrawIndexed"),
            _rec(marker_path="Pass", draw_type="Draw"),
        ]
        keys = make_match_keys(records)
        assert keys == [("Pass", "Draw", 0), ("Pass", "DrawIndexed", 0), ("Pass", "Draw", 1)]

    def test_empty(self) -> None:
        assert make_match_keys([]) == []


# ---------------------------------------------------------------------------
# Tests #11-13: make_fallback_keys
# ---------------------------------------------------------------------------


class TestMakeFallbackKeys:
    def test_distinct(self) -> None:
        records = [
            _rec(draw_type="Draw", shader_hash="aaa", topology="TriangleList"),
            _rec(draw_type="DrawIndexed", shader_hash="bbb", topology="TriangleStrip"),
        ]
        keys = make_fallback_keys(records)
        assert keys == [("Draw", "aaa", "TriangleList"), ("DrawIndexed", "bbb", "TriangleStrip")]

    def test_same_type_diff_topology(self) -> None:
        records = [
            _rec(draw_type="Draw", shader_hash="aaa", topology="TriangleList"),
            _rec(draw_type="Draw", shader_hash="aaa", topology="TriangleStrip"),
        ]
        keys = make_fallback_keys(records)
        assert keys[0] != keys[1]

    def test_identical(self) -> None:
        records = [
            _rec(draw_type="Draw", shader_hash="aaa", topology="TriangleList"),
            _rec(draw_type="Draw", shader_hash="aaa", topology="TriangleList"),
        ]
        keys = make_fallback_keys(records)
        assert keys[0] == keys[1]


# ---------------------------------------------------------------------------
# Tests #14-20: lcs_align
# ---------------------------------------------------------------------------


class TestLcsAlign:
    def test_identical(self) -> None:
        keys = [("A",), ("B",), ("C",)]
        result = lcs_align(keys, keys)
        assert result == [(0, 0), (1, 1), (2, 2)]

    def test_added(self) -> None:
        a = [("A",), ("C",)]
        b = [("A",), ("B",), ("C",)]
        result = lcs_align(a, b)
        assert result == [(0, 0), (None, 1), (1, 2)]

    def test_deleted(self) -> None:
        a = [("A",), ("B",), ("C",)]
        b = [("A",), ("C",)]
        result = lcs_align(a, b)
        assert result == [(0, 0), (1, None), (2, 1)]

    def test_all_different(self) -> None:
        a = [("A",), ("B",)]
        b = [("C",), ("D",)]
        result = lcs_align(a, b)
        # No common subsequence: all from a are deleted, all from b are added
        assert all(ia is not None and ib is None for ia, ib in result if ib is None)
        assert all(ia is None and ib is not None for ia, ib in result if ia is None)
        assert len(result) == 4

    def test_swap(self) -> None:
        a = [("A",), ("B",)]
        b = [("B",), ("A",)]
        result = lcs_align(a, b)
        # LCS picks one match; the other is delete+add
        matched = [(ia, ib) for ia, ib in result if ia is not None and ib is not None]
        assert len(matched) == 1
        assert len(result) == 3

    def test_empty_a(self) -> None:
        result = lcs_align([], [("A",), ("B",)])
        assert result == [(None, 0), (None, 1)]

    def test_empty_b(self) -> None:
        result = lcs_align([("A",), ("B",)], [])
        assert result == [(0, None), (1, None)]

    def test_both_empty(self) -> None:
        assert lcs_align([], []) == []


# ---------------------------------------------------------------------------
# Tests #21-26: align_draws
# ---------------------------------------------------------------------------


class TestAlignDraws:
    def test_marker_identical(self) -> None:
        a = [_rec(eid=1, marker_path="A"), _rec(eid=2, marker_path="B")]
        b = [_rec(eid=10, marker_path="A"), _rec(eid=20, marker_path="B")]
        result = align_draws(a, b)
        assert len(result) == 2
        assert result[0] == (a[0], b[0])
        assert result[1] == (a[1], b[1])

    def test_marker_added(self) -> None:
        a = [_rec(eid=1, marker_path="A")]
        b = [_rec(eid=10, marker_path="A"), _rec(eid=20, marker_path="B")]
        result = align_draws(a, b)
        assert len(result) == 2
        assert result[0] == (a[0], b[0])
        assert result[1] == (None, b[1])

    def test_marker_deleted(self) -> None:
        a = [_rec(eid=1, marker_path="A"), _rec(eid=2, marker_path="B")]
        b = [_rec(eid=10, marker_path="B")]
        result = align_draws(a, b)
        assert len(result) == 2
        assert result[0] == (a[0], None)
        assert result[1] == (a[1], b[0])

    def test_fallback_mode(self) -> None:
        a = [
            _rec(
                eid=1, marker_path="-", draw_type="Draw", shader_hash="aaa", topology="TriangleList"
            )
        ]
        b = [
            _rec(
                eid=10,
                marker_path="-",
                draw_type="Draw",
                shader_hash="aaa",
                topology="TriangleList",
            )
        ]
        result = align_draws(a, b)
        assert len(result) == 1
        assert result[0][0] is not None
        assert result[0][1] is not None

    def test_grouping_large(self) -> None:
        """When combined length > 500, grouping by top-level marker is used."""
        a = [_rec(eid=i, marker_path=f"Group{i % 3}/Sub{i}") for i in range(300)]
        b = [_rec(eid=i + 1000, marker_path=f"Group{i % 3}/Sub{i}") for i in range(300)]
        result = align_draws(a, b)
        # All should be matched since keys are identical
        assert len(result) == 300
        for ra, rb in result:
            assert ra is not None
            assert rb is not None

    def test_no_slash_marker(self) -> None:
        """Markers without slash still work for grouping."""
        a = [_rec(eid=1, marker_path="Flat"), _rec(eid=2, marker_path="Flat")]
        b = [_rec(eid=10, marker_path="Flat"), _rec(eid=20, marker_path="Flat")]
        result = align_draws(a, b)
        assert len(result) == 2
        assert result[0] == (a[0], b[0])
        assert result[1] == (a[1], b[1])
