"""Tests for rdc count and shader-map CLI commands."""

from __future__ import annotations

from click.testing import CliRunner

from rdc.cli import main


def _patch_helpers(monkeypatch, response):
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})


def test_count_draws(monkeypatch) -> None:
    _patch_helpers(monkeypatch, {"value": 42})
    result = CliRunner().invoke(main, ["count", "draws"])
    assert result.exit_code == 0
    assert "42" in result.output


def test_count_events(monkeypatch) -> None:
    _patch_helpers(monkeypatch, {"value": 1000})
    result = CliRunner().invoke(main, ["count", "events"])
    assert result.exit_code == 0
    assert "1000" in result.output


def test_count_triangles(monkeypatch) -> None:
    _patch_helpers(monkeypatch, {"value": 50000})
    result = CliRunner().invoke(main, ["count", "triangles"])
    assert result.exit_code == 0
    assert "50000" in result.output


def test_count_with_pass(monkeypatch) -> None:
    _patch_helpers(monkeypatch, {"value": 10})
    result = CliRunner().invoke(main, ["count", "draws", "--pass", "GBuffer"])
    assert result.exit_code == 0
    assert "10" in result.output


def test_count_no_session(monkeypatch) -> None:
    import rdc.commands._helpers as mod

    monkeypatch.setattr(mod, "load_session", lambda: None)
    result = CliRunner().invoke(main, ["count", "draws"])
    assert result.exit_code == 1


def test_count_error_response(monkeypatch) -> None:
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod, "send_request", lambda _h, _p, _payload: {"error": {"message": "no replay"}}
    )
    result = CliRunner().invoke(main, ["count", "draws"])
    assert result.exit_code == 1


def test_shader_map_tsv(monkeypatch) -> None:
    _patch_helpers(
        monkeypatch,
        {
            "rows": [
                {"eid": 10, "vs": 101, "hs": 0, "ds": 0, "gs": 0, "ps": 201, "cs": 0},
            ]
        },
    )
    result = CliRunner().invoke(main, ["shader-map"])
    assert result.exit_code == 0
    assert "EID" in result.output
    assert "101" in result.output


def test_shader_map_no_header(monkeypatch) -> None:
    _patch_helpers(
        monkeypatch,
        {"rows": [{"eid": 10, "vs": 101, "hs": 0, "ds": 0, "gs": 0, "ps": 201, "cs": 0}]},
    )
    result = CliRunner().invoke(main, ["shader-map", "--no-header"])
    assert result.exit_code == 0
    assert "EID" not in result.output
