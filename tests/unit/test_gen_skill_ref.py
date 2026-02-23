"""Tests for scripts/gen-skill-ref.py — skill reference generator."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import click

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gen-skill-ref.py"


def _load_gen_skill_ref() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_skill_ref", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_gen_skill_ref()
generate_skill_ref = _mod.generate_skill_ref
iter_leaf_commands = _mod.iter_leaf_commands


def test_gen_skill_ref_produces_output() -> None:
    result = generate_skill_ref()
    assert isinstance(result, str)
    assert len(result) > 0


def test_gen_skill_ref_contains_all_commands() -> None:
    from rdc.cli import main as cli_group

    result = generate_skill_ref()
    ctx = click.Context(cli_group)
    for name, _cmd in iter_leaf_commands(cli_group, ctx):
        assert name in result, f"Command {name!r} missing from skill ref"


def test_gen_skill_ref_deterministic() -> None:
    assert generate_skill_ref() == generate_skill_ref()


def test_gen_skill_ref_contains_help_text() -> None:
    result = generate_skill_ref()
    for cmd in ("open", "info", "events"):
        assert cmd in result, f"Known command {cmd!r} absent from skill ref"


def test_gen_skill_ref_contains_options() -> None:
    result = generate_skill_ref()
    assert "--type" in result
    assert "--name" in result


def test_gen_skill_ref_handles_subgroups() -> None:
    result = generate_skill_ref()
    for sub in ("pixel", "vertex", "thread"):
        assert sub in result, f"debug subcommand {sub!r} missing from skill ref"


def test_gen_skill_ref_no_sentinel_leak() -> None:
    result = generate_skill_ref()
    assert "Sentinel" not in result, "Click internal Sentinel leaked into output"
