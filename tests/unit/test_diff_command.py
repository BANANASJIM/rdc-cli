from __future__ import annotations

from pathlib import Path
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


# ---------------------------------------------------------------------------
# #26  Happy path → exit 0
# ---------------------------------------------------------------------------


def test_diff_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    ctx = _make_ctx()
    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

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
# #30  Mode stub raises → cleanup still runs
# ---------------------------------------------------------------------------


def test_diff_cleanup_on_stub_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    ctx = _make_ctx()
    stop_called = MagicMock()
    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", stop_called)

    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b), "--draws"])
    assert stop_called.called
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# #31  --draws → mode dispatched
# ---------------------------------------------------------------------------


def test_diff_draws_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    ctx = _make_ctx()
    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b), "--draws"])
    assert result.exit_code == 2
    assert "not yet implemented" in result.output.lower()


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

    # Pipeline is now implemented — without mocking query_both it
    # reports "both daemons failed" (exit 2), proving dispatch works.
    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b), "--pipeline", "vs"])
    assert result.exit_code == 2
    assert "both daemons failed" in result.output


# ---------------------------------------------------------------------------
# #33  No flag → summary
# ---------------------------------------------------------------------------


def test_diff_default_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    ctx = _make_ctx()
    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# #34  --json forwarded
# ---------------------------------------------------------------------------


def test_diff_json_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    ctx = _make_ctx()
    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b), "--json"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# #35  --no-header forwarded
# ---------------------------------------------------------------------------


def test_diff_no_header_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    ctx = _make_ctx()
    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

    runner = CliRunner()
    result = runner.invoke(diff_cmd, [str(a), str(b), "--no-header"])
    assert result.exit_code == 0
