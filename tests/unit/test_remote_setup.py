"""Tests for `rdc remote setup` command and its helpers."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from rdc.commands.remote import (
    _setup_hint_for,
    _tcp_probe,
    remote_setup_cmd,
)


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


class TestTcpProbe:
    def test_success_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sock = MagicMock()
        sock.__enter__ = MagicMock(return_value=sock)
        sock.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: sock)
        assert _tcp_probe("h", 1, 1.0) is None

    def test_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_refused(*a: Any, **kw: Any) -> None:
            raise ConnectionRefusedError

        monkeypatch.setattr(socket, "create_connection", raise_refused)
        assert _tcp_probe("h", 1, 1.0) == "refused"

    def test_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_timeout(*a: Any, **kw: Any) -> None:
            raise TimeoutError

        monkeypatch.setattr(socket, "create_connection", raise_timeout)
        assert _tcp_probe("h", 1, 1.0) == "timeout"

    def test_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_os(*a: Any, **kw: Any) -> None:
            raise OSError("no route")

        monkeypatch.setattr(socket, "create_connection", raise_os)
        assert _tcp_probe("h", 1, 1.0) == "unreachable"


class TestSetupHintFor:
    def test_refused_mentions_rdc_serve(self) -> None:
        msg = _setup_hint_for("refused", "target", 39920)
        assert "rdc serve" in msg
        assert "target:39920" in msg
        assert "--daemon" in msg

    def test_timeout_mentions_network(self) -> None:
        msg = _setup_hint_for("timeout", "target", 39920, 5.0)
        assert "5s" in msg
        assert "firewall" in msg or "network" in msg

    def test_unreachable_mentions_hostname(self) -> None:
        msg = _setup_hint_for("unreachable", "bad-host", 39920)
        assert "bad-host" in msg
        assert "hostname" in msg or "route" in msg

    def test_ping_failed_mentions_handshake(self) -> None:
        msg = _setup_hint_for("ping_failed", "target", 39920)
        assert "handshake" in msg
        assert "renderdoccmd" in msg
        assert "rdc doctor" in msg

    def test_unknown_falls_through(self) -> None:
        assert "unknown" in _setup_hint_for("whatever", "h", 1)


class TestRemoteSetupCmd:
    def _patch_rd(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        rd = MagicMock()
        monkeypatch.setattr("rdc.commands._helpers.find_renderdoc", lambda: rd)
        return rd

    def test_success_saves_state_and_prints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_rd(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote._tcp_probe", lambda *a, **kw: None)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        saved: list[Any] = []
        monkeypatch.setattr(
            "rdc.commands.remote.save_remote_state", lambda state: saved.append(state)
        )

        result = CliRunner().invoke(remote_setup_cmd, ["192.168.1.10"])
        assert result.exit_code == 0
        assert "connected: 192.168.1.10:39920" in result.output
        assert len(saved) == 1
        assert saved[0].host == "192.168.1.10"
        assert saved[0].port == 39920

    def test_success_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_rd(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote._tcp_probe", lambda *a, **kw: None)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        monkeypatch.setattr("rdc.commands.remote.save_remote_state", lambda state: None)

        result = CliRunner().invoke(remote_setup_cmd, ["192.168.1.10", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"host": "192.168.1.10", "port": 39920, "next": "rdc remote list"}

    def test_refused_emits_hint_and_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        lines = _stderr_spy(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote._tcp_probe", lambda *a, **kw: "refused")
        saved: list[Any] = []
        monkeypatch.setattr(
            "rdc.commands.remote.save_remote_state", lambda state: saved.append(state)
        )

        result = CliRunner().invoke(remote_setup_cmd, ["192.168.1.10"])
        assert result.exit_code == 1
        assert saved == []
        assert any("connection refused" in s for s in lines)
        assert any("rdc serve" in s for s in lines)

    def test_timeout_emits_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        lines = _stderr_spy(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote._tcp_probe", lambda *a, **kw: "timeout")
        result = CliRunner().invoke(remote_setup_cmd, ["192.168.1.10", "--timeout", "3"])
        assert result.exit_code == 1
        assert any("timeout" in s for s in lines)
        assert any("3s" in s for s in lines)

    def test_unreachable_emits_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        lines = _stderr_spy(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote._tcp_probe", lambda *a, **kw: "unreachable")
        result = CliRunner().invoke(remote_setup_cmd, ["192.168.1.10"])
        assert result.exit_code == 1
        assert any("unreachable" in s for s in lines)

    def test_ping_failed_emits_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_rd(monkeypatch)
        lines = _stderr_spy(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote._tcp_probe", lambda *a, **kw: None)
        remote = MagicMock()
        remote.Ping.side_effect = RuntimeError("proto mismatch")
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: remote,
        )

        result = CliRunner().invoke(remote_setup_cmd, ["192.168.1.10"])
        assert result.exit_code == 1
        assert any("handshake failed" in s for s in lines)
        assert any("rdc doctor" in s for s in lines)
        remote.ShutdownConnection.assert_called_once()

    def test_failure_json_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        lines = _stderr_spy(monkeypatch)
        monkeypatch.setattr("rdc.commands.remote._tcp_probe", lambda *a, **kw: "refused")

        result = CliRunner().invoke(remote_setup_cmd, ["192.168.1.10", "--json"])
        assert result.exit_code == 1
        assert lines, "expected stderr output"
        payload = json.loads(lines[0])
        assert payload["host"] == "192.168.1.10"
        assert payload["port"] == 39920
        assert payload["failure"] == "refused"
        assert "hint" in payload
        assert "error" in payload

    def test_timeout_flag_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_rd(monkeypatch)
        captured: dict[str, Any] = {}

        def fake_probe(host: str, port: int, timeout_s: float) -> str | None:
            captured["timeout_s"] = timeout_s
            return None

        monkeypatch.setattr("rdc.commands.remote._tcp_probe", fake_probe)
        monkeypatch.setattr(
            "rdc.commands.remote.connect_remote_server",
            lambda rd, url: MagicMock(),
        )
        monkeypatch.setattr("rdc.commands.remote.save_remote_state", lambda state: None)

        result = CliRunner().invoke(remote_setup_cmd, ["192.168.1.10", "--timeout", "7.5"])
        assert result.exit_code == 0
        assert captured["timeout_s"] == 7.5

    def test_bad_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = CliRunner().invoke(remote_setup_cmd, ["host:notanint"])
        assert result.exit_code == 1

    def test_help(self) -> None:
        result = CliRunner().invoke(remote_setup_cmd, ["--help"])
        assert result.exit_code == 0
