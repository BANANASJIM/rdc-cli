"""Tests for .claude/skills/rdc-cli/ structure and freshness."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gen-skill-ref.py"


def _load_gen_skill_ref() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_skill_ref", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_skill_md_exists(project_root: Path) -> None:
    skill = project_root / ".claude/skills/rdc-cli/SKILL.md"
    assert skill.exists(), "SKILL.md not found"


def test_skill_md_has_valid_frontmatter(project_root: Path) -> None:
    text = (project_root / ".claude/skills/rdc-cli/SKILL.md").read_text()
    assert text.startswith("---"), "Missing YAML frontmatter"
    assert "name:" in text
    assert "description:" in text


def test_skill_md_name_is_rdc_cli(project_root: Path) -> None:
    text = (project_root / ".claude/skills/rdc-cli/SKILL.md").read_text()
    front = text.split("---")[1]
    assert "name: rdc-cli" in front or 'name: "rdc-cli"' in front


def test_skill_md_description_has_triggers(project_root: Path) -> None:
    text = (project_root / ".claude/skills/rdc-cli/SKILL.md").read_text()
    for phrase in ("RenderDoc", ".rdc", "shader"):
        assert phrase in text, f"Trigger phrase {phrase!r} missing from SKILL.md"


def test_commands_ref_exists(project_root: Path) -> None:
    ref = project_root / ".claude/skills/rdc-cli/references/commands-quick-ref.md"
    assert ref.exists(), "commands-quick-ref.md not found"


def test_commands_ref_is_fresh(project_root: Path) -> None:
    mod = _load_gen_skill_ref()
    committed = (
        project_root / ".claude/skills/rdc-cli/references/commands-quick-ref.md"
    ).read_text()
    assert committed == mod.generate_skill_ref(), (
        "commands-quick-ref.md is stale — run `pixi run gen-skill-ref` to regenerate"
    )
