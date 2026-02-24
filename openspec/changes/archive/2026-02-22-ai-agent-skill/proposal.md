# Proposal: ai-agent-skill

**Date:** 2026-02-22
**Phase:** Post-5 / release-prep maintenance
**Status:** Draft

---

## Problem Statement

rdc-cli has 54 commands, daemon-backed JSON-RPC, and TSV/JSON/JSONL output — but no AI-agent-facing documentation exists.

Three specific pain points:

1. AI agents (Claude Code, GitHub Copilot, etc.) have no structured entry point describing what rdc-cli does, what commands exist, or how to compose them into workflows. Users who want to use an AI agent to analyze RenderDoc captures must manually explain every command in the conversation.

2. The command reference that does exist (README, docs site) is written for human readers, not agent consumption. It lacks machine-readable structure, trigger phrase hints, and task-oriented workflow recipes that allow an agent to match a user intent to the correct command sequence.

3. Any hand-written command reference goes stale as commands are added, renamed, or given new options. There is currently no mechanism to detect or prevent drift.

---

## Proposed Solution

### Component 1: `.claude/skills/rdc-cli/` — skill directory

Create `.claude/skills/rdc-cli/` containing:

```
.claude/skills/rdc-cli/
├── SKILL.md                     # Core workflow guide (~2000 words, hand-written)
└── references/
    └── commands-quick-ref.md    # Auto-generated from Click introspection
```

**SKILL.md** is hand-written for quality. It includes:

- YAML frontmatter with `name: rdc-cli` and a `description` field listing trigger phrases that cause Claude Code to activate the skill: "analyze a RenderDoc capture", "debug a shader", "inspect GPU state", "export textures", "trace a pixel", "find shader issues", and file extensions `.rdc`, as well as general terms "RenderDoc", "graphics debugging", "draw calls", "GPU pipeline".
- Core workflow section covering the standard session lifecycle: `open` → inspect (`info`, `events`, `stats`) → navigate VFS (`ls`, `cat`) → analyze (`shaders`, `pipeline`, `resources`) → export (`export-texture`, `log`) → `close`.
- Output format flags: `--json`, `--jsonl`, `--no-header`, `-q`, and when to use each (machine pipeline vs. human review vs. CI assertion).
- Common task recipes as numbered steps: find all draw calls, trace a pixel (`debug pixel`), search shader source, export all render targets, compare event state before/after a pass.
- VFS navigation pattern: how path addressing works, wildcard usage, `ls -l` vs. `cat`.
- CI assertion pattern: how to use rdc-cli in a shell script or pytest fixture with `--json` and `jq`.
- Pointer to `references/commands-quick-ref.md` for the full command list with parameters.

**`references/commands-quick-ref.md`** is auto-generated (see Component 2). It is committed to the repo so agents can read it without running any script.

### Component 2: `scripts/gen-skill-ref.py` — auto-generation script

A new script following the pattern of `scripts/gen-stats.py`:

- Imports `from rdc.cli import main as cli_group` and `click`.
- Walks `cli_group.list_commands(ctx)` recursively, skipping hidden commands.
- For each leaf command: extracts `name`, `help` (first paragraph), all `params` (arguments and options) with their `type`, `default`, `required`, and `help` attributes.
- Outputs a Markdown document with one section per top-level group, a subsection per command, and a parameter table per command.
- Writes to stdout; caller pipes to the target file.
- Deterministic: commands sorted alphabetically; params in Click registration order (stable).
- No external dependencies beyond Click (already in the project).

Invocation: `uv run python scripts/gen-skill-ref.py > .claude/skills/rdc-cli/references/commands-quick-ref.md`

### Component 3: CI integration — `check-skill-ref` task

- New pixi task `gen-skill-ref`: runs `scripts/gen-skill-ref.py` and writes to the committed path (wrapped in `bash -c` for shell redirection).
- New pixi task `check-skill-ref`: diffs generated output against committed `commands-quick-ref.md`, exits non-zero if they differ (with a message directing the developer to run `pixi run gen-skill-ref` and commit the result).
- `check-skill-ref` is added to the `lint` job in `ci.yml` using `uv run` directly (CI does not install pixi — it uses `uv` throughout). It is lightweight (no GPU, no network) and runs on every push.
- `check-skill-ref` is NOT added to the `pixi run check` composite (which is `lint + typecheck + test`) — it runs only in CI to avoid slowing local development.

### Component 4: `.gitignore` adjustment

`.claude/` is currently gitignored entirely (line 17 in `.gitignore`). Change `.claude/` to `.claude/*` (glob) and add a negation rule so the skill directory is tracked:

```
.claude/*
!.claude/skills/
```

**Important:** Using `.claude/*` instead of `.claude/` is required because git will never look inside a directory-level ignore to evaluate negation rules. The glob form makes git evaluate each child individually, allowing `!.claude/skills/` to take effect.

`CLAUDE.md` remains untracked via its own line in `.gitignore` (line 14).

---

## Non-Goals

- MCP server wrapper for rdc-cli (future work, separate proposal).
- `llms.txt` standard file at repo root (future work).
- Auto-generating the SKILL.md body (hand-written for workflow quality).
- Distributing the skill as a standalone `.skill` package.
- Supporting skill formats other than Claude Code SKILL.md.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| `.claude/` gitignored — skills not committed | Add `!.claude/skills/` exception to `.gitignore` |
| `commands-quick-ref.md` goes stale as commands evolve | `check-skill-ref` in CI fails on drift; developer runs `gen-skill-ref` to fix |
| SKILL.md too large for agent context window | Progressive disclosure: core workflow in SKILL.md (~2000 words), full parameter detail in `references/` |
| Click API changes break `gen-skill-ref.py` | Script uses the same stable introspection API as `gen-stats.py`; any breakage surfaces immediately in CI |
| Trigger phrases too narrow — agent doesn't activate skill | Description field includes both specific phrases and general terms; can be expanded without code changes |

---

## Acceptance Criteria

1. `.claude/skills/rdc-cli/SKILL.md` exists with valid YAML frontmatter containing `name` and `description` (with trigger phrases).
2. `references/commands-quick-ref.md` is auto-generated and lists all leaf commands with help text and parameter tables.
3. `scripts/gen-skill-ref.py` produces byte-identical output on two consecutive runs against the same CLI (deterministic).
4. `pixi run check-skill-ref` exits 0 when `commands-quick-ref.md` matches generated output, non-zero when it does not.
5. `ci.yml` lint job includes a skill reference freshness step using `uv run` directly (no pixi), running without GPU or network.
6. `pixi run check` passes with no regressions.
7. `.claude/skills/` is tracked by git: `git ls-files .claude/skills/` lists both files.
