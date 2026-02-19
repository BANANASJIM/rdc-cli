"""Tests for rdc events/draws/event/draw CLI commands."""

from __future__ import annotations

from click.testing import CliRunner

from rdc.cli import main


def _mock_session():
    return type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()


def _patch_events(monkeypatch, response):
    import rdc.commands.events as mod

    monkeypatch.setattr(mod, "_daemon_call", lambda m, p=None: response)


def test_events_tsv(monkeypatch) -> None:
    _patch_events(
        monkeypatch,
        {
            "events": [
                {"eid": 1, "type": "Draw", "name": "vkCmdDraw"},
                {"eid": 2, "type": "Dispatch", "name": "vkCmdDispatch"},
            ]
        },
    )
    result = CliRunner().invoke(main, ["events"])
    assert result.exit_code == 0
    assert "vkCmdDraw" in result.output


def test_events_json(monkeypatch) -> None:
    _patch_events(monkeypatch, {"events": [{"eid": 1, "type": "Draw", "name": "vkCmdDraw"}]})
    result = CliRunner().invoke(main, ["events", "--json"])
    assert result.exit_code == 0
    assert '"eid": 1' in result.output


def test_events_jsonl(monkeypatch) -> None:
    _patch_events(monkeypatch, {"events": [{"eid": 1, "type": "Draw", "name": "vkCmdDraw"}]})
    result = CliRunner().invoke(main, ["events", "--jsonl"])
    assert result.exit_code == 0
    assert "eid" in result.output


def test_events_quiet(monkeypatch) -> None:
    _patch_events(monkeypatch, {"events": [{"eid": 1, "type": "Draw", "name": "x"}]})
    result = CliRunner().invoke(main, ["events", "-q"])
    assert result.exit_code == 0
    assert result.output.strip() == "1"


def test_events_with_filters(monkeypatch) -> None:
    calls: list[dict] = []
    import rdc.commands.events as mod

    def capture_call(m, p=None):
        calls.append(p)
        return {"events": []}

    monkeypatch.setattr(mod, "_daemon_call", capture_call)
    CliRunner().invoke(
        main, ["events", "--type", "Draw", "--filter", "vk*", "--limit", "10", "--range", "0:100"]
    )
    assert calls[0]["type"] == "Draw"
    assert calls[0]["filter"] == "vk*"
    assert calls[0]["limit"] == 10
    assert calls[0]["range"] == "0:100"


def test_events_no_header(monkeypatch) -> None:
    _patch_events(monkeypatch, {"events": [{"eid": 1, "type": "Draw", "name": "x"}]})
    result = CliRunner().invoke(main, ["events", "--no-header"])
    assert result.exit_code == 0
    assert "EID" not in result.output


def test_draws_tsv(monkeypatch) -> None:
    _patch_events(
        monkeypatch,
        {
            "draws": [
                {
                    "eid": 10,
                    "type": "Indexed",
                    "triangles": 500,
                    "instances": 1,
                    "pass": "Main",
                    "marker": "Geo",
                },
            ],
            "summary": "1 draw, 500 triangles",
        },
    )
    result = CliRunner().invoke(main, ["draws"])
    assert result.exit_code == 0
    assert "500" in result.output


def test_draws_json(monkeypatch) -> None:
    _patch_events(
        monkeypatch,
        {
            "draws": [{"eid": 10, "type": "Indexed", "triangles": 500, "instances": 1}],
            "summary": "",
        },
    )
    result = CliRunner().invoke(main, ["draws", "--json"])
    assert result.exit_code == 0
    assert '"eid": 10' in result.output


def test_draws_jsonl(monkeypatch) -> None:
    _patch_events(
        monkeypatch,
        {
            "draws": [{"eid": 10, "type": "Indexed", "triangles": 500, "instances": 1}],
            "summary": "",
        },
    )
    result = CliRunner().invoke(main, ["draws", "--jsonl"])
    assert result.exit_code == 0


def test_draws_quiet(monkeypatch) -> None:
    _patch_events(
        monkeypatch,
        {
            "draws": [{"eid": 10, "type": "Indexed", "triangles": 500, "instances": 1}],
            "summary": "",
        },
    )
    result = CliRunner().invoke(main, ["draws", "-q"])
    assert result.exit_code == 0
    assert result.output.strip() == "10"


def test_draws_with_options(monkeypatch) -> None:
    calls: list[dict] = []
    import rdc.commands.events as mod

    def capture_call(m, p=None):
        calls.append(p)
        return {"draws": [], "summary": ""}

    monkeypatch.setattr(mod, "_daemon_call", capture_call)
    CliRunner().invoke(main, ["draws", "--pass", "GBuffer", "--sort", "triangles", "--limit", "5"])
    assert calls[0]["pass"] == "GBuffer"
    assert calls[0]["sort"] == "triangles"
    assert calls[0]["limit"] == 5


def test_event_detail(monkeypatch) -> None:
    _patch_events(monkeypatch, {"eid": 10, "api_call": "vkCmdDraw", "params": "count=100"})
    result = CliRunner().invoke(main, ["event", "10"])
    assert result.exit_code == 0
    assert "vkCmdDraw" in result.output


def test_event_json(monkeypatch) -> None:
    _patch_events(monkeypatch, {"eid": 10, "api_call": "vkCmdDraw"})
    result = CliRunner().invoke(main, ["event", "10", "--json"])
    assert result.exit_code == 0
    assert '"eid": 10' in result.output


def test_draw_detail(monkeypatch) -> None:
    _patch_events(monkeypatch, {"eid": 10, "type": "Indexed", "triangles": 500})
    result = CliRunner().invoke(main, ["draw", "10"])
    assert result.exit_code == 0
    assert "500" in result.output


def test_draw_json(monkeypatch) -> None:
    _patch_events(monkeypatch, {"eid": 10, "type": "Indexed", "triangles": 500})
    result = CliRunner().invoke(main, ["draw", "10", "--json"])
    assert result.exit_code == 0
    assert '"eid": 10' in result.output


def test_draw_no_eid(monkeypatch) -> None:
    _patch_events(monkeypatch, {"eid": 0, "type": "Indexed", "triangles": 100})
    result = CliRunner().invoke(main, ["draw"])
    assert result.exit_code == 0
