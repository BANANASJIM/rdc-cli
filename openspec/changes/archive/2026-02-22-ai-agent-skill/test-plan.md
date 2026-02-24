# Test Plan: ai-agent-skill

## Scope

Changes covered:
1. `.claude/skills/rdc-cli/SKILL.md` — hand-written skill file with YAML frontmatter
2. `.claude/skills/rdc-cli/references/commands-quick-ref.md` — auto-generated command reference
3. `scripts/gen-skill-ref.py` — Click introspection script that generates the command reference
4. `pixi.toml` — new `check-skill-ref` task
5. `.github/workflows/ci.yml` — CI integration for staleness check (uses `uv run` directly, not pixi)
6. `.gitignore` — change `.claude/` to `.claude/*` + add `!.claude/skills/` negation

Out of scope: testing SKILL.md content quality (subjective), integration with Claude Code agent runtime, GPU/daemon handler changes, MCP or llms.txt.

---

## 1. Unit Tests — `tests/unit/test_gen_skill_ref.py`

Tests import from `gen_skill_ref` (the script is on `PYTHONPATH` via `scripts/` or `sys.path` insert).

### 1.1 `test_gen_skill_ref_produces_output`

Import and invoke the generation function; verify it returns a non-empty string.

```python
def test_gen_skill_ref_produces_output() -> None:
    from gen_skill_ref import generate_skill_ref
    result = generate_skill_ref()
    assert isinstance(result, str)
    assert len(result) > 0
```

### 1.2 `test_gen_skill_ref_contains_all_commands`

Verify the output mentions every leaf command name. `gen-skill-ref.py` exports `iter_leaf_commands(group, ctx)` which yields `(name, cmd)` tuples.

```python
def test_gen_skill_ref_contains_all_commands() -> None:
    import click
    from gen_skill_ref import generate_skill_ref, iter_leaf_commands
    from rdc.cli import main as cli_group
    result = generate_skill_ref()
    ctx = click.Context(cli_group)
    for name, _cmd in iter_leaf_commands(cli_group, ctx):
        assert name in result, f"Command {name!r} missing from skill ref"
```

### 1.3 `test_gen_skill_ref_deterministic`

Run the generation function twice and assert identical output.

```python
def test_gen_skill_ref_deterministic() -> None:
    from gen_skill_ref import generate_skill_ref
    assert generate_skill_ref() == generate_skill_ref()
```

### 1.4 `test_gen_skill_ref_contains_help_text`

Verify output includes help text for known commands.

```python
def test_gen_skill_ref_contains_help_text() -> None:
    from gen_skill_ref import generate_skill_ref
    result = generate_skill_ref()
    for cmd in ("open", "info", "events"):
        assert cmd in result, f"Known command {cmd!r} absent from skill ref"
```

### 1.5 `test_gen_skill_ref_contains_options`

Verify output includes option names for a command with well-known options (`events` has `--type` and `--name`).

```python
def test_gen_skill_ref_contains_options() -> None:
    from gen_skill_ref import generate_skill_ref
    result = generate_skill_ref()
    assert "--type" in result
    assert "--name" in result
```

### 1.6 `test_gen_skill_ref_handles_subgroups`

Verify the `debug` group's subcommands appear in the output.

```python
def test_gen_skill_ref_handles_subgroups() -> None:
    from gen_skill_ref import generate_skill_ref
    result = generate_skill_ref()
    for sub in ("pixel", "vertex", "thread"):
        assert sub in result, f"debug subcommand {sub!r} missing from skill ref"
```

---

## 2. Skill Structure Validation — `tests/unit/test_skill_structure.py`

All tests use a `project_root` fixture (`Path(__file__).resolve().parents[2]`) to resolve paths relative to the repository root, avoiding fragile reliance on the working directory.

### 2.1 `test_skill_md_exists`

```python
def test_skill_md_exists(project_root: Path) -> None:
    skill = project_root / ".claude/skills/rdc-cli/SKILL.md"
    assert skill.exists(), "SKILL.md not found"
```

### 2.2 `test_skill_md_has_frontmatter`

SKILL.md must start with `---` YAML frontmatter containing `name:` and `description:`.

```python
def test_skill_md_has_frontmatter(project_root: Path) -> None:
    text = (project_root / ".claude/skills/rdc-cli/SKILL.md").read_text()
    assert text.startswith("---"), "Missing YAML frontmatter"
    assert "name:" in text
    assert "description:" in text
```

### 2.3 `test_skill_md_name_matches`

Frontmatter `name` field must equal `"rdc-cli"`. Uses simple string matching (no `pyyaml` dependency).

```python
def test_skill_md_name_matches(project_root: Path) -> None:
    text = (project_root / ".claude/skills/rdc-cli/SKILL.md").read_text()
    front = text.split("---")[1]
    assert "name: rdc-cli" in front or 'name: "rdc-cli"' in front
```

### 2.4 `test_skill_md_description_has_triggers`

Description must contain trigger phrases recognised by Claude Code (`RenderDoc`, `.rdc`, `shader`).

```python
def test_skill_md_description_has_triggers(project_root: Path) -> None:
    text = (project_root / ".claude/skills/rdc-cli/SKILL.md").read_text()
    for phrase in ("RenderDoc", ".rdc", "shader"):
        assert phrase in text, f"Trigger phrase {phrase!r} missing from SKILL.md"
```

### 2.5 `test_commands_ref_exists`

```python
def test_commands_ref_exists(project_root: Path) -> None:
    ref = project_root / ".claude/skills/rdc-cli/references/commands-quick-ref.md"
    assert ref.exists(), "commands-quick-ref.md not found"
```

### 2.6 `test_commands_ref_is_fresh`

Run `generate_skill_ref()` and compare its output with the committed file; they must be identical (same logic as the CI staleness check).

```python
def test_commands_ref_is_fresh(project_root: Path) -> None:
    from gen_skill_ref import generate_skill_ref
    committed = (project_root / ".claude/skills/rdc-cli/references/commands-quick-ref.md").read_text()
    assert committed == generate_skill_ref(), (
        "commands-quick-ref.md is stale — run `pixi run gen-skill-ref` to regenerate"
    )
```

Note: `project_root` fixture is defined in the test file or `conftest.py` as `Path(__file__).resolve().parents[2]`.

---

## 3. Script Static Checks — `scripts/gen-skill-ref.py`

Note: existing `pixi run lint` only checks `src tests`. The script must be linted separately or the lint scope must be expanded.

| Check | Command |
|-------|---------|
| Valid Python syntax | `python -m py_compile scripts/gen-skill-ref.py` |
| Type check | `mypy scripts/gen-skill-ref.py` |
| Lint | `ruff check scripts/gen-skill-ref.py` |

---

## 4. CI Integration Verification

CI uses `uv run` directly (not pixi). The skill reference freshness check runs as a step in the lint job.

| Scenario | Expected |
|----------|----------|
| Fresh reference (matches generated output) | CI step exits 0 |
| Stale reference (command help text changed without regenerating) | CI step exits non-zero with diff output |

Manual test for the stale case: edit any `help=` string in a command, run `pixi run check-skill-ref`, confirm non-zero exit and a clear diff message.

---

## 5. Gitignore Verification

| Check | Command |
|-------|---------|
| `.claude/skills/` is tracked | `git ls-files .claude/skills/` lists `SKILL.md` and `commands-quick-ref.md` |
| `.claude/CLAUDE.md` remains gitignored | `git ls-files .claude/CLAUDE.md` returns empty |
| `.claude/*` glob form used (not `.claude/`) | `grep -q '.claude/\*' .gitignore` |

---

## 6. Non-Goals

- No testing of SKILL.md prose quality (subjective)
- No integration testing with the Claude Code agent runtime (requires manual verification)
- No GPU tests (no daemon or handler changes)
- No testing of MCP or llms.txt (out of scope)

---

## Coverage Summary

| Area | Type | Count |
|------|------|-------|
| Gen script output correctness | Unit | 6 |
| Skill file structure | Unit | 6 |
| Script static checks | Lint/Type | 3 |
| CI integration | Manual | 2 |
| Gitignore correctness | Manual | 3 |
