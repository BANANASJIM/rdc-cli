"""Tests for `rdc install-skill` command."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from rdc.commands.install_skill import install_skill_cmd


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return home


def _target(home: Path) -> Path:
    return home / ".claude" / "skills" / "rdc-cli"


def test_install_skill_creates_files(fake_home: Path) -> None:
    result = CliRunner().invoke(install_skill_cmd)
    assert result.exit_code == 0
    target = _target(fake_home)
    assert (target / "SKILL.md").exists()
    assert (target / "references" / "commands-quick-ref.md").exists()


def test_install_skill_overwrites_existing(fake_home: Path) -> None:
    target = _target(fake_home)
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("stale")
    result = CliRunner().invoke(install_skill_cmd)
    assert result.exit_code == 0
    assert (target / "SKILL.md").read_text() != "stale"


def test_install_skill_check_not_installed(fake_home: Path) -> None:
    result = CliRunner().invoke(install_skill_cmd, ["--check"])
    assert result.exit_code == 1


def test_install_skill_check_installed(fake_home: Path) -> None:
    runner = CliRunner()
    runner.invoke(install_skill_cmd)
    result = runner.invoke(install_skill_cmd, ["--check"])
    assert result.exit_code == 0


def test_install_skill_remove(fake_home: Path) -> None:
    runner = CliRunner()
    runner.invoke(install_skill_cmd)
    target = _target(fake_home)
    assert target.exists()
    result = runner.invoke(install_skill_cmd, ["--remove"])
    assert result.exit_code == 0
    assert not target.exists()


def test_install_skill_remove_not_installed(fake_home: Path) -> None:
    result = CliRunner().invoke(install_skill_cmd, ["--remove"])
    assert result.exit_code == 0
    assert "Nothing to remove" in result.output


def test_install_skill_check_and_remove_mutually_exclusive(fake_home: Path) -> None:
    result = CliRunner().invoke(install_skill_cmd, ["--check", "--remove"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output
