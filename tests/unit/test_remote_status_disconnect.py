"""Tests for `rdc remote status` and `rdc remote disconnect`."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner

from rdc.commands.remote import (
    remote_disconnect_cmd,
    remote_group,
    remote_status_cmd,
)
from rdc.remote_state import RemoteServerState, save_remote_state


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")


def _stderr_spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    lines: list[str] = []
    orig = click.echo

    def spy(message: Any = None, err: bool = False, **kw: Any) -> Any:
        if err:
            lines.append(str(message))
        return orig(message, err=err, **kw)

    monkeypatch.setattr("rdc.commands.remote.click.echo", spy)
    return lines


def _save(host: str = "192.168.1.42", port: int = 39920, at: float | None = None) -> None:
    save_remote_state(
        RemoteServerState(host=host, port=port, connected_at=at if at is not None else time.time())
    )


class TestRemoteStatus:
    def test_with_state_prints_fields(self) -> None:
        _save(at=time.time() - 3700)
        result = CliRunner().invoke(remote_status_cmd, [])
        assert result.exit_code == 0
        assert "host: 192.168.1.42" in result.output
        assert "port: 39920" in result.output
        assert "saved_at:" in result.output
        assert "age: 1h" in result.output

    def test_with_state_json(self) -> None:
        _save(at=time.time() - 120)
        result = CliRunner().invoke(remote_status_cmd, ["--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["host"] == "192.168.1.42"
        assert data["port"] == 39920
        assert "saved_at" in data
        assert "age" in data

    def test_no_state_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        lines = _stderr_spy(monkeypatch)
        result = CliRunner().invoke(remote_status_cmd, [])
        assert result.exit_code == 0
        assert any("no saved remote state" in s for s in lines)
        assert any("rdc remote setup" in s for s in lines)

    def test_no_state_json(self) -> None:
        result = CliRunner().invoke(remote_status_cmd, ["--json"])
        assert result.exit_code == 0
        assert json.loads(result.output) == {"state": None}


class TestRemoteDisconnect:
    def test_with_state_deletes(self) -> None:
        _save()
        result = CliRunner().invoke(remote_disconnect_cmd, [])
        assert result.exit_code == 0
        assert "disconnected: 192.168.1.42:39920" in result.output
        # Re-running should say "nothing to disconnect"
        result2 = CliRunner().invoke(remote_disconnect_cmd, [])
        assert result2.exit_code == 0

    def test_with_state_json(self) -> None:
        _save()
        result = CliRunner().invoke(remote_disconnect_cmd, ["--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"disconnected": "192.168.1.42:39920"}

    def test_no_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        lines = _stderr_spy(monkeypatch)
        result = CliRunner().invoke(remote_disconnect_cmd, [])
        assert result.exit_code == 0
        assert any("nothing to disconnect" in s for s in lines)

    def test_no_state_json(self) -> None:
        result = CliRunner().invoke(remote_disconnect_cmd, ["--json"])
        assert result.exit_code == 0
        assert json.loads(result.output) == {"disconnected": None}


class TestGroupRegistration:
    def test_group_lists_new_commands(self) -> None:
        result = CliRunner().invoke(remote_group, ["--help"])
        assert result.exit_code == 0
        assert "setup" in result.output
        assert "status" in result.output
        assert "disconnect" in result.output
