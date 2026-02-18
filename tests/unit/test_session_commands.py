from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from rdc.cli import main


def _session_file(home: Path) -> Path:
    return home / ".rdc" / "sessions" / "default.json"


def test_open_status_goto_close_flow(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    result_open = runner.invoke(main, ["open", "capture.rdc"])
    assert result_open.exit_code == 0
    assert _session_file(tmp_path).exists()

    result_status_1 = runner.invoke(main, ["status"])
    assert result_status_1.exit_code == 0
    assert "capture.rdc" in result_status_1.output
    assert "current_eid: 0" in result_status_1.output

    result_goto = runner.invoke(main, ["goto", "142"])
    assert result_goto.exit_code == 0

    result_status_2 = runner.invoke(main, ["status"])
    assert result_status_2.exit_code == 0
    assert "current_eid: 142" in result_status_2.output

    result_close = runner.invoke(main, ["close"])
    assert result_close.exit_code == 0
    assert not _session_file(tmp_path).exists()


def test_goto_without_session_fails(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    result = runner.invoke(main, ["goto", "1"])
    assert result.exit_code == 1


def test_close_without_session_fails(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    result = runner.invoke(main, ["close"])
    assert result.exit_code == 1


def test_goto_rejects_negative_eid(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    runner.invoke(main, ["open", "capture.rdc"])
    result = runner.invoke(main, ["goto", "-1"])
    assert result.exit_code != 0
