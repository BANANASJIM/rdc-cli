"""Tests for rdc usage CLI command."""

from __future__ import annotations

import json

from click.testing import CliRunner

from rdc.cli import main


def _patch_usage(monkeypatch, response):
    import rdc.commands.info as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})


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


def test_usage_single_tsv(monkeypatch) -> None:
    _patch_usage(monkeypatch, _SINGLE_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "97"])
    assert result.exit_code == 0
    assert "EID\tUSAGE" in result.output
    assert "6\tClear" in result.output
    assert "11\tColorTarget" in result.output
    assert "12\tCopySrc" in result.output


def test_usage_single_json(monkeypatch) -> None:
    _patch_usage(monkeypatch, _SINGLE_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "97", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == 97
    assert len(data["entries"]) == 3


def test_usage_all_tsv(monkeypatch) -> None:
    _patch_usage(monkeypatch, _ALL_RESPONSE)
    result = CliRunner().invoke(main, ["usage", "--all"])
    assert result.exit_code == 0
    assert "ID\tNAME\tEID\tUSAGE" in result.output
    assert "97\t2D Image 97\t6\tClear" in result.output
    assert "105\tBuffer 105\t11\tVS_Constants" in result.output


def test_usage_all_type_filter(monkeypatch) -> None:
    filtered = {
        "rows": [
            {"id": 97, "name": "2D Image 97", "eid": 6, "usage": "Clear"},
        ],
        "total": 1,
    }
    captured: dict = {}

    import rdc.commands.info as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def _capture_req(_h, _p, payload):
        captured.update(payload.get("params", {}))
        return {"result": filtered}

    monkeypatch.setattr(mod, "send_request", _capture_req)
    result = CliRunner().invoke(main, ["usage", "--all", "--type", "Texture"])
    assert result.exit_code == 0
    assert captured.get("type") == "Texture"
    assert "97" in result.output


def test_usage_all_usage_filter(monkeypatch) -> None:
    filtered = {
        "rows": [
            {"id": 97, "name": "2D Image 97", "eid": 11, "usage": "ColorTarget"},
        ],
        "total": 1,
    }
    captured: dict = {}

    import rdc.commands.info as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def _capture_req(_h, _p, payload):
        captured.update(payload.get("params", {}))
        return {"result": filtered}

    monkeypatch.setattr(mod, "send_request", _capture_req)
    result = CliRunner().invoke(main, ["usage", "--all", "--usage", "ColorTarget"])
    assert result.exit_code == 0
    assert captured.get("usage") == "ColorTarget"


def test_usage_no_args_exits_1(monkeypatch) -> None:
    _patch_usage(monkeypatch, {})
    result = CliRunner().invoke(main, ["usage"])
    assert result.exit_code == 1
    assert "error" in result.output


def test_usage_daemon_error_exits_1(monkeypatch) -> None:
    import rdc.commands.info as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod,
        "send_request",
        lambda _h, _p, _payload: {"error": {"code": -32001, "message": "resource 999 not found"}},
    )
    result = CliRunner().invoke(main, ["usage", "999"])
    assert result.exit_code == 1
    assert "not found" in result.output
