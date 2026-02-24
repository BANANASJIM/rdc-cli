# Tasks: ai-agent-skill

## Branch
`feat/ai-agent-skill`

## Context

Claude Code can load project-specific skills from `.claude/skills/`. This feature adds an `rdc-cli`
skill consisting of a hand-written `SKILL.md` (trigger phrases, workflow guidance, output format
reference) and an auto-generated `references/commands-quick-ref.md` produced by
`scripts/gen-skill-ref.py`. The generator follows the same Click introspection pattern as the
existing `scripts/gen-stats.py`. A `check-skill-ref` pixi task and a CI lint step enforce that the
committed reference stays in sync with the live CLI.

---

## Phase A — Tests first

- [ ] **A1** Create `tests/unit/test_gen_skill_ref.py`:
  - `test_gen_skill_ref_produces_output` — `generate_skill_ref()` returns a non-empty string
  - `test_gen_skill_ref_contains_all_commands` — output contains every leaf command name
  - `test_gen_skill_ref_deterministic` — two consecutive calls return identical strings
  - `test_gen_skill_ref_contains_help_text` — output contains help text for `open`, `info`,
    and `events`
  - `test_gen_skill_ref_contains_options` — output contains option names `--type` and `--name`
  - `test_gen_skill_ref_handles_subgroups` — output contains `debug pixel`, `debug vertex`,
    and `debug thread`

- [ ] **A2** Create `tests/unit/test_skill_structure.py`:
  - `test_skill_md_exists` — `.claude/skills/rdc-cli/SKILL.md` exists on disk
  - `test_skill_md_has_valid_frontmatter` — file starts with `---` and contains `name:` and
    `description:` keys
  - `test_skill_md_name_is_rdc_cli` — `name` field value is `rdc-cli`
  - `test_skill_md_description_has_triggers` — description contains `RenderDoc`, `.rdc`, and
    `shader`
  - `test_commands_ref_exists` — `.claude/skills/rdc-cli/references/commands-quick-ref.md` exists
  - `test_commands_ref_is_fresh` — `generate_skill_ref()` output matches the committed file byte
    for byte

- [ ] **A3** Run `pixi run test tests/unit/test_gen_skill_ref.py tests/unit/test_skill_structure.py`
  — expect all tests to fail (red phase)

---

## Phase B — Implementation

### B1 — `scripts/gen-skill-ref.py` (new file)

- [ ] **B1-1** Create `scripts/gen-skill-ref.py`:
  - Imports: `click`, `from rdc.cli import main as cli_group`
  - Public helper `iter_leaf_commands(group, ctx)` that yields `(name, cmd)` tuples
    (reusable by tests; similar to `_count_leaf_commands` in `gen-stats.py` but yields instead of counts)
  - Public function `generate_skill_ref() -> str` with Google-style docstring:
    - Opens `click.Context(cli_group)`
    - Walks all commands recursively; for `Group` nodes recurse into `.commands`
    - For each leaf command collects: full dotted name, help text, arguments (name, type,
      required), options (flags, help text, default, type, `is_flag`)
    - Sorts commands alphabetically before rendering
    - Renders markdown: top-level heading per command, sub-sections for arguments and options
    - Returns the complete markdown string
  - `if __name__ == "__main__": print(generate_skill_ref())`
  - All identifiers typed; no `print()` inside `generate_skill_ref()`

### B2 — `.claude/skills/rdc-cli/SKILL.md` (new file, hand-written)

- [ ] **B2-1** Create `.claude/skills/rdc-cli/SKILL.md` with YAML frontmatter:
  ```yaml
  ---
  name: rdc-cli
  description: >
    Use this skill when working with RenderDoc capture files (.rdc), analyzing GPU frames,
    tracing shaders, inspecting draw calls, or running CI assertions against GPU captures.
    Trigger phrases: "open capture", "rdc file", ".rdc", "renderdoc", "shader debug",
    "pixel trace", "draw calls", "GPU frame", "assert pixel", "export render target".
  ---
  ```
- [ ] **B2-2** Write body sections (keep under 2000 words, imperative form):
  1. **Overview** — rdc-cli is a Unix-friendly CLI for RenderDoc captures; daemon-backed
     JSON-RPC; VFS path namespace; composable with standard shell tools
  2. **Core Workflow** — open → inspect → navigate → analyze → export → close; session
     lifecycle; `--session` flag and `$RDC_SESSION`
  3. **Output Formats** — TSV default; `--json` (newline-delimited JSON objects); `--jsonl`;
     `--no-header`; `-q` (quiet); `--format` where applicable
  4. **Common Tasks** — find draw calls, trace a pixel, search shaders by name or source,
     export a render target, browse VFS paths
  5. **CI Assertions** — `assert-pixel`, `assert-clean`, `assert-count`, `assert-state`,
     `assert-image`; non-zero exit on failure
  6. **Session Management** — `rdc open`, `rdc close`, `--session`, `$RDC_SESSION`
  7. **Command Reference** — pointer to `references/commands-quick-ref.md`

### B3 — Generate `references/commands-quick-ref.md`

- [ ] **B3-1** Run:
  ```bash
  python scripts/gen-skill-ref.py > .claude/skills/rdc-cli/references/commands-quick-ref.md
  ```
- [ ] **B3-2** Commit the generated file alongside `SKILL.md` and `gen-skill-ref.py`

### B4 — CI integration

- [ ] **B4-1** Add to `pixi.toml` under `[tasks]`:
  ```toml
  gen-skill-ref = "bash -c 'uv run python scripts/gen-skill-ref.py > .claude/skills/rdc-cli/references/commands-quick-ref.md'"
  check-skill-ref = "bash -c 'diff <(uv run python scripts/gen-skill-ref.py) .claude/skills/rdc-cli/references/commands-quick-ref.md'"
  ```
  Note: both tasks need `bash -c` wrapper for shell redirection/process substitution.
- [ ] **B4-2** Add to `.github/workflows/ci.yml` lint job after the existing lint steps.
  CI uses `uv` directly (no pixi installed), so the step runs the diff command inline:
  ```yaml
  - name: Verify skill reference is fresh
    run: diff <(uv run python scripts/gen-skill-ref.py) .claude/skills/rdc-cli/references/commands-quick-ref.md
    shell: bash
  ```

### B5 — `.gitignore` adjustment

- [ ] **B5-1** Change `.claude/` (line 17 in `.gitignore`) to `.claude/*` (glob form).
  This is required because git never evaluates negation rules inside a directory-level ignore.
  The glob form makes git evaluate each child individually.
- [ ] **B5-2** Add `!.claude/skills/` on the next line to un-ignore the skill directory.
  Result:
  ```
  .claude/*
  !.claude/skills/
  ```
- [ ] **B5-3** Confirm `CLAUDE.md` (line 14) remains gitignored (it has its own line, unaffected)

---

## Phase C — Integration and Verify

- [ ] **C1** `pixi run lint` — zero errors
- [ ] **C2** `pixi run test tests/unit/test_gen_skill_ref.py tests/unit/test_skill_structure.py`
  — all tests pass
- [ ] **C3** `pixi run test` (full suite) — zero failures, coverage unchanged
- [ ] **C4** `pixi run check-skill-ref` — exits 0
- [ ] **C5** `git ls-files .claude/skills/` — lists both `SKILL.md` and
  `references/commands-quick-ref.md`
- [ ] **C6** Verify `CLAUDE.md` is still gitignored: `git ls-files CLAUDE.md` returns empty

---

## File Conflict Analysis

| File | Change type | Conflicts with |
|------|------------|----------------|
| `scripts/gen-skill-ref.py` | New file | None |
| `.claude/skills/rdc-cli/SKILL.md` | New file | None |
| `.claude/skills/rdc-cli/references/commands-quick-ref.md` | New (generated) | None |
| `tests/unit/test_gen_skill_ref.py` | New file | None |
| `tests/unit/test_skill_structure.py` | New file | None |
| `pixi.toml` | Add 2 tasks | Low risk |
| `.github/workflows/ci.yml` | Add 1 step to lint job | Low risk |
| `.gitignore` | Add exception for `.claude/skills/` | Low risk |

Single-worktree sequential execution is sufficient.

---

## Definition of Done

- `pixi run lint && pixi run test` passes with zero failures
- `pixi run check-skill-ref` passes (generated reference matches committed file byte for byte)
- `SKILL.md` has valid YAML frontmatter with `name: rdc-cli` and trigger phrases `RenderDoc`,
  `.rdc`, `shader`
- All leaf commands appear in the auto-generated reference
- `.claude/skills/` is tracked by git; `CLAUDE.md` remains gitignored
- CI lint job includes the skill reference freshness check step
