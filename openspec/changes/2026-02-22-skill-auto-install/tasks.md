# Tasks: skill-auto-install

### Branch
`skill-install`

### Context
Move skill files into the Python package (`src/rdc/_skills/`) so they are bundled in the wheel and distributable via pip. Add `rdc install-skill` command to copy them to `~/.claude/skills/rdc-cli/`. Create a relative symlink at `.claude/skills/rdc-cli` pointing to `../../src/rdc/_skills` so Claude Code can discover the skill during local development without any changes to the skill files themselves.

---

## Phase A — Tests first

- [ ] **A1** Create `tests/unit/test_install_skill.py`:
  - `test_install_skill_creates_files` — CliRunner invokes `install-skill` with monkeypatched `Path.home()`; verify `SKILL.md` and `references/commands-quick-ref.md` are created under `{tmp}/.claude/skills/rdc-cli/`
  - `test_install_skill_overwrites_existing` — create stale files, run `install-skill`, verify content is updated
  - `test_install_skill_check_not_installed` — `install-skill --check` exits 1 when not installed
  - `test_install_skill_check_installed` — install first, then `--check` exits 0
  - `test_install_skill_remove` — install first, then `--remove` removes the target directory
  - `test_install_skill_remove_not_installed` — `--remove` when nothing installed exits 0 gracefully
  - `test_install_skill_check_and_remove_mutually_exclusive` — `--check --remove` exits non-zero with error

- [ ] **A2** Update `tests/unit/test_skill_structure.py`:
  - Change all path references from `.claude/skills/rdc-cli/` to `src/rdc/_skills/`
  - Example: `project_root / "src/rdc/_skills/SKILL.md"` instead of `project_root / ".claude/skills/rdc-cli/SKILL.md"`

- [ ] **A3** Run tests — expect `test_install_skill` tests to fail (red phase); `test_skill_structure` tests may partially fail until B1 is complete

---

## Phase B — Implementation

- [ ] **B1** Move skill files into Python package:
  - Create `src/rdc/_skills/__init__.py` (empty)
  - Move `.claude/skills/rdc-cli/SKILL.md` → `src/rdc/_skills/SKILL.md`
  - Move `.claude/skills/rdc-cli/references/commands-quick-ref.md` → `src/rdc/_skills/references/commands-quick-ref.md`

- [ ] **B2** Create symlink for local Claude Code discovery:
  - Remove the now-empty `.claude/skills/rdc-cli/` directory
  - Create relative symlink: `.claude/skills/rdc-cli` → `../../src/rdc/_skills`
  - Verify: `readlink .claude/skills/rdc-cli` outputs `../../src/rdc/_skills`

- [ ] **B3** Add package-data to `pyproject.toml`:
  ```toml
  [tool.setuptools.package-data]
  "rdc._skills" = ["**/*.md"]
  ```

- [ ] **B4** Create `src/rdc/commands/install_skill.py`:
  - `_skill_target() -> Path`: returns `Path.home() / ".claude" / "skills" / "rdc-cli"`
  - `_bundled_files() -> list[tuple[Traversable, str]]`: uses `importlib.resources.files("rdc._skills")` to enumerate `.md` files recursively; returns list of `(traversable, relative_name)` pairs. (`Traversable` from `importlib.resources.abc`)
  - `_install(target: Path) -> list[str]`: copies all bundled files to target, creating parent directories as needed; returns list of installed relative paths
  - `_check(target: Path) -> bool`: returns `True` if all bundled files exist at target and content matches byte-for-byte
  - `_remove(target: Path) -> bool`: removes the target directory if it exists; returns `True` if something was removed
  - Click command `install_skill_cmd` with mutually exclusive `--check` / `--remove` flags:
    - Default (no flags): runs `_install`, prints each installed path
    - `--check`: runs `_check`, exits 0 if installed, exits 1 otherwise
    - `--remove`: runs `_remove`, prints result message
  - Uses `click.echo()` for all output; no `print()`

- [ ] **B5** Register command in `src/rdc/cli.py`:
  - Add `from rdc.commands.install_skill import install_skill_cmd`
  - Add `main.add_command(install_skill_cmd, name="install-skill")`

- [ ] **B6** Regenerate `commands-quick-ref.md`:
  - Run `pixi run gen-skill-ref` (after B5 updates the path in B6b) to include the new `install-skill` command
  - Without this, `test_commands_ref_is_fresh` and `pixi run check-skill-ref` will fail

- [ ] **B7** Update pixi.toml task paths:
  - `gen-skill-ref` task: change output path argument to `src/rdc/_skills/references/commands-quick-ref.md`
  - `check-skill-ref` task: change diff path to `src/rdc/_skills/references/commands-quick-ref.md`

- [ ] **B8** Update CI path in `.github/workflows/ci.yml`:
  - Change the skill reference freshness check `diff` path to `src/rdc/_skills/references/commands-quick-ref.md`

---

## Phase C — Integration and Verify

- [ ] **C1** `pixi run lint` — zero errors
- [ ] **C2** `pixi run test tests/unit/test_install_skill.py` — all 7 tests pass
- [ ] **C3** `pixi run test tests/unit/test_skill_structure.py` — all tests pass with updated paths
- [ ] **C4** `pixi run test tests/unit/test_gen_skill_ref.py` — all 7 tests pass (file unchanged)
- [ ] **C5** `pixi run test` (full suite) — zero failures
- [ ] **C6** `pixi run check-skill-ref` — exits 0
- [ ] **C7** Verify symlink: `test -L .claude/skills/rdc-cli && readlink .claude/skills/rdc-cli`
- [ ] **C8** Manual smoke test: `rdc install-skill` then `rdc install-skill --check` exits 0, then `rdc install-skill --remove` cleans up

---

## File Conflict Analysis

| File | Change type | Conflicts with |
|------|-------------|----------------|
| `src/rdc/_skills/__init__.py` | New file | None |
| `src/rdc/_skills/SKILL.md` | Moved from `.claude/skills/rdc-cli/` | None |
| `src/rdc/_skills/references/commands-quick-ref.md` | Moved | None |
| `.claude/skills/rdc-cli` | Directory → relative symlink | None |
| `src/rdc/commands/install_skill.py` | New file | None |
| `tests/unit/test_install_skill.py` | New file | None |
| `tests/unit/test_skill_structure.py` | Path strings updated | Low risk |
| `src/rdc/cli.py` | Add 2 lines (import + add_command) | Low risk |
| `pyproject.toml` | Add package-data section | Low risk |
| `pixi.toml` | Update 2 task paths | Low risk |
| `.github/workflows/ci.yml` | Update 1 path string | Low risk |

Single-worktree sequential execution is sufficient — no file conflicts between phases.

---

## Definition of Done

- `pixi run lint && pixi run test` passes with zero failures
- `rdc install-skill` copies `SKILL.md` and `references/commands-quick-ref.md` to `~/.claude/skills/rdc-cli/`
- `rdc install-skill --check` exits 0 after a successful install
- `rdc install-skill --remove` removes the installed files and exits 0
- `.claude/skills/rdc-cli` is a symlink resolving to `../../src/rdc/_skills`
- Built wheel includes `_skills/**/*.md` files (verified via `pip show -f rdc-cli | grep _skills`)
- CI freshness check (`check-skill-ref`) passes with updated paths
