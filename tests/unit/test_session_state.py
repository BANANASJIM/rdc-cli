from __future__ import annotations

import os
from pathlib import Path

import pytest

from rdc.session_state import is_pid_alive, session_path


def test_is_pid_alive_for_current_process() -> None:
    assert is_pid_alive(os.getpid()) is True


def test_is_pid_alive_for_invalid_pid() -> None:
    assert is_pid_alive(-1) is False


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
