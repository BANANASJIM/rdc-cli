"""Tests for rdc info/stats/log CLI commands."""

from __future__ import annotations

from click.testing import CliRunner

from rdc.cli import main


def _patch_info(monkeypatch, response):
    import rdc.commands.info as mod

    monkeypatch.setattr(mod, "_daemon_call", lambda m, p=None: response)


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
    import rdc.commands.info as mod

    monkeypatch.setattr(mod, "load_session", lambda: None)
    result = CliRunner().invoke(main, ["info"])
    assert result.exit_code == 1
    assert "no active session" in result.output


def test_daemon_call_error_response(monkeypatch) -> None:
    import rdc.commands.info as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod, "send_request", lambda _h, _p, _payload: {"error": {"message": "no replay loaded"}}
    )
    result = CliRunner().invoke(main, ["info"])
    assert result.exit_code == 1
    assert "no replay loaded" in result.output


def test_daemon_call_connection_error(monkeypatch) -> None:
    import rdc.commands.info as mod

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
    import rdc.commands.info as mod

    monkeypatch.setattr(mod, "load_session", lambda: None)
    result = CliRunner().invoke(main, ["log"])
    assert result.exit_code == 1
    assert "no active session" in result.output
