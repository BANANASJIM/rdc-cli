from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rdc.session_state import (
    SessionState,
    is_pid_alive,
    load_session,
    save_session,
    session_path,
)


def test_is_pid_alive_for_current_process() -> None:
    assert is_pid_alive(os.getpid()) is True


def test_is_pid_alive_for_invalid_pid() -> None:
    assert is_pid_alive(-1) is False


@pytest.mark.skipif(sys.platform != "linux", reason="Linux /proc variant")
def test_is_pid_alive_wrong_process_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """PID alive but cmdline doesn't contain 'rdc' -> False (Linux)."""
    pid = os.getpid()
    monkeypatch.setattr(
        "rdc._platform.Path.read_bytes",
        lambda _self: b"nginx\x00--daemon\x00",
    )
    assert is_pid_alive(pid) is False


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS ps variant")
def test_is_pid_alive_wrong_process_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    """PID alive but ps output doesn't contain 'rdc' -> False (macOS)."""
    pid = os.getpid()
    monkeypatch.setattr(
        "rdc._platform.subprocess.run",
        lambda *_a, **_kw: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="nginx --daemon\n"
        ),
    )
    assert is_pid_alive(pid) is False


@pytest.mark.skipif(sys.platform != "linux", reason="Linux /proc variant")
def test_is_pid_alive_correct_process_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """PID alive and cmdline contains 'rdc' -> True (Linux)."""
    pid = os.getpid()
    monkeypatch.setattr(
        "rdc._platform.Path.read_bytes",
        lambda _self: b"python\x00-m\x00rdc\x00daemon\x00",
    )
    assert is_pid_alive(pid) is True


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS ps variant")
def test_is_pid_alive_correct_process_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    """PID alive and ps output contains 'rdc' -> True (macOS)."""
    pid = os.getpid()
    monkeypatch.setattr(
        "rdc._platform.subprocess.run",
        lambda *_a, **_kw: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="python -m rdc daemon\n"
        ),
    )
    assert is_pid_alive(pid) is True


@pytest.mark.skipif(sys.platform != "linux", reason="Linux /proc variant")
def test_is_pid_alive_no_proc_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """When /proc doesn't exist, falls back to kill-only check (Linux)."""
    pid = os.getpid()
    monkeypatch.setattr(
        "rdc._platform.Path.read_bytes",
        lambda _self: (_ for _ in ()).throw(OSError("no /proc")),
    )
    assert is_pid_alive(pid) is True


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS ps variant")
def test_is_pid_alive_no_proc_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ps raises SubprocessError, falls back to kill-only check (macOS)."""
    pid = os.getpid()

    def _raise(*_a: object, **_kw: object) -> None:
        raise subprocess.SubprocessError("ps failed")

    monkeypatch.setattr("rdc._platform.subprocess.run", _raise)
    assert is_pid_alive(pid) is True


def test_session_path_reads_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.setenv("RDC_SESSION", "foo")
    assert session_path() == tmp_path / ".rdc" / "sessions" / "foo.json"


def test_session_path_default_no_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    assert session_path() == tmp_path / ".rdc" / "sessions" / "default.json"


def test_session_path_default_empty_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.setenv("RDC_SESSION", "")
    assert session_path() == tmp_path / ".rdc" / "sessions" / "default.json"


def test_session_path_rejects_traversal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
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


# --- P0-SEC-1: save_session permission tests ---

_SAMPLE_STATE = SessionState(
    capture="/tmp/test.rdc",
    current_eid=0,
    opened_at="2026-01-01T00:00:00+00:00",
    host="127.0.0.1",
    port=9876,
    token="secret-token",
    pid=1234,
)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix file permissions not enforced on NTFS")
def test_save_session_file_mode_0600(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Session file must be created with mode 0o600 (owner read/write only)."""
    monkeypatch.setattr("rdc.session_state._session_dir", lambda: tmp_path / "sessions")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    save_session(_SAMPLE_STATE)
    session_file = tmp_path / "sessions" / "default.json"
    assert session_file.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="Unix file permissions not enforced on NTFS")
def test_save_session_dir_mode_0700(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Session directory must be set to mode 0o700 (owner only)."""
    monkeypatch.setattr("rdc.session_state._session_dir", lambda: tmp_path / "sessions")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    save_session(_SAMPLE_STATE)
    session_dir = tmp_path / "sessions"
    assert session_dir.stat().st_mode & 0o777 == 0o700


@pytest.mark.skipif(sys.platform == "win32", reason="Unix file permissions not enforced on NTFS")
def test_save_session_umask_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Permissions hold even under a permissive umask (0o022)."""
    monkeypatch.setattr("rdc.session_state._session_dir", lambda: tmp_path / "sessions")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    old_umask = os.umask(0o022)
    try:
        save_session(_SAMPLE_STATE)
    finally:
        os.umask(old_umask)
    session_file = tmp_path / "sessions" / "default.json"
    session_dir = tmp_path / "sessions"
    assert session_file.stat().st_mode & 0o777 == 0o600
    assert session_dir.stat().st_mode & 0o777 == 0o700


@pytest.mark.skipif(sys.platform == "win32", reason="Unix file permissions not enforced on NTFS")
def test_save_session_corrects_existing_file_perms(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Overwriting an existing 0o644 file must correct permissions to 0o600."""
    monkeypatch.setattr("rdc.session_state._session_dir", lambda: tmp_path / "sessions")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    session_dir = tmp_path / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "default.json"
    session_file.write_text("{}")
    session_file.chmod(0o644)
    save_session(_SAMPLE_STATE)
    assert session_file.stat().st_mode & 0o777 == 0o600


def test_save_then_load_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """load_session reads back data correctly after the permission-hardened save."""
    monkeypatch.setattr("rdc.session_state._session_dir", lambda: tmp_path / "sessions")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    save_session(_SAMPLE_STATE)
    result = load_session()
    assert result is not None
    assert result.capture == _SAMPLE_STATE.capture
    assert result.token == _SAMPLE_STATE.token
    assert result.port == _SAMPLE_STATE.port
