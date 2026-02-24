"""Tests for rdc info/stats/log CLI commands."""

from __future__ import annotations

import json

from click.testing import CliRunner

from rdc.cli import main


def _patch_info(monkeypatch, response):
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})


def test_info_tsv(monkeypatch) -> None:
    _patch_info(
        monkeypatch,
        {
            "capture": "test.rdc",
            "api": "Vulkan",
            "event_count": 1000,
            "driver": "NVIDIA 535.183",
        },
    )
    result = CliRunner().invoke(main, ["info"])
    assert result.exit_code == 0
    assert "Vulkan" in result.output
    assert "1000" in result.output


def test_info_json(monkeypatch) -> None:
    _patch_info(monkeypatch, {"capture": "test.rdc", "api": "Vulkan", "event_count": 1000})
    result = CliRunner().invoke(main, ["info", "--json"])
    assert result.exit_code == 0
    assert '"capture": "test.rdc"' in result.output


def test_info_empty_values(monkeypatch) -> None:
    _patch_info(monkeypatch, {"capture": "test.rdc", "api": "", "driver": None})
    result = CliRunner().invoke(main, ["info"])
    assert result.exit_code == 0
    assert "-" in result.output


def test_stats_json(monkeypatch) -> None:
    _patch_info(
        monkeypatch,
        {
            "per_pass": [{"name": "Main", "draws": 10, "dispatches": 0, "triangles": 5000}],
            "top_draws": [{"eid": 42, "marker": "Geo", "triangles": 3000}],
        },
    )
    result = CliRunner().invoke(main, ["stats", "--json"])
    assert result.exit_code == 0
    assert "per_pass" in result.output


def test_stats_tsv(monkeypatch) -> None:
    _patch_info(
        monkeypatch,
        {
            "per_pass": [
                {
                    "name": "Main",
                    "draws": 10,
                    "dispatches": 0,
                    "triangles": 5000,
                    "rt_w": 1920,
                    "rt_h": 1080,
                    "attachments": 3,
                },
            ],
            "top_draws": [{"eid": 42, "marker": "Geo", "triangles": 3000}],
        },
    )
    result = CliRunner().invoke(main, ["stats"])
    assert result.exit_code == 0
    assert "5000" in result.output
    assert "3000" in result.output


def test_stats_no_header(monkeypatch) -> None:
    _patch_info(
        monkeypatch,
        {
            "per_pass": [
                {"name": "Main", "draws": 10, "dispatches": 0, "triangles": 5000},
            ],
            "top_draws": [],
        },
    )
    result = CliRunner().invoke(main, ["stats", "--no-header"])
    assert result.exit_code == 0
    assert "PASS" not in result.output


def test_stats_empty(monkeypatch) -> None:
    _patch_info(monkeypatch, {"per_pass": [], "top_draws": []})
    result = CliRunner().invoke(main, ["stats"])
    assert result.exit_code == 0


def test_daemon_call_no_session(monkeypatch) -> None:
    import rdc.commands._helpers as mod

    monkeypatch.setattr(mod, "load_session", lambda: None)
    result = CliRunner().invoke(main, ["info"])
    assert result.exit_code == 1
    assert "no active session" in result.output


def test_daemon_call_error_response(monkeypatch) -> None:
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod, "send_request", lambda _h, _p, _payload: {"error": {"message": "no replay loaded"}}
    )
    result = CliRunner().invoke(main, ["info"])
    assert result.exit_code == 1
    assert "no replay loaded" in result.output


def test_daemon_call_connection_error(monkeypatch) -> None:
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def raise_error(*args):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(mod, "send_request", raise_error)
    result = CliRunner().invoke(main, ["info"])
    assert result.exit_code == 1
    assert "daemon unreachable" in result.output


def test_log_tsv(monkeypatch) -> None:
    _patch_info(
        monkeypatch,
        {
            "messages": [
                {"level": "HIGH", "eid": 0, "message": "validation error"},
                {"level": "INFO", "eid": 42, "message": "info msg"},
            ]
        },
    )
    result = CliRunner().invoke(main, ["log"])
    assert result.exit_code == 0
    assert "LEVEL" in result.output
    assert "HIGH" in result.output
    assert "validation error" in result.output


def test_log_json(monkeypatch) -> None:
    _patch_info(
        monkeypatch,
        {"messages": [{"level": "HIGH", "eid": 0, "message": "error"}]},
    )
    result = CliRunner().invoke(main, ["log", "--json"])
    assert result.exit_code == 0
    assert '"level": "HIGH"' in result.output


def test_log_with_level_filter(monkeypatch) -> None:
    _patch_info(monkeypatch, {"messages": []})
    result = CliRunner().invoke(main, ["log", "--level", "HIGH"])
    assert result.exit_code == 0


def test_log_with_eid_filter(monkeypatch) -> None:
    _patch_info(monkeypatch, {"messages": []})
    result = CliRunner().invoke(main, ["log", "--eid", "42"])
    assert result.exit_code == 0


def test_log_empty(monkeypatch) -> None:
    _patch_info(monkeypatch, {"messages": []})
    result = CliRunner().invoke(main, ["log"])
    assert result.exit_code == 0
    assert "LEVEL" in result.output


def test_log_no_session(monkeypatch) -> None:
    import rdc.commands._helpers as mod

    monkeypatch.setattr(mod, "load_session", lambda: None)
    result = CliRunner().invoke(main, ["log"])
    assert result.exit_code == 1
    assert "no active session" in result.output


# ── log output options ─────────────────────────────────────────────

_LOG_MESSAGES = {
    "messages": [
        {"level": "HIGH", "eid": 0, "message": "validation error"},
        {"level": "INFO", "eid": 42, "message": "info msg"},
    ]
}


def test_log_default_has_header(monkeypatch) -> None:
    _patch_info(monkeypatch, _LOG_MESSAGES)
    result = CliRunner().invoke(main, ["log"])
    assert result.exit_code == 0
    assert "LEVEL\tEID\tMESSAGE" in result.output


def test_log_no_header_regression(monkeypatch) -> None:
    _patch_info(monkeypatch, _LOG_MESSAGES)
    result = CliRunner().invoke(main, ["log", "--no-header"])
    assert result.exit_code == 0
    assert "LEVEL\tEID\tMESSAGE" not in result.output
    assert "validation error" in result.output


def test_log_jsonl(monkeypatch) -> None:
    _patch_info(monkeypatch, _LOG_MESSAGES)
    result = CliRunner().invoke(main, ["log", "--jsonl"])
    assert result.exit_code == 0
    lines = [json.loads(ln) for ln in result.output.strip().splitlines()]
    assert len(lines) == 2
    assert lines[0]["level"] == "HIGH"
    assert lines[0]["eid"] == 0
    assert lines[0]["message"] == "validation error"


def test_log_quiet(monkeypatch) -> None:
    _patch_info(monkeypatch, _LOG_MESSAGES)
    result = CliRunner().invoke(main, ["log", "-q"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["0", "42"]


# ── B6: log handler caches messages ──────────────────────────────────


def test_log_handler_caches_messages(monkeypatch) -> None:
    """Second _handle_log call returns same data without re-calling GetDebugMessages."""
    import mock_renderdoc as rd

    from rdc.adapter import RenderDocAdapter
    from rdc.daemon_server import DaemonState, _handle_request

    ctrl = rd.MockReplayController()
    msg = rd.DebugMessage(eventId=10, severity=rd.MessageSeverity.High, description="test msg")
    ctrl._debug_messages = [msg]

    ctrl._actions = [
        rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall, _name="draw"),
    ]
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 10
    state.rd = rd

    req = {"jsonrpc": "2.0", "id": 1, "method": "log", "params": {"_token": "tok"}}

    resp1, _ = _handle_request(req, state)
    assert len(resp1["result"]["messages"]) == 1

    # Clear the controller's messages to simulate consume-once
    ctrl._debug_messages = []

    resp2, _ = _handle_request(req, state)
    # Should still return messages from cache
    assert len(resp2["result"]["messages"]) == 1
    assert resp2["result"]["messages"][0]["message"] == "test msg"


# ── B8: stats --no-header hides section titles ───────────────────────


def test_stats_no_header_hides_section_titles(monkeypatch) -> None:
    """--no-header suppresses section title lines from stderr."""
    _patch_info(
        monkeypatch,
        {
            "per_pass": [{"name": "Main", "draws": 10, "dispatches": 0, "triangles": 5000}],
            "top_draws": [{"eid": 42, "marker": "Geo", "triangles": 3000}],
        },
    )
    result = CliRunner().invoke(main, ["stats", "--no-header"])
    assert result.exit_code == 0
    assert "Per-Pass Breakdown:" not in result.output
    assert "Top Draws by Triangle Count:" not in result.output


def test_stats_default_shows_section_titles(monkeypatch) -> None:
    """Default mode shows section title lines in stderr."""
    _patch_info(
        monkeypatch,
        {
            "per_pass": [{"name": "Main", "draws": 10, "dispatches": 0, "triangles": 5000}],
            "top_draws": [{"eid": 42, "marker": "Geo", "triangles": 3000}],
        },
    )
    result = CliRunner().invoke(main, ["stats"])
    assert result.exit_code == 0
    assert "Per-Pass Breakdown:" in result.output


# ── B9: stats --jsonl and -q ─────────────────────────────────────────


def test_stats_jsonl(monkeypatch) -> None:
    """--jsonl outputs each per-pass item as separate JSON line."""
    _patch_info(
        monkeypatch,
        {
            "per_pass": [
                {
                    "name": "Main",
                    "draws": 10,
                    "dispatches": 0,
                    "triangles": 5000,
                    "rt_w": 1920,
                    "rt_h": 1080,
                    "attachments": 3,
                },
            ],
            "top_draws": [{"eid": 42, "marker": "Geo", "triangles": 3000}],
        },
    )
    result = CliRunner().invoke(main, ["stats", "--jsonl"])
    assert result.exit_code == 0
    lines = [json.loads(ln) for ln in result.output.strip().splitlines()]
    assert len(lines) >= 1
    assert lines[0]["name"] == "Main"


def test_stats_quiet(monkeypatch) -> None:
    """-q outputs pass names only."""
    _patch_info(
        monkeypatch,
        {
            "per_pass": [
                {"name": "Main", "draws": 10, "dispatches": 0, "triangles": 5000},
                {"name": "Shadow", "draws": 5, "dispatches": 0, "triangles": 2000},
            ],
            "top_draws": [],
        },
    )
    result = CliRunner().invoke(main, ["stats", "-q"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["Main", "Shadow"]


# ── B7: stats handler returns RT dimensions ──────────────────────────


def test_stats_tsv_shows_rt_dimensions(monkeypatch) -> None:
    """Stats TSV output includes RT_W and RT_H columns with actual values."""
    _patch_info(
        monkeypatch,
        {
            "per_pass": [
                {
                    "name": "Main",
                    "draws": 10,
                    "dispatches": 0,
                    "triangles": 5000,
                    "rt_w": 1920,
                    "rt_h": 1080,
                    "attachments": 3,
                },
            ],
            "top_draws": [],
        },
    )
    result = CliRunner().invoke(main, ["stats"])
    assert result.exit_code == 0
    assert "1920" in result.output
    assert "1080" in result.output


def test_stats_json_includes_rt_dimensions(monkeypatch) -> None:
    """Stats JSON output includes rt_w and rt_h fields."""
    _patch_info(
        monkeypatch,
        {
            "per_pass": [
                {
                    "name": "Main",
                    "draws": 10,
                    "dispatches": 0,
                    "triangles": 5000,
                    "rt_w": 1920,
                    "rt_h": 1080,
                    "attachments": 3,
                },
            ],
            "top_draws": [],
        },
    )
    result = CliRunner().invoke(main, ["stats", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["per_pass"][0]["rt_w"] == 1920
    assert data["per_pass"][0]["rt_h"] == 1080
    assert data["per_pass"][0]["attachments"] == 3
