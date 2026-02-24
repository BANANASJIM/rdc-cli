"""Tests for rdc usage CLI command."""

from __future__ import annotations

from typing import Any

from click.testing import CliRunner
from conftest import assert_json_output, assert_jsonl_output

from rdc.cli import main
from rdc.commands import usage as usage_mod


def _patch(monkeypatch: Any, response: dict) -> None:
    monkeypatch.setattr(usage_mod, "_daemon_call", lambda method, params=None: response)


_SINGLE_RESPONSE = {
    "id": 97,
    "name": "2D Image 97",
    "entries": [
        {"eid": 6, "usage": "Clear"},
        {"eid": 11, "usage": "ColorTarget"},
        {"eid": 12, "usage": "CopySrc"},
    ],
}

_ALL_RESPONSE = {
    "rows": [
        {"id": 97, "name": "2D Image 97", "eid": 6, "usage": "Clear"},
        {"id": 97, "name": "2D Image 97", "eid": 11, "usage": "ColorTarget"},
        {"id": 97, "name": "2D Image 97", "eid": 12, "usage": "CopySrc"},
        {"id": 105, "name": "Buffer 105", "eid": 11, "usage": "VS_Constants"},
    ],
    "total": 4,
}


def test_usage_single_tsv(monkeypatch: Any) -> None:
    _patch(monkeypatch, _SINGLE_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "97"])
    assert result.exit_code == 0
    assert "EID\tUSAGE" in result.output
    assert "6\tClear" in result.output
    assert "11\tColorTarget" in result.output
    assert "12\tCopySrc" in result.output


def test_usage_single_json(monkeypatch: Any) -> None:
    _patch(monkeypatch, _SINGLE_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "97", "--json"])
    data = assert_json_output(result)
    assert data["id"] == 97
    assert len(data["entries"]) == 3


def test_usage_all_tsv(monkeypatch: Any) -> None:
    _patch(monkeypatch, _ALL_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "--all"])
    assert result.exit_code == 0
    assert "ID\tNAME\tEID\tUSAGE" in result.output
    assert "97\t2D Image 97\t6\tClear" in result.output
    assert "105\tBuffer 105\t11\tVS_Constants" in result.output


def test_usage_all_type_filter(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def _capture(method: str, params: dict | None = None) -> dict:
        captured["method"] = method
        captured["params"] = params or {}
        return {"rows": [{"id": 97, "name": "2D Image 97", "eid": 6, "usage": "Clear"}], "total": 1}

    monkeypatch.setattr(usage_mod, "_daemon_call", _capture)
    result = CliRunner().invoke(main, ["usage", "--all", "--type", "Texture"])
    assert result.exit_code == 0
    assert captured["params"].get("type") == "Texture"


def test_usage_all_usage_filter(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def _capture(method: str, params: dict | None = None) -> dict:
        captured["method"] = method
        captured["params"] = params or {}
        row = {"id": 97, "name": "2D Image 97", "eid": 11, "usage": "ColorTarget"}
        return {"rows": [row], "total": 1}

    monkeypatch.setattr(usage_mod, "_daemon_call", _capture)
    result = CliRunner().invoke(main, ["usage", "--all", "--usage", "ColorTarget"])
    assert result.exit_code == 0
    assert captured["params"].get("usage") == "ColorTarget"


def test_usage_no_args_exits_1(monkeypatch: Any) -> None:
    _patch(monkeypatch, {})
    result = CliRunner().invoke(main, ["usage"])
    assert result.exit_code == 1
    assert "error" in result.output


def test_usage_daemon_error_exits_1(monkeypatch: Any) -> None:
    from rdc.commands.info import _daemon_call as _orig  # noqa: F401

    def _raise_error(method: str, params: dict | None = None) -> dict:
        import click

        click.echo("error: resource 999 not found", err=True)
        raise SystemExit(1)

    monkeypatch.setattr(usage_mod, "_daemon_call", _raise_error)
    result = CliRunner().invoke(main, ["usage", "999"])
    assert result.exit_code == 1


# ── usage single-resource output options ───────────────────────────


def test_usage_single_default_has_header(monkeypatch: Any) -> None:
    _patch(monkeypatch, _SINGLE_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "97"])
    assert result.exit_code == 0
    assert "EID\tUSAGE" in result.output


def test_usage_single_no_header(monkeypatch: Any) -> None:
    _patch(monkeypatch, _SINGLE_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "97", "--no-header"])
    assert result.exit_code == 0
    assert "EID\tUSAGE" not in result.output
    assert "Clear" in result.output


def test_usage_single_jsonl(monkeypatch: Any) -> None:
    _patch(monkeypatch, _SINGLE_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "97", "--jsonl"])
    lines = assert_jsonl_output(result, 3)
    assert lines[0]["eid"] == 6
    assert lines[0]["usage"] == "Clear"


def test_usage_single_quiet(monkeypatch: Any) -> None:
    _patch(monkeypatch, _SINGLE_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "97", "-q"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["6", "11", "12"]


# ── usage --all output options ─────────────────────────────────────


def test_usage_all_default_has_header(monkeypatch: Any) -> None:
    _patch(monkeypatch, _ALL_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "--all"])
    assert result.exit_code == 0
    assert "ID\tNAME\tEID\tUSAGE" in result.output


def test_usage_all_no_header(monkeypatch: Any) -> None:
    _patch(monkeypatch, _ALL_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "--all", "--no-header"])
    assert result.exit_code == 0
    assert "ID\tNAME\tEID\tUSAGE" not in result.output
    assert "2D Image 97" in result.output


def test_usage_all_jsonl(monkeypatch: Any) -> None:
    _patch(monkeypatch, _ALL_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "--all", "--jsonl"])
    lines = assert_jsonl_output(result, 4)
    assert lines[0]["id"] == 97
    assert lines[0]["name"] == "2D Image 97"
    assert lines[0]["eid"] == 6
    assert lines[0]["usage"] == "Clear"


def test_usage_all_quiet(monkeypatch: Any) -> None:
    _patch(monkeypatch, _ALL_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "--all", "-q"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["97", "97", "97", "105"]
