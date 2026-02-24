"""Tests for remote replay in session commands and session service."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from rdc.commands.session import open_cmd, status_cmd
from rdc.services import session_service


class TestOpenCmdRemote:
    def test_remote_option_passes_remote_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        def fake_open_session(
            capture: str | Path, *, remote_url: str | None = None
        ) -> tuple[bool, str]:
            captured.append({"capture": str(capture), "remote_url": remote_url})
            return True, f"opened: {capture}"

        monkeypatch.setattr("rdc.commands.session.open_session", fake_open_session)
        monkeypatch.setattr("rdc.commands.session.session_path", lambda: Path("/tmp/sess"))

        runner = CliRunner()
        result = runner.invoke(open_cmd, ["--remote", "host:39920", "/tmp/frame.rdc"])
        assert result.exit_code == 0
        assert len(captured) == 1
        assert captured[0]["remote_url"] == "host:39920"

    def test_no_remote_option_passes_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: list[dict[str, Any]] = []
        capture_file = tmp_path / "frame.rdc"
        capture_file.touch()

        def fake_open_session(
            capture: str | Path, *, remote_url: str | None = None
        ) -> tuple[bool, str]:
            captured.append({"capture": str(capture), "remote_url": remote_url})
            return True, f"opened: {capture}"

        monkeypatch.setattr("rdc.commands.session.open_session", fake_open_session)
        monkeypatch.setattr("rdc.commands.session.session_path", lambda: Path("/tmp/sess"))

        runner = CliRunner()
        result = runner.invoke(open_cmd, [str(capture_file)])
        assert result.exit_code == 0
        assert len(captured) == 1
        assert captured[0]["remote_url"] is None


class TestStatusCmdRemote:
    def test_status_shows_remote_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rdc.commands.session.status_session",
            lambda: (
                True,
                {
                    "capture": "frame.rdc",
                    "current_eid": 0,
                    "opened_at": "2026-01-01",
                    "daemon": "127.0.0.1:9999 pid=123",
                    "remote": "host:39920",
                },
            ),
        )
        monkeypatch.delenv("RDC_SESSION", raising=False)
        runner = CliRunner()
        result = runner.invoke(status_cmd)
        assert result.exit_code == 0
        assert "remote: host:39920" in result.output

    def test_status_no_remote_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rdc.commands.session.status_session",
            lambda: (
                True,
                {
                    "capture": "frame.rdc",
                    "current_eid": 0,
                    "opened_at": "2026-01-01",
                    "daemon": "127.0.0.1:9999 pid=123",
                },
            ),
        )
        monkeypatch.delenv("RDC_SESSION", raising=False)
        runner = CliRunner()
        result = runner.invoke(status_cmd)
        assert result.exit_code == 0
        assert "remote:" not in result.output


class TestStartDaemonRemote:
    def test_remote_url_appended_to_cmd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(session_service, "_renderdoc_available", lambda: False)
        captured_cmd: list[str] = []

        def fake_popen(cmd: list[str], **kwargs: object) -> MagicMock:
            captured_cmd.extend(cmd)
            return MagicMock()

        monkeypatch.setattr(session_service.subprocess, "Popen", fake_popen)
        session_service.start_daemon("frame.rdc", 9999, "tok", remote_url="host:39920")
        assert "--remote-url" in captured_cmd
        idx = captured_cmd.index("--remote-url")
        assert captured_cmd[idx + 1] == "host:39920"

    def test_no_remote_url_no_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(session_service, "_renderdoc_available", lambda: False)
        captured_cmd: list[str] = []

        def fake_popen(cmd: list[str], **kwargs: object) -> MagicMock:
            captured_cmd.extend(cmd)
            return MagicMock()

        monkeypatch.setattr(session_service.subprocess, "Popen", fake_popen)
        session_service.start_daemon("frame.rdc", 9999, "tok")
        assert "--remote-url" not in captured_cmd

    def test_remote_url_skips_no_replay(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(session_service, "_renderdoc_available", lambda: False)
        captured_cmd: list[str] = []

        def fake_popen(cmd: list[str], **kwargs: object) -> MagicMock:
            captured_cmd.extend(cmd)
            return MagicMock()

        monkeypatch.setattr(session_service.subprocess, "Popen", fake_popen)
        session_service.start_daemon("frame.rdc", 9999, "tok", remote_url="host:39920")
        assert "--no-replay" not in captured_cmd
        assert "--remote-url" in captured_cmd
