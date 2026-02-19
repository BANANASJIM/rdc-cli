# Proposal: phase1-draws-events

## Goal

Implement the Week 4 query commands that expose capture-level overview and
event/draw-call browsing: `rdc info`, `rdc stats`, `rdc events`, `rdc draws`,
`rdc event <eid>`, `rdc draw [eid]`.

These are the first user-facing commands that read real data from the
ReplayController via the daemon.

## Scope

### New CLI commands
- `rdc info` — capture metadata (API, GPU, resolution, event/resource counts).
- `rdc stats` — per-pass breakdown + top draws + largest resources.
- `rdc events [--type TYPE] [--filter PATTERN]` — full event list (TSV).
- `rdc draws [--pass NAME] [--sort FIELD] [--limit N]` — draw call list (TSV).
- `rdc event <eid>` — single API call detail (key:value block).
- `rdc draw [eid]` — draw call detail (key:value block with bindings,
  shaders, render targets).

### New daemon JSON-RPC methods
- `info` — return capture metadata dict.
- `stats` — return per-pass stats + top draws + largest resources.
- `events` — return event list with optional type/filter.
- `draws` — return draw call list with optional pass/sort/limit.
- `event` — return single event detail from structured data.
- `draw` — return single draw call detail (requires SetFrameEvent).

### New source files (per Obsidian 技术栈 project structure)
- `src/rdc/commands/info.py` — info, stats commands.
- `src/rdc/commands/events.py` — events, draws, event, draw commands.
- `src/rdc/services/query_service.py` — business logic for querying action
  tree, aggregating stats, resolving structured data.

### Output format
- All list commands: TSV with header row. Footer/summary to stderr.
- Detail commands: `key: value` block format.
- Respect global options: `--no-header`, `--json`, `--jsonl`, `--quiet`,
  `--columns`, `--sort`, `--limit`, `--range`.
- Numbers are raw (e.g. `1200000` not `1.2M`) per design principles.

## Non-goals
- `rdc count` / `rdc shader-map` (separate parallel feature).
- Shader, pipeline, resource, pass commands (Week 5-6).
- Path addressing (`rdc cat/ls/tree`) (Week 5).

## Key design references (Obsidian)
- 设计/命令总览 — command signatures, arguments, options
- 设计/输出格式示例 — exact output format for each command
- 设计/API 实现映射 — GetRootActions, GetStructuredData, SetFrameEvent,
  GetPipelineState, GetResources, action tree traversal
- 设计/设计原则 — TSV rules, exit codes, error handling
