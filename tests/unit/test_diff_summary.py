"""Tests for capture-level summary diff module."""

from __future__ import annotations

import json

from rdc.diff.summary import SummaryRow, diff_summary, render_json, render_text


def _stats(per_pass: list[dict[str, object]], event_count: int = 0) -> dict[str, object]:
    return {"per_pass": per_pass, "event_count": event_count}


def _pass(
    name: str = "GBuffer", draws: int = 10, triangles: int = 5000, dispatches: int = 0
) -> dict[str, object]:
    return {"name": name, "draws": draws, "triangles": triangles, "dispatches": dispatches}


# ---------------------------------------------------------------------------
# S-01 through S-06: diff_summary logic
# ---------------------------------------------------------------------------


class TestDiffSummary:
    def test_identical_stats(self) -> None:
        """S-01: identical stats produce all-zero deltas."""
        s = _stats([_pass("G", draws=10)], event_count=100)
        rows = diff_summary(s, s, 5, 5)
        assert all(r.delta == 0 for r in rows)
        assert rows[0].value_a == rows[0].value_b == 10

    def test_draw_count_increased(self) -> None:
        """S-02: draw count delta is positive when B has more."""
        sa = _stats([_pass(draws=10)], event_count=100)
        sb = _stats([_pass(draws=15)], event_count=100)
        rows = diff_summary(sa, sb, 5, 5)
        draw_row = next(r for r in rows if r.category == "draws")
        assert draw_row.delta == 5

    def test_pass_removed(self) -> None:
        """S-03: pass removed produces negative delta."""
        sa = _stats([_pass("A"), _pass("B")], event_count=100)
        sb = _stats([_pass("A")], event_count=100)
        rows = diff_summary(sa, sb, 5, 5)
        pass_row = next(r for r in rows if r.category == "passes")
        assert pass_row.delta == -1

    def test_resource_count_changed(self) -> None:
        """S-04: resource count change produces non-zero delta."""
        s = _stats([_pass()], event_count=100)
        rows = diff_summary(s, s, 5, 8)
        res_row = next(r for r in rows if r.category == "resources")
        assert res_row.delta == 3

    def test_all_categories_changed(self) -> None:
        """S-05: all four categories changed simultaneously."""
        sa = _stats([_pass(draws=10), _pass(draws=5)], event_count=100)
        sb = _stats([_pass(draws=20)], event_count=200)
        rows = diff_summary(sa, sb, 5, 10)
        assert len(rows) == 4
        assert all(r.delta != 0 for r in rows)

    def test_empty_both_sides(self) -> None:
        """S-06: empty inputs produce all-zero deltas."""
        s = _stats([], event_count=0)
        rows = diff_summary(s, s, 0, 0)
        assert all(r.delta == 0 for r in rows)
        assert all(r.value_a == 0 and r.value_b == 0 for r in rows)


# ---------------------------------------------------------------------------
# S-07 through S-11: render_text
# ---------------------------------------------------------------------------


class TestRenderText:
    def test_all_zero_identical(self) -> None:
        """S-07: all-zero deltas produce 'identical'."""
        rows = [
            SummaryRow("draws", 10, 10, 0),
            SummaryRow("passes", 2, 2, 0),
            SummaryRow("resources", 5, 5, 0),
            SummaryRow("events", 100, 100, 0),
        ]
        assert render_text(rows) == "identical"

    def test_positive_draw_delta(self) -> None:
        """S-08: positive delta formats as (+N)."""
        rows = [
            SummaryRow("draws", 10, 15, 5),
            SummaryRow("passes", 2, 2, 0),
            SummaryRow("resources", 5, 5, 0),
            SummaryRow("events", 100, 100, 0),
        ]
        out = render_text(rows)
        assert "(+5)" in out
        assert "draws:" in out

    def test_negative_pass_delta(self) -> None:
        """S-09: negative delta formats as (-N)."""
        rows = [
            SummaryRow("draws", 10, 10, 0),
            SummaryRow("passes", 3, 2, -1),
            SummaryRow("resources", 5, 5, 0),
            SummaryRow("events", 100, 100, 0),
        ]
        out = render_text(rows)
        assert "(-1)" in out
        assert "passes:" in out

    def test_equal_shows_eq(self) -> None:
        """S-10: zero-delta categories show (=)."""
        rows = [
            SummaryRow("draws", 10, 15, 5),
            SummaryRow("passes", 2, 2, 0),
            SummaryRow("resources", 5, 5, 0),
            SummaryRow("events", 100, 100, 0),
        ]
        out = render_text(rows)
        assert "(=)" in out

    def test_four_lines_when_non_identical(self) -> None:
        """S-11: output has exactly 4 lines when non-identical."""
        rows = [
            SummaryRow("draws", 10, 15, 5),
            SummaryRow("passes", 2, 3, 1),
            SummaryRow("resources", 5, 6, 1),
            SummaryRow("events", 100, 110, 10),
        ]
        out = render_text(rows)
        lines = [ln for ln in out.split("\n") if ln.strip()]
        assert len(lines) == 4


# ---------------------------------------------------------------------------
# S-12 through S-14: render_json
# ---------------------------------------------------------------------------


class TestRenderJsonSummary:
    def test_json_schema(self) -> None:
        """S-12: JSON has all four category keys."""
        rows = [
            SummaryRow("draws", 10, 15, 5),
            SummaryRow("passes", 2, 2, 0),
            SummaryRow("resources", 5, 5, 0),
            SummaryRow("events", 100, 100, 0),
        ]
        data = json.loads(render_json(rows))
        assert set(data.keys()) == {"draws", "passes", "resources", "events"}

    def test_subfields(self) -> None:
        """S-13: each key has a, b, delta sub-fields as ints."""
        rows = [
            SummaryRow("draws", 10, 15, 5),
            SummaryRow("passes", 2, 2, 0),
            SummaryRow("resources", 5, 5, 0),
            SummaryRow("events", 100, 100, 0),
        ]
        data = json.loads(render_json(rows))
        for cat in data.values():
            assert isinstance(cat["a"], int)
            assert isinstance(cat["b"], int)
            assert isinstance(cat["delta"], int)

    def test_empty_valid_json(self) -> None:
        """S-14: empty input produces valid JSON with all-zero values."""
        rows = [
            SummaryRow("draws", 0, 0, 0),
            SummaryRow("passes", 0, 0, 0),
            SummaryRow("resources", 0, 0, 0),
            SummaryRow("events", 0, 0, 0),
        ]
        data = json.loads(render_json(rows))
        assert all(v["delta"] == 0 for v in data.values())
