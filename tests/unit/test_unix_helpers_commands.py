"""Tests for rdc count and shader-map CLI commands."""

from __future__ import annotations

import json

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


# ── shader-map output options ──────────────────────────────────────

_SHADER_MAP_ROWS = {
    "rows": [
        {"eid": 10, "vs": 101, "hs": 0, "ds": 0, "gs": 0, "ps": 201, "cs": 0},
        {"eid": 20, "vs": 102, "hs": 0, "ds": 0, "gs": 0, "ps": 202, "cs": 0},
    ]
}


def test_shader_map_no_header_regression(monkeypatch) -> None:
    _patch_helpers(monkeypatch, _SHADER_MAP_ROWS)
    result = CliRunner().invoke(main, ["shader-map", "--no-header"])
    assert result.exit_code == 0
    assert "EID\tVS" not in result.output
    assert "101" in result.output


def test_shader_map_json(monkeypatch) -> None:
    _patch_helpers(monkeypatch, _SHADER_MAP_ROWS)
    result = CliRunner().invoke(main, ["shader-map", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["eid"] == 10


def test_shader_map_jsonl(monkeypatch) -> None:
    _patch_helpers(monkeypatch, _SHADER_MAP_ROWS)
    result = CliRunner().invoke(main, ["shader-map", "--jsonl"])
    assert result.exit_code == 0
    lines = [json.loads(ln) for ln in result.output.strip().splitlines()]
    assert len(lines) == 2
    assert lines[0]["eid"] == 10
    assert lines[0]["vs"] == 101
    assert lines[0]["ps"] == 201


def test_shader_map_quiet(monkeypatch) -> None:
    _patch_helpers(monkeypatch, _SHADER_MAP_ROWS)
    result = CliRunner().invoke(main, ["shader-map", "-q"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["10", "20"]


# ── count shaders ──────────────────────────────────────────────────


def test_count_shaders(monkeypatch) -> None:
    _patch_helpers(monkeypatch, {"value": 5})
    result = CliRunner().invoke(main, ["count", "shaders"])
    assert result.exit_code == 0
    assert "5" in result.output


def test_count_shaders_handler(monkeypatch) -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))
    import mock_renderdoc as rd

    from rdc.adapter import RenderDocAdapter
    from rdc.daemon_server import DaemonState, _handle_request

    ctrl = rd.MockReplayController()
    ctrl._actions = [
        rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall, _name="draw"),
    ]
    state = DaemonState(capture="test.rdc", current_eid=10, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 10
    state.rd = rd
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "count",
        "params": {"_token": "tok", "what": "shaders"},
    }
    resp, _ = _handle_request(req, state)
    assert "result" in resp
    assert isinstance(resp["result"]["value"], int)


def test_assert_count_shaders_pass(monkeypatch) -> None:
    import rdc.commands.assert_ci as mod

    def fake(method, params=None):
        return {"value": 3}

    monkeypatch.setattr(mod, "_assert_call", fake)
    result = CliRunner().invoke(main, ["assert-count", "shaders", "--expect", "3"])
    assert result.exit_code == 0


def test_assert_count_shaders_fail(monkeypatch) -> None:
    import rdc.commands.assert_ci as mod

    def fake(method, params=None):
        return {"value": 3}

    monkeypatch.setattr(mod, "_assert_call", fake)
    result = CliRunner().invoke(main, ["assert-count", "shaders", "--expect", "5"])
    assert result.exit_code == 1


def test_count_invalid_target() -> None:
    result = CliRunner().invoke(main, ["count", "invalid_target"])
    assert result.exit_code == 2
