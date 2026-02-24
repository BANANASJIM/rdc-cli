from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from rdc.cli import main


def _session_file(home: Path) -> Path:
    return home / ".rdc" / "sessions" / "default.json"


def test_open_status_goto_close_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
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


def test_goto_without_session_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RDC_SESSION", raising=False)
    runner = CliRunner()

    result = runner.invoke(main, ["goto", "1"])
    assert result.exit_code == 1


def test_close_without_session_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RDC_SESSION", raising=False)
    runner = CliRunner()

    result = runner.invoke(main, ["close"])
    assert result.exit_code == 1


def test_goto_rejects_negative_eid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    runner = CliRunner()

    runner.invoke(main, ["open", "capture.rdc"])
    result = runner.invoke(main, ["goto", "-1"])
    assert result.exit_code != 0


def test_status_shows_session_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """rdc status first line is 'session: <name>' matching active RDC_SESSION."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RDC_SESSION", "mytest")
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    runner = CliRunner()

    runner.invoke(main, ["open", "capture.rdc"])
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0] == "session: mytest"


def test_status_shows_default_session_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without --session, status first line is 'session: default'."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    runner = CliRunner()

    runner.invoke(main, ["open", "capture.rdc"])
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0] == "session: default"


def test_require_session_cleans_stale_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    """B18: require_session() detects dead daemon PID and cleans up."""
    import rdc.commands._helpers as helpers_mod
    from rdc.session_state import SessionState

    session = SessionState(
        capture="test.rdc",
        current_eid=0,
        opened_at="2024-01-01",
        host="127.0.0.1",
        port=9999,
        token="tok",
        pid=99999,
    )
    monkeypatch.setattr(helpers_mod, "load_session", lambda: session)
    monkeypatch.setattr("rdc.session_state.is_pid_alive", lambda pid: False)
    deleted: list[bool] = []
    monkeypatch.setattr("rdc.session_state.delete_session", lambda: (deleted.append(True), True)[1])

    with pytest.raises(SystemExit):
        helpers_mod.require_session()
    assert deleted


def test_open_no_replay_mode_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """B23: open command warns when renderdoc is unavailable."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    runner = CliRunner()

    result = runner.invoke(main, ["open", "capture.rdc"])
    assert result.exit_code == 0
    assert "no-replay mode" in result.output
    assert "warning" in result.stderr
