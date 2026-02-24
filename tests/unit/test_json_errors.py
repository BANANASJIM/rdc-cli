"""Tests for B2: JSON-aware error output in _helpers and assert_ci."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import click
from click.testing import CliRunner

import rdc.commands._helpers as helpers_mod
import rdc.commands.assert_ci as assert_ci_mod
from rdc.cli import main
from rdc.commands._helpers import _json_mode, call, require_session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_session() -> MagicMock:
    return MagicMock(host="localhost", port=9876, token="tok" * 4)


# ---------------------------------------------------------------------------
# require_session — plain text
# ---------------------------------------------------------------------------


def test_require_session_no_json_plain_error(monkeypatch: Any) -> None:
    """No --json flag: stderr contains plain-text error."""
    monkeypatch.setattr(helpers_mod, "load_session", lambda: None)

    @click.command("dummy")
    def cmd() -> None:
        require_session()

    runner = CliRunner()
    result = runner.invoke(cmd, [])
    assert result.exit_code == 1
    assert "error:" in result.stderr
    assert not result.stderr.strip().startswith("{")


# ---------------------------------------------------------------------------
# require_session — JSON
# ---------------------------------------------------------------------------


def test_require_session_json_error(monkeypatch: Any) -> None:
    """With --json flag: stderr is valid JSON error envelope."""
    monkeypatch.setattr(helpers_mod, "load_session", lambda: None)

    @click.command("dummy")
    @click.option("--json", "use_json", is_flag=True)
    def cmd(use_json: bool) -> None:
        require_session()

    runner = CliRunner()
    result = runner.invoke(cmd, ["--json"])
    assert result.exit_code == 1
    data = json.loads(result.stderr.strip())
    assert "error" in data
    assert isinstance(data["error"]["message"], str)
    assert len(data["error"]["message"]) > 0


# ---------------------------------------------------------------------------
# call — OSError plain
# ---------------------------------------------------------------------------


def test_call_oserror_plain_error(monkeypatch: Any) -> None:
    """OSError without --json: plain text on stderr."""
    monkeypatch.setattr(helpers_mod, "load_session", lambda: _fake_session())
    monkeypatch.setattr(helpers_mod, "send_request", _raise_oserror)

    @click.command("dummy")
    def cmd() -> None:
        call("ping", {})

    runner = CliRunner()
    result = runner.invoke(cmd, [])
    assert result.exit_code == 1
    assert "daemon unreachable" in result.stderr
    assert not result.stderr.strip().startswith("{")


def _raise_oserror(*_a: Any, **_kw: Any) -> None:
    raise OSError("connection refused")


# ---------------------------------------------------------------------------
# call — OSError JSON
# ---------------------------------------------------------------------------


def test_call_oserror_json_error(monkeypatch: Any) -> None:
    """OSError with --json: JSON envelope on stderr."""
    monkeypatch.setattr(helpers_mod, "load_session", lambda: _fake_session())
    monkeypatch.setattr(helpers_mod, "send_request", _raise_oserror)

    @click.command("dummy")
    @click.option("--json", "use_json", is_flag=True)
    def cmd(use_json: bool) -> None:
        call("ping", {})

    runner = CliRunner()
    result = runner.invoke(cmd, ["--json"])
    assert result.exit_code == 1
    data = json.loads(result.stderr.strip())
    assert "error" in data
    assert "unreachable" in data["error"]["message"]


# ---------------------------------------------------------------------------
# call — daemon error plain
# ---------------------------------------------------------------------------


def test_call_daemon_error_plain(monkeypatch: Any) -> None:
    """Daemon error without --json: plain text."""
    monkeypatch.setattr(helpers_mod, "load_session", lambda: _fake_session())
    monkeypatch.setattr(
        helpers_mod,
        "send_request",
        lambda *a, **kw: {"error": {"message": "no capture loaded"}},
    )

    @click.command("dummy")
    def cmd() -> None:
        call("ping", {})

    runner = CliRunner()
    result = runner.invoke(cmd, [])
    assert result.exit_code == 1
    assert "no capture loaded" in result.stderr
    assert not result.stderr.strip().startswith("{")


# ---------------------------------------------------------------------------
# call — daemon error JSON
# ---------------------------------------------------------------------------


def test_call_daemon_error_json(monkeypatch: Any) -> None:
    """Daemon error with --json: JSON on stderr."""
    monkeypatch.setattr(helpers_mod, "load_session", lambda: _fake_session())
    monkeypatch.setattr(
        helpers_mod,
        "send_request",
        lambda *a, **kw: {"error": {"message": "no capture loaded"}},
    )

    @click.command("dummy")
    @click.option("--json", "use_json", is_flag=True)
    def cmd(use_json: bool) -> None:
        call("ping", {})

    runner = CliRunner()
    result = runner.invoke(cmd, ["--json"])
    assert result.exit_code == 1
    data = json.loads(result.stderr.strip())
    assert data == {"error": {"message": "no capture loaded"}}


# ---------------------------------------------------------------------------
# assert_ci — JSON error (no session)
# ---------------------------------------------------------------------------


def test_assert_ci_json_error_no_session(monkeypatch: Any) -> None:
    """assert-count --json with no session: JSON error on stderr, exit 2."""
    monkeypatch.setattr(assert_ci_mod, "load_session", lambda: None)

    runner = CliRunner()
    result = runner.invoke(main, ["assert-count", "draws", "--expect", "1", "--json"])
    assert result.exit_code == 2
    data = json.loads(result.stderr.strip())
    assert "error" in data
    assert isinstance(data["error"]["message"], str)


# ---------------------------------------------------------------------------
# assert_ci — plain error (no session)
# ---------------------------------------------------------------------------


def test_assert_ci_plain_error_no_session(monkeypatch: Any) -> None:
    """assert-count without --json and no session: plain error, exit 2."""
    monkeypatch.setattr(assert_ci_mod, "load_session", lambda: None)

    runner = CliRunner()
    result = runner.invoke(main, ["assert-count", "draws", "--expect", "1"])
    assert result.exit_code == 2
    assert "error:" in result.stderr
    assert not result.stderr.strip().startswith("{")


# ---------------------------------------------------------------------------
# _json_mode — no Click context
# ---------------------------------------------------------------------------


def test_json_mode_false_without_context() -> None:
    """_json_mode() returns False when called outside a Click invocation."""
    assert _json_mode() is False


# ---------------------------------------------------------------------------
# B10: call() catches ValueError (transport overflow)
# ---------------------------------------------------------------------------


def _raise_value_error(*_a: Any, **_kw: Any) -> None:
    raise ValueError("recv_line: message exceeds max_bytes limit")


def test_call_catches_value_error(monkeypatch: Any) -> None:
    """call() must catch ValueError and exit rc=1."""
    monkeypatch.setattr(helpers_mod, "load_session", lambda: _fake_session())
    monkeypatch.setattr(helpers_mod, "send_request", _raise_value_error)

    @click.command("dummy")
    def cmd() -> None:
        call("ping", {})

    runner = CliRunner()
    result = runner.invoke(cmd, [])
    assert result.exit_code == 1
    assert "daemon unreachable" in result.stderr
