from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from rdc.cli import main


def test_session_flag_sets_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--session NAME sets RDC_SESSION before subcommand runs."""
    captured_env: dict[str, str] = {}
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RDC_SESSION", raising=False)

    def fake_status() -> tuple[bool, object]:
        captured_env["RDC_SESSION"] = os.environ.get("RDC_SESSION", "")
        return False, "no session"

    monkeypatch.setattr("rdc.commands.session.status_session", fake_status)
    runner = CliRunner()
    runner.invoke(main, ["--session", "baseline", "status"])
    assert captured_env.get("RDC_SESSION") == "baseline"


def test_session_flag_overrides_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--session NAME overrides a pre-existing RDC_SESSION value."""
    captured_env: dict[str, str] = {}
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RDC_SESSION", "old")

    def fake_status() -> tuple[bool, object]:
        captured_env["RDC_SESSION"] = os.environ.get("RDC_SESSION", "")
        return False, "no session"

    monkeypatch.setattr("rdc.commands.session.status_session", fake_status)
    runner = CliRunner()
    runner.invoke(main, ["--session", "new", "status"])
    assert captured_env.get("RDC_SESSION") == "new"


def test_session_flag_invalid_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Name containing '/' is rejected with exit code 2."""
    monkeypatch.delenv("RDC_SESSION", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["--session", "a/b", "status"])
    assert result.exit_code == 2
    assert "session" in result.output.lower() or "invalid" in result.output.lower()


def test_session_flag_invalid_too_long(monkeypatch: pytest.MonkeyPatch) -> None:
    """Name longer than 64 chars is rejected with exit code 2."""
    monkeypatch.delenv("RDC_SESSION", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["--session", "a" * 65, "status"])
    assert result.exit_code == 2


def test_session_flag_valid_chars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Names with hyphens and underscores are accepted."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RDC_SESSION", raising=False)

    def fake_status() -> tuple[bool, object]:
        return False, "no session"

    for name in ("my-session", "session_1", "ABC"):
        monkeypatch.setattr("rdc.commands.session.status_session", fake_status)
        runner = CliRunner()
        result = runner.invoke(main, ["--session", name, "status"])
        assert result.exit_code != 2, f"name {name!r} should be valid"


def test_two_sessions_isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Two named sessions return independent data from their respective files."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    runner = CliRunner()

    # Open session "a"
    alpha_file = tmp_path / "alpha.rdc"
    alpha_file.touch()
    monkeypatch.setenv("RDC_SESSION", "a")
    result = runner.invoke(main, ["open", str(alpha_file)])
    assert result.exit_code == 0
    assert (tmp_path / ".rdc" / "sessions" / "a.json").exists()

    # Open session "b"
    beta_file = tmp_path / "beta.rdc"
    beta_file.touch()
    monkeypatch.setenv("RDC_SESSION", "b")
    result = runner.invoke(main, ["open", str(beta_file)])
    assert result.exit_code == 0
    assert (tmp_path / ".rdc" / "sessions" / "b.json").exists()

    # Status for "a" shows alpha.rdc
    monkeypatch.setenv("RDC_SESSION", "a")
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "alpha.rdc" in result.output
    assert "beta.rdc" not in result.output

    # Status for "b" shows beta.rdc
    monkeypatch.setenv("RDC_SESSION", "b")
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "beta.rdc" in result.output
    assert "alpha.rdc" not in result.output
