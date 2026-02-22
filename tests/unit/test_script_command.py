"""Tests for CLI script command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from rdc.cli import main


def _patch_daemon(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]) -> None:
    """Patch load_session and send_request for CLI tests."""
    import rdc.commands._helpers as helpers_mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(helpers_mod, "load_session", lambda: session)
    monkeypatch.setattr(helpers_mod, "send_request", lambda _h, _p, _payload: response)


def _success_response(
    stdout: str = "",
    stderr: str = "",
    elapsed_ms: int = 42,
    return_value: Any = None,
) -> dict[str, Any]:
    return {
        "result": {
            "stdout": stdout,
            "stderr": stderr,
            "elapsed_ms": elapsed_ms,
            "return_value": return_value,
        }
    }


class TestScriptDefaultOutput:
    def test_stdout_content(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        _patch_daemon(monkeypatch, _success_response(stdout="hello\n"))
        result = CliRunner().invoke(main, ["script", str(script)])
        assert result.exit_code == 0
        assert "hello\n" in result.output

    def test_stderr_routing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        _patch_daemon(monkeypatch, _success_response(stderr="warn\n"))
        result = CliRunner().invoke(main, ["script", str(script)])
        assert result.exit_code == 0
        assert "warn\n" in result.output

    def test_elapsed_footer(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        _patch_daemon(monkeypatch, _success_response(elapsed_ms=42))
        result = CliRunner().invoke(main, ["script", str(script)])
        assert result.exit_code == 0
        assert "# elapsed: 42 ms" in result.output

    def test_return_value_footer(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        _patch_daemon(monkeypatch, _success_response(return_value={"count": 3}))
        result = CliRunner().invoke(main, ["script", str(script)])
        assert result.exit_code == 0
        assert "# result:" in result.output

    def test_return_value_null_no_footer(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        _patch_daemon(monkeypatch, _success_response(return_value=None))
        result = CliRunner().invoke(main, ["script", str(script)])
        assert result.exit_code == 0
        assert "# result:" not in result.output


class TestScriptJsonOutput:
    def test_json_flag(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        resp = _success_response(stdout="hello\n", return_value=42)
        _patch_daemon(monkeypatch, resp)
        result = CliRunner().invoke(main, ["script", "--json", str(script)])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["stdout"] == "hello\n"
        assert data["return_value"] == 42


class TestScriptDaemonError:
    def test_daemon_error_exit_1(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        _patch_daemon(monkeypatch, {"error": {"code": -32002, "message": "no replay loaded"}})
        result = CliRunner().invoke(main, ["script", str(script)])
        assert result.exit_code == 1
        assert "no replay loaded" in result.output


class TestScriptArgParsing:
    def test_single_arg(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        captured: list[dict[str, Any]] = []

        import rdc.commands._helpers as helpers_mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)

        def _capture(_h: str, _p: int, payload: dict[str, Any]) -> dict[str, Any]:
            captured.append(payload)
            return _success_response()

        monkeypatch.setattr(helpers_mod, "send_request", _capture)
        CliRunner().invoke(main, ["script", "--arg", "KEY=VALUE", str(script)])
        assert captured[0]["params"]["args"] == {"KEY": "VALUE"}

    def test_multiple_args(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        captured: list[dict[str, Any]] = []

        import rdc.commands._helpers as helpers_mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)

        def _capture(_h: str, _p: int, payload: dict[str, Any]) -> dict[str, Any]:
            captured.append(payload)
            return _success_response()

        monkeypatch.setattr(helpers_mod, "send_request", _capture)
        CliRunner().invoke(main, ["script", "--arg", "A=1", "--arg", "B=2", str(script)])
        assert captured[0]["params"]["args"] == {"A": "1", "B": "2"}

    def test_arg_missing_equals(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        _patch_daemon(monkeypatch, _success_response())
        result = CliRunner().invoke(main, ["script", "--arg", "NOEQUALSSIGN", str(script)])
        assert result.exit_code == 2

    def test_no_args_default_empty(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        captured: list[dict[str, Any]] = []

        import rdc.commands._helpers as helpers_mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)

        def _capture(_h: str, _p: int, payload: dict[str, Any]) -> dict[str, Any]:
            captured.append(payload)
            return _success_response()

        monkeypatch.setattr(helpers_mod, "send_request", _capture)
        CliRunner().invoke(main, ["script", str(script)])
        assert captured[0]["params"]["args"] == {}

    def test_arg_value_with_equals(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        script = tmp_path / "s.py"
        script.write_text("x = 1", encoding="utf-8")
        captured: list[dict[str, Any]] = []

        import rdc.commands._helpers as helpers_mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)

        def _capture(_h: str, _p: int, payload: dict[str, Any]) -> dict[str, Any]:
            captured.append(payload)
            return _success_response()

        monkeypatch.setattr(helpers_mod, "send_request", _capture)
        CliRunner().invoke(main, ["script", "--arg", "K=A=B", str(script)])
        assert captured[0]["params"]["args"] == {"K": "A=B"}
