# CLAUDE.md — rdc-cli Development Rules

These rules apply to ALL coding agents working on this project. No exceptions.

## Source of Truth

**Obsidian design docs are the single source of truth.**
Location: `~/Documents/Obsidian Vault/rdoc-cli/`

Before any implementation work:
1. Read the relevant Obsidian design docs
2. Read the OpenSpec proposal for your feature (`openspec/changes/<feature>/`)
3. Implementation follows design — if there's a conflict, STOP and discuss

## OpenSpec Workflow

Every feature follows this flow:
1. `openspec/changes/<feature>/proposal.md` — what and why
2. `openspec/changes/<feature>/test-plan.md` — test design (mandatory gate)
3. `openspec/changes/<feature>/tasks.md` — implementation checklist
4. `openspec/changes/<feature>/specs/` — spec deltas (ADDED/MODIFIED/REMOVED)
5. `openspec validate --all` MUST pass before committing

## Test-First

**No Test Design, No Implementation.**
- Write tests BEFORE implementation code
- Mock renderdoc module: `tests/mocks/mock_renderdoc.py`
- Test layers: Unit (formatters, parsers) → Mock (daemon with mock RD) → Integration (GPU, deferred)

## Code Standards

- **Language**: ALL code, comments, commits, docstrings, CLI help text in English
- **Type hints**: Complete, mypy strict mode
- **No `print()`**: Use `click.echo()` or formatters
- **No bare `except:`**: At least `except Exception:`
- **Paths**: Use `pathlib.Path`, not `os.path`
- **Imports**: ruff auto-sorts (stdlib → third-party → local)
- **Docstrings**: Google style for all public functions

## Commit Messages

[Conventional Commits](https://www.conventionalcommits.org/) strictly enforced:
```
<type>(<scope>): <short description>
```
Types: `feat`, `fix`, `refactor`, `test`, `docs`, `ci`, `chore`
Scopes: `daemon`, `cli`, `adapter`, `fmt`, `openspec`, etc.

**FORBIDDEN in commit messages**: `AI`, `ai`, `assistant`, `generated`, `copilot`, `claude`, `gpt`

## Quality Gates

Before pushing, run:
```bash
make check          # ruff + mypy strict + pytest ≥80% coverage
openspec validate --all
```

ALL must pass. No exceptions.

## Output Format Rules

From `设计/设计原则.md`:
- **TSV default** for list commands (tab-separated, one record per line)
- **key: value** blocks for detail commands
- **Raw numbers** always (e.g. `1200000` not `1.2M`)
- **`-`** for empty/null fields
- **Footer/summary to stderr** — never pollute stdout
- Escape rules: `\t` for tabs, `\n` for newlines in field values
- Support: `--no-header`, `--json`, `--jsonl`, `-q/--quiet`, `--sort`, `--limit`

## Branch Strategy

- One feature = one branch = one PR
- Branch naming: `feat/`, `fix/`, `refactor/`, `docs/`, `test/`, `ci/`
- Squash merge only
- Non-conflicting features MUST be developed in parallel
- Shared layers merge first
- Rebase onto latest master before merge

## Architecture

- Commands (`src/rdc/commands/`) are thin CLI adapters — delegate to services
- Services (`src/rdc/services/`) hold business logic
- Daemon (`src/rdc/daemon_server.py`) handles JSON-RPC, uses `RenderDocAdapter`
- Adapter (`src/rdc/adapter.py`) wraps renderdoc API for version compatibility
- Formatters (`src/rdc/formatters/`) handle TSV/JSON/JSONL output
- **Never call renderdoc API directly** — always go through adapter

## Key Files

| File | Purpose |
|------|---------|
| `openspec/changes/` | Active feature proposals |
| `openspec/specs/` | Merged specifications |
| `tests/mocks/mock_renderdoc.py` | Mock renderdoc module for GPU-free testing |
| `src/rdc/daemon_server.py` | JSON-RPC daemon with replay lifecycle |
| `src/rdc/adapter.py` | RenderDoc version compatibility layer |
| `Makefile` | `make check` = lint + typecheck + test |
