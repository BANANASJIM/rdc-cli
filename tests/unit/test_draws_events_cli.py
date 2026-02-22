"""CLI integration tests for info, stats, events, draws, event, draw commands."""

from __future__ import annotations

from click.testing import CliRunner

from rdc.cli import main


class TestCliRegistration:
    def test_help_shows_info(self):
        assert "info" in CliRunner().invoke(main, ["--help"]).output

    def test_help_shows_stats(self):
        assert "stats" in CliRunner().invoke(main, ["--help"]).output

    def test_help_shows_events(self):
        assert "events" in CliRunner().invoke(main, ["--help"]).output

    def test_help_shows_draws(self):
        assert "draws" in CliRunner().invoke(main, ["--help"]).output

    def test_help_shows_event(self):
        assert "event" in CliRunner().invoke(main, ["--help"]).output

    def test_help_shows_draw(self):
        assert "draw" in CliRunner().invoke(main, ["--help"]).output


class TestNoSession:
    def test_info(self, monkeypatch):
        monkeypatch.setattr("rdc.commands._helpers.load_session", lambda: None)
        assert CliRunner().invoke(main, ["info"]).exit_code == 1

    def test_events(self, monkeypatch):
        monkeypatch.setattr("rdc.commands._helpers.load_session", lambda: None)
        assert CliRunner().invoke(main, ["events"]).exit_code == 1

    def test_draws(self, monkeypatch):
        monkeypatch.setattr("rdc.commands._helpers.load_session", lambda: None)
        assert CliRunner().invoke(main, ["draws"]).exit_code == 1

    def test_event(self, monkeypatch):
        monkeypatch.setattr("rdc.commands._helpers.load_session", lambda: None)
        assert CliRunner().invoke(main, ["event", "42"]).exit_code == 1

    def test_draw(self, monkeypatch):
        monkeypatch.setattr("rdc.commands._helpers.load_session", lambda: None)
        assert CliRunner().invoke(main, ["draw", "42"]).exit_code == 1

    def test_stats(self, monkeypatch):
        monkeypatch.setattr("rdc.commands._helpers.load_session", lambda: None)
        assert CliRunner().invoke(main, ["stats"]).exit_code == 1
