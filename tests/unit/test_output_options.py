"""Tests for the @list_output_options decorator."""

from __future__ import annotations

import click
from click.testing import CliRunner

from rdc.formatters.options import list_output_options


def test_decorator_adds_no_header() -> None:
    @click.command("test-cmd")
    @list_output_options
    def cmd(no_header: bool, use_jsonl: bool, quiet: bool) -> None:
        click.echo(f"no_header={no_header}")

    result = CliRunner().invoke(cmd, ["--no-header"])
    assert result.exit_code == 0
    assert "no_header=True" in result.output


def test_decorator_adds_jsonl() -> None:
    @click.command("test-cmd")
    @list_output_options
    def cmd(no_header: bool, use_jsonl: bool, quiet: bool) -> None:
        click.echo(f"use_jsonl={use_jsonl}")

    result = CliRunner().invoke(cmd, ["--jsonl"])
    assert result.exit_code == 0
    assert "use_jsonl=True" in result.output


def test_decorator_adds_quiet() -> None:
    @click.command("test-cmd")
    @list_output_options
    def cmd(no_header: bool, use_jsonl: bool, quiet: bool) -> None:
        click.echo(f"quiet={quiet}")

    result = CliRunner().invoke(cmd, ["-q"])
    assert result.exit_code == 0
    assert "quiet=True" in result.output


def test_decorator_defaults_false() -> None:
    @click.command("test-cmd")
    @list_output_options
    def cmd(no_header: bool, use_jsonl: bool, quiet: bool) -> None:
        click.echo(f"{no_header},{use_jsonl},{quiet}")

    result = CliRunner().invoke(cmd, [])
    assert result.exit_code == 0
    assert "False,False,False" in result.output


def test_decorator_preserves_other_options() -> None:
    @click.command("test-cmd")
    @click.option("--json", "use_json", is_flag=True)
    @list_output_options
    def cmd(use_json: bool, no_header: bool, use_jsonl: bool, quiet: bool) -> None:
        click.echo(f"json={use_json},quiet={quiet}")

    result = CliRunner().invoke(cmd, ["--json", "-q"])
    assert result.exit_code == 0
    assert "json=True,quiet=True" in result.output
