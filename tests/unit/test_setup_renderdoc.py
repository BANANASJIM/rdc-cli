"""Unit tests for rdc setup-renderdoc command."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from rdc.commands.setup_renderdoc import setup_renderdoc_cmd


def test_setup_renderdoc_help() -> None:
    result = CliRunner().invoke(setup_renderdoc_cmd, ["--help"])
    assert result.exit_code == 0
    assert "renderdoc" in result.output.lower()


def test_setup_renderdoc_delegates_no_args() -> None:
    with patch("rdc._build_renderdoc.main") as mock_main:
        CliRunner().invoke(setup_renderdoc_cmd, [])
    mock_main.assert_called_once_with([])


def test_setup_renderdoc_delegates_all_options() -> None:
    with patch("rdc._build_renderdoc.main") as mock_main:
        CliRunner().invoke(
            setup_renderdoc_cmd,
            ["/tmp/install", "--build-dir", "/tmp/build", "--version", "v1.40", "--jobs", "8"],
        )
    mock_main.assert_called_once_with(
        ["/tmp/install", "--build-dir", "/tmp/build", "--version", "v1.40", "--jobs", "8"]
    )
