# Test Plan: skill-auto-install

## Scope

- In scope: `src/rdc/_skills/` package (SKILL.md, references/commands-quick-ref.md, __init__.py),
  `src/rdc/commands/install_skill.py` CLI command, `.claude/skills/rdc-cli` symlink,
  package data inclusion in wheel, `importlib.resources` discoverability,
  CI skill-ref freshness check path update.
- Out of scope: Claude Code runtime discovery (manual only), AUR packaging, GPU tests.

---

## New Test Files

### `tests/unit/test_install_skill.py`

Tests for the `rdc install-skill` command using `click.testing.CliRunner` and `tmp_path`.
All tests monkeypatch `Path.home()` to a `tmp_path` subdirectory so no real `~/.claude/` is touched.

**Tests:**

| Test name | Description |
|-----------|-------------|
| `test_install_skill_creates_files` | Run `install-skill` with monkeypatched home. Verify `SKILL.md` and `references/commands-quick-ref.md` exist under `{tmp}/.claude/skills/rdc-cli/` and exit code is 0. |
| `test_install_skill_overwrites_existing` | Pre-create stale content in target dir, run `install-skill`, verify files are updated to current package content. |
| `test_install_skill_check_not_installed` | Run `install-skill --check` when target dir is absent. Exit code must be 1. |
| `test_install_skill_check_installed` | Run `install-skill` (no flags), then `install-skill --check`. Exit code must be 0. |
| `test_install_skill_remove` | Run `install-skill`, then `install-skill --remove`. Verify `~/.claude/skills/rdc-cli/` directory no longer exists. Exit code is 0. |
| `test_install_skill_remove_not_installed` | Run `install-skill --remove` when target dir does not exist. Must exit 0 with a user-friendly message (no exception). |
| `test_install_skill_check_and_remove_mutually_exclusive` | Run `install-skill --check --remove`. Must exit non-zero with an error message about mutually exclusive options. |

Monkeypatching pattern:

```python
monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
```

The command must derive the target as `Path.home() / ".claude" / "skills" / "rdc-cli"`.

---

## Updated Test Files

### `tests/unit/test_skill_structure.py`

Update all path references from `.claude/skills/rdc-cli/` to `src/rdc/_skills/`.
The test logic is unchanged; only the base path constant changes.

| Test name | Description |
|-----------|-------------|
| `test_skill_md_exists` | `src/rdc/_skills/SKILL.md` exists on disk. |
| `test_skill_md_has_valid_frontmatter` | File begins with `---` YAML frontmatter that parses without error. |
| `test_skill_md_name_is_rdc_cli` | Frontmatter field `name` equals `rdc-cli`. |
| `test_skill_md_description_has_triggers` | Frontmatter or body contains trigger keywords expected by Claude Code skill discovery. |
| `test_commands_ref_exists` | `src/rdc/_skills/references/commands-quick-ref.md` exists on disk. |
| `test_commands_ref_is_fresh` | `generate_skill_ref()` output matches the file contents exactly (CI freshness guard). |

---

### `tests/unit/test_gen_skill_ref.py`

No changes required. These tests cover the generation function itself, not file locations.
Verify they continue to pass unmodified after the path migration.

---

## Symlink Verification (Manual)

| Check | Command |
|-------|---------|
| Symlink exists | `test -L .claude/skills/rdc-cli` |
| Symlink target is correct | `readlink .claude/skills/rdc-cli` returns `../../src/rdc/_skills` |
| Files reachable via symlink | `test -f .claude/skills/rdc-cli/SKILL.md` |

---

## Package Data Verification (Manual)

| Check | Method |
|-------|--------|
| Wheel includes skill files | `pip wheel . -w /tmp/rdc-dist && unzip -l /tmp/rdc-dist/*.whl \| grep _skills` — output must include `SKILL.md` and `references/commands-quick-ref.md` |
| `importlib.resources` finds package | `python -c "from importlib.resources import files; print(list(files('rdc._skills').iterdir()))"` exits 0 and lists the skill files |

---

## CI Integration

The existing CI step that checks `commands-quick-ref.md` freshness must be updated to reference
`src/rdc/_skills/references/commands-quick-ref.md` instead of the old `.claude/` path.

| Scenario | Expected |
|----------|----------|
| Reference file matches `generate_skill_ref()` output | CI exits 0 |
| Reference file is stale (content differs) | CI exits non-zero with diff output |

---

## Coverage Summary

| Area | Type | Count |
|------|------|-------|
| `install-skill` command | Unit | 7 |
| Skill structure (updated paths) | Unit | 6 |
| Gen-skill-ref (unchanged) | Unit | 7 |
| Symlink | Manual | 3 |
| Package data | Manual | 2 |
| CI integration | Manual | 2 |
| **Total** | | **27** |

---

## Test Matrix

| Dimension | Value |
|-----------|-------|
| Python | 3.10, 3.12, 3.14 (CI matrix) |
| Platform | Linux (primary) |
| GPU | Not required |
| CI | `pixi run lint && pixi run test` |

### Fixtures

- `test_install_skill.py`: `CliRunner`, `tmp_path`, `monkeypatch` on `Path.home`.
- `test_skill_structure.py`: `project_root` fixture (existing pattern from `__file__`).
- No daemon state, no mock renderdoc, no socket mocks.

---

## Non-Goals

- No testing Claude Code runtime discovery (manual verification only).
- No testing AUR packaging (AUR consumes the wheel; package data is inherited automatically).
- No GPU integration tests.
- No Windows / macOS testing.
