from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from rdc.commands.completion import completion_cmd


@pytest.fixture(autouse=True)
def _mock_bash_check_version() -> object:
    """Prevent BashComplete.source() from spawning a real bash subprocess."""
    with patch("click.shell_completion.BashComplete._check_version", return_value=True):
        yield


def test_completion_bash() -> None:
    result = CliRunner().invoke(completion_cmd, ["bash"])
    assert result.exit_code == 0
    assert "_rdc_completion" in result.output
    assert "complete" in result.output


def test_completion_zsh() -> None:
    result = CliRunner().invoke(completion_cmd, ["zsh"])
    assert result.exit_code == 0
    assert "compdef" in result.output or "_rdc_completion" in result.output


def test_completion_fish() -> None:
    result = CliRunner().invoke(completion_cmd, ["fish"])
    assert result.exit_code == 0
    assert "complete" in result.output
    assert "rdc" in result.output


def test_completion_auto_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    import rdc.commands.completion as mod

    monkeypatch.setattr(mod, "_detect_shell", lambda: "bash")
    result = CliRunner().invoke(completion_cmd, [])
    assert result.exit_code == 0
    assert "_rdc_completion" in result.output
    assert "Detected shell: bash" in result.output


def test_completion_invalid_shell() -> None:
    result = CliRunner().invoke(completion_cmd, ["powershell"])
    assert result.exit_code != 0
