"""Tests for the @list_output_options decorator."""

from __future__ import annotations

import click
from click.testing import CliRunner

from rdc.formatters.options import list_output_options


def test_decorator_adds_no_header() -> None:
    @click.command("test-cmd")
    @list_output_options
    def cmd(no_header: bool, use_json: bool, use_jsonl: bool, quiet: bool) -> None:
        click.echo(f"no_header={no_header}")

    result = CliRunner().invoke(cmd, ["--no-header"])
    assert result.exit_code == 0
    assert "no_header=True" in result.output


def test_decorator_adds_json() -> None:
    @click.command("test-cmd")
    @list_output_options
    def cmd(no_header: bool, use_json: bool, use_jsonl: bool, quiet: bool) -> None:
        click.echo(f"use_json={use_json}")

    result = CliRunner().invoke(cmd, ["--json"])
    assert result.exit_code == 0
    assert "use_json=True" in result.output


def test_decorator_adds_jsonl() -> None:
    @click.command("test-cmd")
    @list_output_options
    def cmd(no_header: bool, use_json: bool, use_jsonl: bool, quiet: bool) -> None:
        click.echo(f"use_jsonl={use_jsonl}")

    result = CliRunner().invoke(cmd, ["--jsonl"])
    assert result.exit_code == 0
    assert "use_jsonl=True" in result.output


def test_decorator_adds_quiet() -> None:
    @click.command("test-cmd")
    @list_output_options
    def cmd(no_header: bool, use_json: bool, use_jsonl: bool, quiet: bool) -> None:
        click.echo(f"quiet={quiet}")

    result = CliRunner().invoke(cmd, ["-q"])
    assert result.exit_code == 0
    assert "quiet=True" in result.output


def test_decorator_defaults_false() -> None:
    @click.command("test-cmd")
    @list_output_options
    def cmd(no_header: bool, use_json: bool, use_jsonl: bool, quiet: bool) -> None:
        click.echo(f"{no_header},{use_json},{use_jsonl},{quiet}")

    result = CliRunner().invoke(cmd, [])
    assert result.exit_code == 0
    assert "False,False,False,False" in result.output


def test_decorator_preserves_other_options() -> None:
    @click.command("test-cmd")
    @click.option("--type", "type_filter", default=None)
    @list_output_options
    def cmd(
        type_filter: str | None,
        no_header: bool,
        use_json: bool,
        use_jsonl: bool,
        quiet: bool,
    ) -> None:
        click.echo(f"type={type_filter},json={use_json},quiet={quiet}")

    result = CliRunner().invoke(cmd, ["--type", "tex", "--json", "-q"])
    assert result.exit_code == 0
    assert "type=tex,json=True,quiet=True" in result.output
