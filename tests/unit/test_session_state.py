from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from rdc.session_state import is_pid_alive, load_session, session_path


def test_is_pid_alive_for_current_process() -> None:
    assert is_pid_alive(os.getpid()) is True


def test_is_pid_alive_for_invalid_pid() -> None:
    assert is_pid_alive(-1) is False


def test_is_pid_alive_wrong_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """PID alive but cmdline doesn't contain 'rdc' -> False."""
    pid = os.getpid()
    monkeypatch.setattr(
        "rdc.session_state.Path.read_bytes",
        lambda _self: b"nginx\x00--daemon\x00",
    )
    assert is_pid_alive(pid) is False


def test_is_pid_alive_correct_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """PID alive and cmdline contains 'rdc' -> True."""
    pid = os.getpid()
    monkeypatch.setattr(
        "rdc.session_state.Path.read_bytes",
        lambda _self: b"python\x00-m\x00rdc\x00daemon\x00",
    )
    assert is_pid_alive(pid) is True


def test_is_pid_alive_no_proc(monkeypatch: pytest.MonkeyPatch) -> None:
    """When /proc doesn't exist, falls back to kill-only check."""
    pid = os.getpid()
    monkeypatch.setattr(
        "rdc.session_state.Path.read_bytes",
        lambda _self: (_ for _ in ()).throw(OSError("no /proc")),
    )
    assert is_pid_alive(pid) is True


def test_session_path_reads_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RDC_SESSION", "foo")
    assert session_path() == tmp_path / ".rdc" / "sessions" / "foo.json"


def test_session_path_default_no_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RDC_SESSION", raising=False)
    assert session_path() == tmp_path / ".rdc" / "sessions" / "default.json"


def test_session_path_default_empty_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RDC_SESSION", "")
    assert session_path() == tmp_path / ".rdc" / "sessions" / "default.json"


def test_session_path_rejects_traversal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RDC_SESSION", "../../etc/evil")
    assert session_path() == tmp_path / ".rdc" / "sessions" / "default.json"


# --- load_session tests ---

_VALID_SESSION = {
    "capture": "/tmp/test.rdc",
    "current_eid": 42,
    "opened_at": "2026-01-01T00:00:00+00:00",
    "host": "127.0.0.1",
    "port": 9876,
    "token": "abc123",
    "pid": 1234,
}


def test_load_session_corrupt_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Corrupt JSON file returns None and is deleted."""
    monkeypatch.setattr("rdc.session_state._session_dir", lambda: tmp_path / ".rdc" / "sessions")
    session_dir = tmp_path / ".rdc" / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "default.json"
    session_file.write_text("{invalid json")
    monkeypatch.delenv("RDC_SESSION", raising=False)

    result = load_session()
    assert result is None
    assert not session_file.exists()


def test_load_session_missing_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """JSON missing required keys returns None."""
    monkeypatch.setattr("rdc.session_state._session_dir", lambda: tmp_path / ".rdc" / "sessions")
    session_dir = tmp_path / ".rdc" / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "default.json"
    session_file.write_text(json.dumps({"capture": "/tmp/test.rdc"}))
    monkeypatch.delenv("RDC_SESSION", raising=False)

    result = load_session()
    assert result is None
    assert not session_file.exists()


def test_load_session_valid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Valid session file loads correctly (regression)."""
    monkeypatch.setattr("rdc.session_state._session_dir", lambda: tmp_path / ".rdc" / "sessions")
    session_dir = tmp_path / ".rdc" / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "default.json"
    session_file.write_text(json.dumps(_VALID_SESSION))
    monkeypatch.delenv("RDC_SESSION", raising=False)

    result = load_session()
    assert result is not None
    assert result.capture == "/tmp/test.rdc"
    assert result.current_eid == 42
    assert result.port == 9876
    assert result.pid == 1234
