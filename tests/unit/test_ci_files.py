from __future__ import annotations

from pathlib import Path


def test_commitlint_config_exists() -> None:
    assert Path(".commitlintrc.yml").exists()


def test_commitlint_workflow_exists() -> None:
    assert Path(".github/workflows/commitlint.yml").exists()
