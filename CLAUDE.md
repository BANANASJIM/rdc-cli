# rdc-cli Development Guide

## Obsidian Vault Rules (MUST follow)

Design docs live in the Obsidian vault and are the single source of truth.
Vault path: `/home/jim_z/Documents/Obsidian Vault/rdoc-cli/`

### SSoT Routing — where to find each type of information

| Information | Canonical file | Never duplicate in other files |
|-------------|---------------|-------------------------------|
| Progress numbers (tests, methods, coverage) | `进度跟踪.md` | Use link, not hardcode |
| Phase roadmap, task breakdown, deferred items | `规划/Roadmap.md` | Use link, not hardcode |
| Command specs + Phase assignment | `设计/命令总览.md` | Use link, not hardcode |
| JSON-RPC method list | `设计/交互模式.md` | Use link, not hardcode |
| Decision records | `归档/决策记录.md` | Use link, not hardcode |
| Bugs and P1 fixes only | `待解决.md` | No feature tasks here |

### Vault structure

- `设计/` — finalized design specs (what to build)
- `工程/` — engineering process (how to build)
- `规划/` — planning and roadmap (when to build)
- `调研/` — research and analysis (exploration)
- `归档/` — completed phase archives (frozen records)
- `测试/` — test session reports
- Root: `rdc-cli.md` (MOC), `进度跟踪.md`, `待解决.md`

### Rules for modifying vault files

1. Before changing any vault file, `git -C "/home/jim_z/Documents/Obsidian Vault" pull` to get latest
2. Never hardcode metrics (test count, method count) — link to SSoT file
3. Phase assignments: `命令总览.md` is authoritative — check it before assuming
4. If adding new decisions, append to `归档/决策记录.md` with next D-NNN number
5. Deferred features go in `Roadmap.md` "未计划/推迟" only — not in other files
6. Every new vault file needs: `#rdc-cli` tag + `父页面` callout + `相关` footer

### Current Phase: 4A+4B complete (Debug + Shader Edit-Replay)

Next: Phase 4C (Overlay/Mesh) or release
Roadmap: `规划/Roadmap.md`
Open bugs: `待解决.md`

## Core Disciplines

1. **Obsidian design docs are single source of truth** — strictly follow them
2. **OpenSpec driven** — every feature: proposal + test-plan + tasks, reviewed before coding
3. **No Test Design, No Implementation**
4. **All English output** — code, commits, PRs, docs (Chinese only in Obsidian design docs)
5. **`pixi run lint && pixi run test` must pass before PR**

## Design Docs (Obsidian Vault)

Before making changes, always consult:
`/home/jim_z/Documents/Obsidian Vault/rdoc-cli/`

Key references:
- `rdc-cli.md` — Project overview and doc navigation
- `设计/命令总览.md` — Full command reference
- `设计/API 实现映射.md` — RenderDoc Python API mapping per command
- `设计/设计原则.md` — Output philosophy, global options, exit codes
- `设计/交互模式.md` — Daemon architecture, JSON-RPC protocol
- `工程/开发流程.md` — OpenSpec workflow, branch strategy, code style
- `工程/测试策略.md` — Testing layers, mock module, CI matrix

If implementation conflicts with design: stop → discuss with Jim → update Obsidian docs first → then code.

## Git Workflow

- Never push master directly — feature branch + PR + squash merge
- Non-conflicting tasks must be split into parallel branches
- Conventional Commits: `<type>(<scope>): <description>`
- Commit messages must NEVER contain "AI", "ai", "assistant", "generated"

## Completion Checklist

1. OpenSpec archive归档
2. Update Obsidian 进度跟踪
3. Record decisions/deviations/lessons learned

## Code Review

- Multi-perspective review with different agents (Opus / Codex / Gemini)

## Code Style

- Comments concise; skip self-explanatory ones
- Keep code minimal; use Python 3.10+ features
- All type hints required; public functions need docstrings (Google style)
- No `print()` — use `click.echo()` or `logging`
- Use `pathlib.Path`, not `os.path`
