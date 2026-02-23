# Proposal: skill-auto-install

**Date:** 2026-02-22
**Phase:** Post-5 / release-prep
**Status:** Draft

---

## Problem Statement

PR #87 added Claude Code skill files at `.claude/skills/rdc-cli/` in the repo. These files enable Claude Code to discover rdc-cli's workflow guide and command reference when working inside the repo directory.

Three specific pain points:

1. End users who install rdc-cli via `pip install rdc-cli`, `pipx install rdc-cli`, or AUR never receive the skill files. The `.claude/skills/` directory is part of the repo checkout, not the installed package. A user running `rdc` from a system-wide install gets no Claude Code skill benefit.

2. There is no mechanism to place the skill files into `~/.claude/skills/rdc-cli/`, which is where Claude Code discovers globally installed skills. Users must manually locate and copy the files, which is not discoverable.

3. The skill files currently live only in `.claude/skills/rdc-cli/` (tracked via the `.gitignore` exception added in PR #87). Moving them into the Python package (`src/rdc/_skills/`) and creating a symlink at the old location keeps the developer experience intact while also enabling wheel-based distribution.

---

## Proposed Solution

### Component 1: Move skill files into the Python package

Move the canonical skill files from `.claude/skills/rdc-cli/` into a new `src/rdc/_skills/` package:

```
src/rdc/_skills/
├── __init__.py                       # empty; makes it a package for importlib.resources
├── SKILL.md                          # moved from .claude/skills/rdc-cli/SKILL.md
└── references/                       # data subdirectory; no __init__.py needed
    └── commands-quick-ref.md         # moved from .claude/skills/rdc-cli/references/
```

Add package-data declaration to `pyproject.toml` so setuptools includes the Markdown files in the wheel:

```toml
[tool.setuptools.package-data]
"rdc._skills" = ["**/*.md"]
```

The files ship as part of the wheel and are accessible at runtime via `importlib.resources`.

### Component 2: Symlink for local Claude Code discovery

Replace the `.claude/skills/rdc-cli/` directory with a **relative symlink** pointing to `../../src/rdc/_skills`:

```
.claude/skills/rdc-cli -> ../../src/rdc/_skills
```

Git stores symlinks as their target path string, so the symlink is tracked normally. Claude Code follows the symlink and reads `SKILL.md` and `references/commands-quick-ref.md` from `src/rdc/_skills/`, preserving the developer experience without duplicating files.

No `.gitignore` changes are needed beyond what PR #87 already added (`!.claude/skills/`).

### Component 3: `rdc install-skill` command

New command at `src/rdc/commands/install_skill.py`, following the pattern of `completion.py`:

- Locates bundled skill files via `importlib.resources.files("rdc._skills")`.
- Default (no flags): copies `SKILL.md` and `references/commands-quick-ref.md` to `~/.claude/skills/rdc-cli/`, creating subdirectories as needed. Prints each installed path.
- `--remove`: deletes `~/.claude/skills/rdc-cli/` entirely. Prints confirmation.
- `--check`: compares installed files against bundled content byte-for-byte. Exits 0 if installed and current, exits 1 with a diagnostic message if not installed or stale.
- Installation is idempotent — running `install-skill` always overwrites with the latest bundled content.
- `--check` and `--remove` are mutually exclusive; passing both produces an error.

Register in `cli.py`:

```python
from rdc.commands.install_skill import install_skill_cmd
main.add_command(install_skill_cmd, name="install-skill")
```

### Component 4: Update gen-skill-ref.py output path

The `gen-skill-ref.py` script and related pixi tasks must write to the new canonical location.

Update `pixi.toml`:

```toml
gen-skill-ref   = "bash -c 'uv run python scripts/gen-skill-ref.py > src/rdc/_skills/references/commands-quick-ref.md'"
check-skill-ref = "bash -c 'diff <(uv run python scripts/gen-skill-ref.py) src/rdc/_skills/references/commands-quick-ref.md'"
```

The CI `check-skill-ref` step in `ci.yml` must reference the same new path.

### Component 5: Update test paths

Update `tests/unit/test_skill_structure.py` to resolve all paths from `src/rdc/_skills/` instead of `.claude/skills/rdc-cli/`:

- `test_skill_md_exists`: check `project_root / "src/rdc/_skills/SKILL.md"`.
- `test_skill_md_has_valid_frontmatter`, `test_skill_md_name_is_rdc_cli`, `test_skill_md_description_has_triggers`: read from new path.
- `test_commands_ref_exists`: check `project_root / "src/rdc/_skills/references/commands-quick-ref.md"`.
- `test_commands_ref_is_fresh`: read committed file from new path.

Add new unit tests for `install-skill` in `tests/unit/test_install_skill.py`:

- `test_install_copies_files`: invoke command via `CliRunner` with a tmp `HOME`; assert both files exist at `~/.claude/skills/rdc-cli/`.
- `test_check_exits_0_after_install`: `--check` exits 0 after a successful install.
- `test_check_exits_1_when_not_installed`: `--check` exits 1 before install.
- `test_remove_deletes_directory`: `--remove` deletes the installed directory.

---

## Non-Goals

- Auto-running `install-skill` during `pip install` (post-install hooks are unreliable and disallowed in modern packaging).
- MCP server wrapper for rdc-cli (separate proposal).
- Supporting skill formats other than Claude Code `SKILL.md`.
- Updating the content of `SKILL.md` (already done in PR #87).
- Windows support (rdc-cli is Linux-only; renderdoc replay requires Linux).
- Doctor hint for missing skill installation (deferred — adds complexity for marginal benefit).

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Symlink breaks on Windows | rdc-cli is Linux-only; renderdoc replay requires Linux; not a concern |
| `importlib.resources.files()` API differs across Python versions | `files()` is stable since Python 3.9; project requires `>=3.10` |
| Two apparent locations for skill files confuse contributors | `src/rdc/_skills/` is canonical; `.claude/skills/rdc-cli` is only a symlink — documented in comments |
| `gen-skill-ref.py` path change breaks CI before PR lands | Path change is atomic within the same PR; both pixi tasks and CI step updated together |
| Installed skill becomes stale after `rdc` upgrade | `--check` flag detects staleness; users re-run `rdc install-skill` after upgrade |
| `~/.claude/skills/rdc-cli/` owned by another install method | `--remove` provides clean uninstall; install overwrites files silently (idempotent) |

---

## Acceptance Criteria

1. `pip install .` includes skill files in the wheel: `unzip -l dist/*.whl | grep _skills` lists `SKILL.md` and `commands-quick-ref.md`.
2. `rdc install-skill` copies both files to `~/.claude/skills/rdc-cli/` and prints the installed paths.
3. `rdc install-skill --check` exits 0 immediately after a successful install.
4. `rdc install-skill --check` exits 1 before any install has been performed.
5. `rdc install-skill --remove` deletes `~/.claude/skills/rdc-cli/` and exits 0.
6. `.claude/skills/rdc-cli` is a symlink resolving to `src/rdc/_skills/`; Claude Code reads `SKILL.md` from the repo without any separate copy.
7. `pixi run check-skill-ref` passes with the updated output path.
8. All updated and new unit tests in `test_skill_structure.py` and `test_install_skill.py` pass.
9. `pixi run lint && pixi run test` passes with no regressions.
