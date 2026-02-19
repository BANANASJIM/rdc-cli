from __future__ import annotations

from click.testing import CliRunner

from rdc.cli import main


def test_version_flag_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "rdc" in result.output.lower()


def test_help_shows_core_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.output
    assert "capture" in result.output
    assert "pipeline" in result.output
    assert "shader" in result.output
