"""Tests for rdc cbuffer CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from rdc.cli import main
from rdc.commands.cbuffer import cbuffer_cmd

_DECODE_RESPONSE: dict[str, Any] = {
    "eid": 10,
    "set": 0,
    "binding": 0,
    "variables": [{"name": "mvp", "type": "mat4", "value": [1.0, 0.0, 0.0, 0.0]}],
}


class TestCbufferCmd:
    def test_json_default(self, monkeypatch: Any) -> None:
        monkeypatch.setattr("rdc.commands.cbuffer.call", lambda m, p: dict(_DECODE_RESPONSE))
        runner = CliRunner()
        result = runner.invoke(cbuffer_cmd, ["10", "--stage", "ps", "--set", "0", "--binding", "0"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["variables"] == _DECODE_RESPONSE["variables"]
        assert data["set"] == 0

    def test_json_explicit_flag(self, monkeypatch: Any) -> None:
        monkeypatch.setattr("rdc.commands.cbuffer.call", lambda m, p: dict(_DECODE_RESPONSE))
        runner = CliRunner()
        result = runner.invoke(cbuffer_cmd, ["10", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == _DECODE_RESPONSE

    def test_decode_params_forwarded(self, monkeypatch: Any) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        def mock_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
            calls.append((method, params))
            return dict(_DECODE_RESPONSE)

        monkeypatch.setattr("rdc.commands.cbuffer.call", mock_call)
        runner = CliRunner()
        result = runner.invoke(cbuffer_cmd, ["7", "--stage", "vs", "--set", "1", "--binding", "2"])
        assert result.exit_code == 0
        assert calls[0][0] == "cbuffer_decode"
        assert calls[0][1] == {"eid": 7, "stage": "vs", "set": 1, "binding": 2}

    def test_raw_output(self, monkeypatch: Any, tmp_path: Path) -> None:
        out = tmp_path / "cb.bin"
        captured: dict[str, Any] = {}

        def mock_export(vfs_path: str, output: str | None, raw: bool) -> None:
            captured["vfs_path"] = vfs_path
            captured["output"] = output
            Path(output).write_bytes(bytes(range(16)))

        monkeypatch.setattr("rdc.commands.cbuffer._export_vfs_path", mock_export)
        runner = CliRunner()
        result = runner.invoke(cbuffer_cmd, ["10", "--raw", "-o", str(out)])
        assert result.exit_code == 0
        assert out.read_bytes() == bytes(range(16))
        assert captured["vfs_path"] == "/draws/10/cbuffer/0/0/data"

    def test_raw_without_output(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(
            "rdc.commands.cbuffer._export_vfs_path",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not be called")),
        )
        runner = CliRunner()
        result = runner.invoke(cbuffer_cmd, ["10", "--raw"])
        assert result.exit_code != 0
        assert "-o" in result.output or "output" in result.output.lower()

    def test_no_session(self, monkeypatch: Any) -> None:
        def mock_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
            raise SystemExit(1)

        monkeypatch.setattr("rdc.commands.cbuffer.call", mock_call)
        runner = CliRunner()
        result = runner.invoke(cbuffer_cmd, ["10"])
        assert result.exit_code == 1

    def test_eid_omitted_uses_completion_fallback(self, monkeypatch: Any) -> None:
        calls: list[dict[str, Any]] = []

        def mock_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
            calls.append(params)
            return dict(_DECODE_RESPONSE)

        monkeypatch.setattr("rdc.commands.cbuffer.call", mock_call)
        runner = CliRunner()
        result = runner.invoke(cbuffer_cmd, [])
        assert result.exit_code == 0
        assert "eid" not in calls[0]

    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cbuffer_cmd, ["--help"])
        assert result.exit_code == 0
        assert "EID" in result.output
        assert "--stage" in result.output
        assert "--raw" in result.output

    def test_in_main_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "cbuffer" in result.output
