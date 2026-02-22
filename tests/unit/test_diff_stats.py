"""Tests for per-pass stats comparison and renderers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from rdc.commands import diff as diff_mod
from rdc.commands.diff import diff_cmd
from rdc.diff.draws import DiffStatus
from rdc.diff.stats import (
    PassDiffRow,
    diff_stats,
    render_json,
    render_shortstat,
    render_tsv,
    render_unified,
)
from rdc.services.diff_service import DiffContext


def _pass(
    name: str = "GBuffer",
    draws: int = 10,
    triangles: int = 5000,
    dispatches: int = 0,
) -> dict[str, object]:
    return {
        "name": name,
        "draws": draws,
        "triangles": triangles,
        "dispatches": dispatches,
    }


# ---------------------------------------------------------------------------
# diff_stats matching
# ---------------------------------------------------------------------------


class TestDiffStats:
    def test_identical_passes(self) -> None:
        a = [_pass("GBuffer"), _pass("Lighting")]
        b = [_pass("GBuffer"), _pass("Lighting")]
        rows = diff_stats(a, b)
        assert len(rows) == 2
        assert all(r.status == DiffStatus.EQUAL for r in rows)

    def test_modified_draws(self) -> None:
        a = [_pass("GBuffer", draws=10)]
        b = [_pass("GBuffer", draws=15)]
        rows = diff_stats(a, b)
        assert rows[0].status == DiffStatus.MODIFIED
        assert rows[0].draws_a == 10
        assert rows[0].draws_b == 15
        assert rows[0].draws_delta == "+5"

    def test_modified_triangles(self) -> None:
        a = [_pass("GBuffer", triangles=5000)]
        b = [_pass("GBuffer", triangles=3000)]
        rows = diff_stats(a, b)
        assert rows[0].status == DiffStatus.MODIFIED
        assert rows[0].triangles_delta == "-2000"

    def test_modified_dispatches(self) -> None:
        a = [_pass("Compute", dispatches=5)]
        b = [_pass("Compute", dispatches=8)]
        rows = diff_stats(a, b)
        assert rows[0].status == DiffStatus.MODIFIED
        assert rows[0].dispatches_delta == "+3"

    def test_deleted_pass(self) -> None:
        a = [_pass("GBuffer"), _pass("Shadow")]
        b = [_pass("GBuffer")]
        rows = diff_stats(a, b)
        assert len(rows) == 2
        statuses = {r.name: r.status for r in rows}
        assert statuses["GBuffer"] == DiffStatus.EQUAL
        assert statuses["Shadow"] == DiffStatus.DELETED

    def test_added_pass(self) -> None:
        a = [_pass("GBuffer")]
        b = [_pass("GBuffer"), _pass("PostFX")]
        rows = diff_stats(a, b)
        assert len(rows) == 2
        statuses = {r.name: r.status for r in rows}
        assert statuses["GBuffer"] == DiffStatus.EQUAL
        assert statuses["PostFX"] == DiffStatus.ADDED

    def test_case_insensitive_match(self) -> None:
        a = [_pass("gbuffer", draws=10)]
        b = [_pass("GBuffer", draws=10)]
        rows = diff_stats(a, b)
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.EQUAL

    def test_whitespace_stripped(self) -> None:
        a = [_pass(" GBuffer ", draws=10)]
        b = [_pass("GBuffer", draws=10)]
        rows = diff_stats(a, b)
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.EQUAL

    def test_both_empty(self) -> None:
        assert diff_stats([], []) == []

    def test_empty_a(self) -> None:
        rows = diff_stats([], [_pass("GBuffer")])
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.ADDED

    def test_empty_b(self) -> None:
        rows = diff_stats([_pass("GBuffer")], [])
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.DELETED

    def test_deleted_fields_none(self) -> None:
        rows = diff_stats([_pass("X", draws=5, triangles=100, dispatches=2)], [])
        r = rows[0]
        assert r.draws_a == 5
        assert r.draws_b is None
        assert r.draws_delta == "-"
        assert r.triangles_b is None
        assert r.dispatches_b is None

    def test_added_fields_none(self) -> None:
        rows = diff_stats([], [_pass("X", draws=5, triangles=100, dispatches=2)])
        r = rows[0]
        assert r.draws_a is None
        assert r.draws_b == 5
        assert r.draws_delta == "-"
        assert r.triangles_a is None
        assert r.dispatches_a is None

    def test_ordering_a_side_first(self) -> None:
        a = [_pass("Alpha"), _pass("Beta")]
        b = [_pass("Gamma"), _pass("Alpha")]
        rows = diff_stats(a, b)
        names = [r.name for r in rows]
        assert names[0] == "Alpha"
        assert names[1] == "Beta"
        assert names[2] == "Gamma"

    def test_zero_delta(self) -> None:
        a = [_pass("P", draws=10, triangles=500)]
        b = [_pass("P", draws=10, triangles=500)]
        rows = diff_stats(a, b)
        assert rows[0].draws_delta == "0"
        assert rows[0].triangles_delta == "0"


# ---------------------------------------------------------------------------
# _delta formatting (tested through diff_stats)
# ---------------------------------------------------------------------------


class TestDelta:
    def test_positive(self) -> None:
        rows = diff_stats([_pass("P", draws=10)], [_pass("P", draws=15)])
        assert rows[0].draws_delta == "+5"

    def test_negative(self) -> None:
        rows = diff_stats([_pass("P", draws=15)], [_pass("P", draws=10)])
        assert rows[0].draws_delta == "-5"

    def test_zero(self) -> None:
        rows = diff_stats([_pass("P", draws=10)], [_pass("P", draws=10)])
        assert rows[0].draws_delta == "0"

    def test_missing_side(self) -> None:
        rows = diff_stats([_pass("P")], [])
        assert rows[0].draws_delta == "-"


# ---------------------------------------------------------------------------
# render_tsv
# ---------------------------------------------------------------------------


class TestRenderTsv:
    def test_header_columns(self) -> None:
        out = render_tsv([], header=True)
        cols = out.strip().split("\t")
        assert cols == [
            "STATUS",
            "PASS",
            "DRAWS_A",
            "DRAWS_B",
            "DRAWS_DELTA",
            "TRI_A",
            "TRI_B",
            "TRI_DELTA",
            "DISP_A",
            "DISP_B",
            "DISP_DELTA",
        ]

    def test_no_header(self) -> None:
        out = render_tsv([], header=False)
        assert out == ""

    def test_single_row(self) -> None:
        row = PassDiffRow(
            status=DiffStatus.MODIFIED,
            name="GBuffer",
            draws_a=10,
            draws_b=15,
            draws_delta="+5",
            triangles_a=5000,
            triangles_b=5200,
            triangles_delta="+200",
            dispatches_a=0,
            dispatches_b=2,
            dispatches_delta="+2",
        )
        out = render_tsv([row], header=True)
        lines = out.split("\n")
        assert len(lines) == 2
        fields = lines[1].split("\t")
        assert len(fields) == 11
        assert fields[0] == "~"
        assert fields[1] == "GBuffer"
        assert fields[4] == "+5"
        # dispatch columns
        assert fields[8] == "0"
        assert fields[9] == "2"
        assert fields[10] == "+2"

    def test_none_values_rendered_as_dash(self) -> None:
        row = PassDiffRow(
            status=DiffStatus.ADDED,
            name="PostFX",
            draws_a=None,
            draws_b=5,
            draws_delta="-",
            triangles_a=None,
            triangles_b=100,
            triangles_delta="-",
            dispatches_a=None,
            dispatches_b=0,
            dispatches_delta="-",
        )
        out = render_tsv([row], header=False)
        fields = out.split("\t")
        assert len(fields) == 11
        assert fields[2] == "-"  # draws_a
        assert fields[8] == "-"  # dispatches_a


# ---------------------------------------------------------------------------
# render_shortstat
# ---------------------------------------------------------------------------


class TestRenderShortstat:
    def test_no_changes(self) -> None:
        rows = [
            PassDiffRow(DiffStatus.EQUAL, "A", 10, 10, "0", 100, 100, "0", 0, 0, "0"),
        ]
        out = render_shortstat(rows)
        assert out == "0 passes changed; 0 draws, 0 triangles, 0 dispatches"

    def test_changes(self) -> None:
        rows = [
            PassDiffRow(DiffStatus.MODIFIED, "A", 10, 13, "+3", 5000, 5150, "+150", 0, 2, "+2"),
            PassDiffRow(DiffStatus.MODIFIED, "B", 5, 5, "0", 1000, 1000, "0", 2, 5, "+3"),
        ]
        out = render_shortstat(rows)
        assert "2 passes changed" in out
        assert "+150 triangles" in out
        assert "+3 draws" in out
        assert "+5 dispatches" in out

    def test_added_pass_counts(self) -> None:
        rows = [
            PassDiffRow(DiffStatus.ADDED, "New", None, 10, "-", None, 500, "-", None, 3, "-"),
        ]
        out = render_shortstat(rows)
        assert "1 passes changed" in out
        assert "1 added" in out
        assert "+500 triangles" in out
        assert "+10 draws" in out
        assert "+3 dispatches" in out

    def test_deleted_pass_subtracts(self) -> None:
        rows = [
            PassDiffRow(DiffStatus.DELETED, "Old", 10, None, "-", 500, None, "-", 2, None, "-"),
        ]
        out = render_shortstat(rows)
        assert "1 passes changed" in out
        assert "1 deleted" in out
        assert "-500 triangles" in out
        assert "-10 draws" in out
        assert "-2 dispatches" in out

    def test_empty(self) -> None:
        assert render_shortstat([]) == "0 passes changed; 0 draws, 0 triangles, 0 dispatches"

    def test_added_deleted_breakdown(self) -> None:
        rows = [
            PassDiffRow(DiffStatus.ADDED, "New", None, 5, "-", None, 100, "-", None, 0, "-"),
            PassDiffRow(DiffStatus.DELETED, "Old", 3, None, "-", 200, None, "-", 1, None, "-"),
        ]
        out = render_shortstat(rows)
        assert "2 passes changed, 1 added, 1 deleted" in out
        assert "; " in out


# ---------------------------------------------------------------------------
# render_json
# ---------------------------------------------------------------------------


class TestRenderJson:
    def test_schema(self) -> None:
        row = PassDiffRow(
            DiffStatus.EQUAL,
            "GBuffer",
            10,
            10,
            "0",
            5000,
            5000,
            "0",
            0,
            0,
            "0",
        )
        data = json.loads(render_json([row]))
        assert isinstance(data, list)
        assert len(data) == 1
        obj = data[0]
        assert obj["status"] == "="
        assert obj["name"] == "GBuffer"
        assert obj["draws_a"] == 10
        assert obj["draws_delta"] == "0"

    def test_nulls_for_added(self) -> None:
        row = PassDiffRow(
            DiffStatus.ADDED,
            "New",
            None,
            10,
            "-",
            None,
            500,
            "-",
            None,
            0,
            "-",
        )
        data = json.loads(render_json([row]))
        assert data[0]["draws_a"] is None
        assert data[0]["triangles_a"] is None

    def test_empty(self) -> None:
        assert json.loads(render_json([])) == []


# ---------------------------------------------------------------------------
# render_unified
# ---------------------------------------------------------------------------


class TestRenderUnified:
    def test_header(self) -> None:
        out = render_unified([], "a.rdc", "b.rdc")
        assert out.startswith("--- a/a.rdc\n+++ b/b.rdc")

    def test_equal_line(self) -> None:
        row = PassDiffRow(
            DiffStatus.EQUAL,
            "GBuffer",
            10,
            10,
            "0",
            5000,
            5000,
            "0",
            0,
            0,
            "0",
        )
        out = render_unified([row], "a.rdc", "b.rdc")
        lines = out.split("\n")
        assert lines[2].startswith(" GBuffer")
        assert "draws=10" in lines[2]
        assert "tri=5000" in lines[2]
        assert "disp=0" in lines[2]

    def test_deleted_line(self) -> None:
        row = PassDiffRow(
            DiffStatus.DELETED,
            "Shadow",
            5,
            None,
            "-",
            200,
            None,
            "-",
            0,
            None,
            "-",
        )
        out = render_unified([row], "a.rdc", "b.rdc")
        lines = out.split("\n")
        assert lines[2].startswith("-Shadow")
        assert "tri=200" in lines[2]
        assert "disp=0" in lines[2]

    def test_added_line(self) -> None:
        row = PassDiffRow(
            DiffStatus.ADDED,
            "PostFX",
            None,
            3,
            "-",
            None,
            100,
            "-",
            None,
            1,
            "-",
        )
        out = render_unified([row], "a.rdc", "b.rdc")
        lines = out.split("\n")
        assert lines[2].startswith("+PostFX")
        assert "tri=100" in lines[2]
        assert "disp=1" in lines[2]

    def test_modified_two_lines(self) -> None:
        row = PassDiffRow(
            DiffStatus.MODIFIED,
            "GBuffer",
            10,
            15,
            "+5",
            5000,
            5200,
            "+200",
            0,
            2,
            "+2",
        )
        out = render_unified([row], "a.rdc", "b.rdc")
        lines = out.split("\n")
        assert lines[2].startswith("-GBuffer")
        assert lines[3].startswith("+GBuffer")
        assert "draws=10" in lines[2]
        assert "draws=15" in lines[3]
        assert "tri=5000" in lines[2]
        assert "tri=5200" in lines[3]
        assert "disp=0" in lines[2]
        assert "disp=2" in lines[3]

    def test_empty_rows(self) -> None:
        out = render_unified([], "a.rdc", "b.rdc")
        assert out == "--- a/a.rdc\n+++ b/b.rdc"


# ---------------------------------------------------------------------------
# Exit code logic (tested via has_changes pattern)
# ---------------------------------------------------------------------------


class TestExitCodeLogic:
    def test_all_equal_no_changes(self) -> None:
        rows = diff_stats([_pass("A")], [_pass("A")])
        assert not any(r.status != DiffStatus.EQUAL for r in rows)

    def test_modified_has_changes(self) -> None:
        rows = diff_stats([_pass("A", draws=10)], [_pass("A", draws=20)])
        assert any(r.status != DiffStatus.EQUAL for r in rows)

    def test_added_has_changes(self) -> None:
        rows = diff_stats([], [_pass("A")])
        assert any(r.status != DiffStatus.EQUAL for r in rows)

    def test_deleted_has_changes(self) -> None:
        rows = diff_stats([_pass("A")], [])
        assert any(r.status != DiffStatus.EQUAL for r in rows)


# ---------------------------------------------------------------------------
# Mixed multi-pass (all 4 statuses simultaneously)
# ---------------------------------------------------------------------------


class TestMixedMultiPass:
    def test_all_four_statuses(self) -> None:
        a = [
            _pass("Equal", draws=10, triangles=500, dispatches=0),
            _pass("Modified", draws=10, triangles=500, dispatches=2),
            _pass("Deleted", draws=5, triangles=200, dispatches=1),
        ]
        b = [
            _pass("Equal", draws=10, triangles=500, dispatches=0),
            _pass("Modified", draws=15, triangles=600, dispatches=3),
            _pass("Added", draws=8, triangles=300, dispatches=0),
        ]
        rows = diff_stats(a, b)
        statuses = {r.name: r.status for r in rows}
        assert statuses["Equal"] == DiffStatus.EQUAL
        assert statuses["Modified"] == DiffStatus.MODIFIED
        assert statuses["Deleted"] == DiffStatus.DELETED
        assert statuses["Added"] == DiffStatus.ADDED
        assert len(rows) == 4

        # TSV includes all rows
        tsv = render_tsv(rows)
        assert tsv.count("\n") == 4  # header + 4 data rows

        # shortstat reflects all changes
        short = render_shortstat(rows)
        assert "3 passes changed" in short
        assert "1 added" in short
        assert "1 deleted" in short

        # unified has correct prefixes
        uni = render_unified(rows, "a.rdc", "b.rdc")
        lines = uni.split("\n")
        prefixes = [line[0] for line in lines[2:]]
        assert " " in prefixes
        assert "-" in prefixes
        assert "+" in prefixes

        # JSON has all 4 rows
        data = json.loads(render_json(rows))
        assert len(data) == 4


# ---------------------------------------------------------------------------
# CLI integration tests for diff --stats
# ---------------------------------------------------------------------------


def _make_diff_ctx() -> DiffContext:
    return DiffContext(
        session_id="aabbccddeeff",
        host="127.0.0.1",
        port_a=5000,
        port_b=5001,
        token_a="ta",
        token_b="tb",
        pid_a=100,
        pid_b=200,
        capture_a="a.rdc",
        capture_b="b.rdc",
    )


def _make_stats_response(per_pass: list[dict[str, object]]) -> dict[str, Any]:
    return {"result": {"per_pass": per_pass}}


def _patch_diff(
    monkeypatch: pytest.MonkeyPatch,
    passes_a: list[dict[str, object]],
    passes_b: list[dict[str, object]],
) -> None:
    """Monkeypatch start/stop/query_both for stats CLI tests."""
    ctx = _make_diff_ctx()
    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)
    monkeypatch.setattr(
        diff_mod,
        "query_both",
        lambda c, m, p, **kw: (
            _make_stats_response(passes_a),
            _make_stats_response(passes_b),
            "",
        ),
    )


class TestDiffStatsCLI:
    """CLI integration tests using CliRunner."""

    def test_stats_exit_0_all_equal(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        passes = [_pass("GBuffer", draws=10, triangles=500, dispatches=0)]
        _patch_diff(monkeypatch, passes, passes)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--stats"])
        assert result.exit_code == 0

    def test_stats_exit_1_changes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        pa = [_pass("GBuffer", draws=10)]
        pb = [_pass("GBuffer", draws=20)]
        _patch_diff(monkeypatch, pa, pb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--stats"])
        assert result.exit_code == 1

    def test_stats_exit_2_query_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        ctx = _make_diff_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)
        monkeypatch.setattr(
            diff_mod,
            "query_both",
            lambda c, m, p, **kw: (None, None, "timeout"),
        )
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--stats"])
        assert result.exit_code == 2

    def test_stats_shortstat_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        pa = [_pass("GBuffer", draws=10, triangles=500, dispatches=1)]
        pb = [_pass("GBuffer", draws=15, triangles=600, dispatches=3)]
        _patch_diff(monkeypatch, pa, pb)
        result = CliRunner().invoke(
            diff_cmd,
            [str(a), str(b), "--stats", "--shortstat"],
        )
        assert result.exit_code == 1
        assert "1 passes changed" in result.output
        assert "draws" in result.output
        assert "triangles" in result.output
        assert "dispatches" in result.output

    def test_stats_json_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        passes = [_pass("GBuffer")]
        _patch_diff(monkeypatch, passes, passes)
        result = CliRunner().invoke(
            diff_cmd,
            [str(a), str(b), "--stats", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["name"] == "GBuffer"

    def test_stats_unified_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        pa = [_pass("GBuffer", draws=10, triangles=500, dispatches=0)]
        pb = [_pass("GBuffer", draws=15, triangles=500, dispatches=0)]
        _patch_diff(monkeypatch, pa, pb)
        result = CliRunner().invoke(
            diff_cmd,
            [str(a), str(b), "--stats", "--format", "unified"],
        )
        assert result.exit_code == 1
        assert "--- a/" in result.output
        assert "+++ b/" in result.output
        assert "draws=" in result.output
        assert "tri=" in result.output
        assert "disp=" in result.output

    def test_stats_no_header(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        passes = [_pass("GBuffer")]
        _patch_diff(monkeypatch, passes, passes)
        result = CliRunner().invoke(
            diff_cmd,
            [str(a), str(b), "--stats", "--no-header"],
        )
        assert result.exit_code == 0
        assert "PASS" not in result.output
        assert "STATUS" not in result.output

    def test_stats_not_a_stub(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """--stats must produce real output, not 'not yet implemented'."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        passes = [_pass("GBuffer")]
        _patch_diff(monkeypatch, passes, passes)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--stats"])
        assert "not yet implemented" not in result.output.lower()

    def test_stats_tsv_has_dispatch_columns(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        pa = [_pass("GBuffer", dispatches=2)]
        pb = [_pass("GBuffer", dispatches=5)]
        _patch_diff(monkeypatch, pa, pb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--stats"])
        assert result.exit_code == 1
        assert "DISP_A" in result.output
        assert "DISP_B" in result.output
        assert "DISP_DELTA" in result.output
