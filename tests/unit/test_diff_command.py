"""Tests for the rdc diff CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from rdc.commands import diff as diff_mod
from rdc.commands.diff import diff_cmd
from rdc.services.diff_service import DiffContext


def _make_ctx() -> DiffContext:
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


def _draws_resp(
    draws: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    if draws is None:
        draws = [
            {
                "eid": 10,
                "type": "DrawIndexed",
                "triangles": 100,
                "instances": 1,
                "pass": "GBuffer",
                "marker": "Floor",
            },
        ]
    return {"result": {"draws": draws, "summary": f"{len(draws)} draw calls"}}


def _stats_resp(
    per_pass: list[dict[str, object]] | None = None,
    event_count: int = 100,
) -> dict[str, Any]:
    if per_pass is None:
        per_pass = [{"name": "GBuffer", "draws": 10, "triangles": 5000, "dispatches": 0}]
    return {"result": {"per_pass": per_pass, "event_count": event_count, "top_draws": []}}


def _resources_resp(
    rows: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    if rows is None:
        rows = [{"id": 1, "type": "Texture2D", "name": "albedo"}]
    return {"result": {"rows": rows}}


def _patch_summary(
    monkeypatch: pytest.MonkeyPatch,
    stats_a: dict[str, Any] | None = None,
    stats_b: dict[str, Any] | None = None,
    res_a: dict[str, Any] | None = None,
    res_b: dict[str, Any] | None = None,
) -> None:
    """Patch diff module for summary mode (default)."""
    ctx = _make_ctx()
    sa = stats_a or _stats_resp()
    sb = stats_b or _stats_resp()
    ra = res_a or _resources_resp()
    rb = res_b or _resources_resp()

    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

    def mock_query_both(c: object, method: str, params: object, **kw: object) -> tuple[Any, ...]:
        if method == "stats":
            return sa, sb, ""
        if method == "resources":
            return ra, rb, ""
        return None, None, "unexpected"

    monkeypatch.setattr(diff_mod, "query_both", mock_query_both)


def _patch_draws(
    monkeypatch: pytest.MonkeyPatch,
    draws_a: dict[str, Any] | None = None,
    draws_b: dict[str, Any] | None = None,
) -> None:
    """Patch diff module for --draws mode."""
    ctx = _make_ctx()
    da = draws_a or _draws_resp()
    db = draws_b or _draws_resp()

    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)
    monkeypatch.setattr(
        diff_mod,
        "query_both",
        lambda c, m, p, **kw: (da, db, ""),
    )


def _patch_passes(
    monkeypatch: pytest.MonkeyPatch,
    stats_a: dict[str, Any] | None = None,
    stats_b: dict[str, Any] | None = None,
) -> None:
    """Patch diff module for --passes mode."""
    ctx = _make_ctx()
    sa = stats_a or _stats_resp()
    sb = stats_b or _stats_resp()

    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)
    monkeypatch.setattr(
        diff_mod,
        "query_both",
        lambda c, m, p, **kw: (sa, sb, ""),
    )


# ---------------------------------------------------------------------------
# #26  Happy path → exit 0 (summary, identical)
# ---------------------------------------------------------------------------


def test_diff_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    _patch_summary(monkeypatch)

    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# #27  --timeout forwarded
# ---------------------------------------------------------------------------


def test_diff_timeout_forwarded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    captured_kw: dict[str, object] = {}

    def mock_start(*args: object, **kw: object) -> tuple[DiffContext, str]:
        captured_kw.update(kw)
        return _make_ctx(), ""

    monkeypatch.setattr(diff_mod, "start_diff_session", mock_start)
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)
    monkeypatch.setattr(
        diff_mod,
        "query_both",
        lambda c, m, p, **kw: (
            (_stats_resp(), _stats_resp(), "")
            if m == "stats"
            else (_resources_resp(), _resources_resp(), "")
        ),
    )

    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b), "--timeout", "90"])
    assert result.exit_code == 0
    assert captured_kw.get("timeout_s") == 90.0


# ---------------------------------------------------------------------------
# #28  Missing file → exit 2
# ---------------------------------------------------------------------------


def test_diff_missing_file(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(tmp_path / "no.rdc"), str(tmp_path / "no2.rdc")])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# #29  Startup error → exit 2
# ---------------------------------------------------------------------------


def test_diff_startup_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (None, "spawn failed"))

    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b)])
    assert result.exit_code == 2
    assert "spawn failed" in result.output


# ---------------------------------------------------------------------------
# #30  Cleanup always runs (even on query error)
# ---------------------------------------------------------------------------


def test_diff_cleanup_on_query_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    ctx = _make_ctx()
    stop_called = MagicMock()
    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", stop_called)
    monkeypatch.setattr(
        diff_mod,
        "query_both",
        lambda c, m, p, **kw: (None, None, "both daemons failed"),
    )

    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b), "--draws"])
    assert stop_called.called
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# #32  --pipeline MARKER
# ---------------------------------------------------------------------------


def test_diff_pipeline_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    ctx = _make_ctx()
    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b), "--pipeline", "vs"])
    assert result.exit_code == 2
    assert "both daemons failed" in result.output


# ===========================================================================
# --draws mode tests (C-01, C-03 through C-09)
# ===========================================================================


class TestDiffDrawsCLI:
    def test_draws_identical_exit_0(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-01/C-03: --draws with identical draws exits 0, TSV header present."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_draws(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--draws"])
        assert result.exit_code == 0
        assert "STATUS" in result.output

    def test_draws_differences_exit_1(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """C-04: --draws with differences exits 1."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        da = _draws_resp(
            [
                {
                    "eid": 10,
                    "type": "DrawIndexed",
                    "triangles": 100,
                    "instances": 1,
                    "pass": "GBuffer",
                    "marker": "Floor",
                },
            ]
        )
        db = _draws_resp(
            [
                {
                    "eid": 10,
                    "type": "DrawIndexed",
                    "triangles": 200,
                    "instances": 1,
                    "pass": "GBuffer",
                    "marker": "Floor",
                },
            ]
        )
        _patch_draws(monkeypatch, da, db)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--draws"])
        assert result.exit_code == 1
        assert "~" in result.output

    def test_draws_shortstat(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-05: --draws --shortstat produces summary line."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_draws(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--draws", "--shortstat"])
        assert result.exit_code == 0
        assert "unchanged" in result.output

    def test_draws_json(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-06: --draws --format json produces valid JSON."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_draws(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--draws", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_draws_unified(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-07: --draws --format unified starts with --- a/ header."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_draws(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--draws", "--format", "unified"])
        assert result.exit_code == 0
        assert "--- a/" in result.output

    def test_draws_query_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-08: --draws when query fails exits 2."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        ctx = _make_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)
        monkeypatch.setattr(
            diff_mod,
            "query_both",
            lambda c, m, p, **kw: (None, None, "timeout"),
        )
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--draws"])
        assert result.exit_code == 2

    def test_draws_no_header(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-09: --draws --no-header omits header line."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_draws(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--draws", "--no-header"])
        assert result.exit_code == 0
        assert "STATUS" not in result.output


# ===========================================================================
# --passes mode tests (C-10 through C-16)
# ===========================================================================


class TestDiffPassesCLI:
    def test_passes_identical_exit_0(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-10: --passes with identical passes exits 0."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_passes(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--passes"])
        assert result.exit_code == 0
        assert "=" in result.output

    def test_passes_added_exit_1(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-11: --passes with pass added exits 1."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        sa = _stats_resp([{"name": "GBuffer", "draws": 10, "triangles": 5000, "dispatches": 0}])
        sb = _stats_resp(
            [
                {"name": "GBuffer", "draws": 10, "triangles": 5000, "dispatches": 0},
                {"name": "PostFX", "draws": 5, "triangles": 100, "dispatches": 0},
            ]
        )
        _patch_passes(monkeypatch, sa, sb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--passes"])
        assert result.exit_code == 1
        assert "+" in result.output

    def test_passes_removed_exit_1(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-12: --passes with pass removed exits 1."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        sa = _stats_resp(
            [
                {"name": "GBuffer", "draws": 10, "triangles": 5000, "dispatches": 0},
                {"name": "Shadow", "draws": 3, "triangles": 200, "dispatches": 0},
            ]
        )
        sb = _stats_resp([{"name": "GBuffer", "draws": 10, "triangles": 5000, "dispatches": 0}])
        _patch_passes(monkeypatch, sa, sb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--passes"])
        assert result.exit_code == 1
        assert "-" in result.output

    def test_passes_shortstat(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-13: --passes --shortstat produces shortstat format."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_passes(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--passes", "--shortstat"])
        assert result.exit_code == 0
        assert "passes changed" in result.output

    def test_passes_json(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-14: --passes --format json produces valid JSON."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_passes(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--passes", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_passes_unified(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-15: --passes --format unified starts with --- a/ header."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_passes(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--passes", "--format", "unified"])
        assert result.exit_code == 0
        assert "--- a/" in result.output

    def test_passes_query_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-16: --passes when query fails exits 2."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        ctx = _make_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)
        monkeypatch.setattr(
            diff_mod,
            "query_both",
            lambda c, m, p, **kw: (None, None, "timeout"),
        )
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--passes"])
        assert result.exit_code == 2


# ===========================================================================
# summary mode tests (C-02, C-17 through C-20)
# ===========================================================================


class TestDiffSummaryCLI:
    def test_summary_identical_exit_0(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """C-02/C-17: no flag, all identical exits 0, output is 'identical'."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_summary(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b)])
        assert result.exit_code == 0
        assert "identical" in result.output

    def test_summary_draws_differ_exit_1(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """C-18: no flag, draws differ exits 1, output contains draws: line."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        sa = _stats_resp(
            [{"name": "GBuffer", "draws": 10, "triangles": 5000, "dispatches": 0}],
            event_count=100,
        )
        sb = _stats_resp(
            [{"name": "GBuffer", "draws": 15, "triangles": 5000, "dispatches": 0}],
            event_count=100,
        )
        _patch_summary(monkeypatch, sa, sb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b)])
        assert result.exit_code == 1
        assert "draws:" in result.output

    def test_summary_json(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-19: no flag --json produces valid JSON with four keys."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        _patch_summary(monkeypatch)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert set(data.keys()) == {"draws", "passes", "resources", "events"}

    def test_summary_query_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """C-20: no flag, query fails exits 2."""
        a, b = tmp_path / "a.rdc", tmp_path / "b.rdc"
        a.touch()
        b.touch()
        ctx = _make_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)
        monkeypatch.setattr(
            diff_mod,
            "query_both",
            lambda c, m, p, **kw: (None, None, "timeout"),
        )
        result = CliRunner().invoke(diff_cmd, [str(a), str(b)])
        assert result.exit_code == 2
