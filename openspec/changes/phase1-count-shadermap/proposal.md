# Proposal: phase1-count-shadermap

## Goal

Implement Unix-tool-friendly helper commands `rdc count` and `rdc shader-map`
for composable pipelines. These output minimal, machine-readable data designed
for `wc`, `join`, `xargs`, and shell arithmetic.

## Scope

### New CLI commands
- `rdc count <what> [--filter]` — output a single integer to stdout.
  Supported targets: `draws`, `events`, `resources`, `triangles`, `passes`,
  `dispatches`, `clears`.
  Optional `--pass NAME` filter for draws/triangles.
- `rdc shader-map` — TSV mapping of EID to shader ResourceId for every draw
  call, enabling `join` with other TSV outputs.

### New daemon JSON-RPC methods
- `count` — accepts `what` + optional filter params, returns `{"value": int}`.
- `shader_map` — returns list of `{eid, vs, hs, ds, gs, ps, cs}` rows.

### New source files
- `src/rdc/commands/unix_helpers.py` — count, shader-map commands.

### Output format
- `rdc count`: single integer on stdout, nothing else (no header, no footer).
- `rdc shader-map`: TSV with header: `EID\tVS\tHS\tDS\tGS\tPS\tCS`.
  Empty stages show `-`. Supports `--no-header`.

## Non-goals
- `rdc state-changes` (Phase 2).
- `rdc find` (Phase 2).

## Key design references (Obsidian)
- 设计/命令总览 — rdc count, rdc shader-map specs
- 调研/调研-Unix工具集成 — pipeline recipes, format requirements
- 设计/输出格式示例 — (not explicitly shown; follows TSV conventions)
- 设计/API 实现映射 — action tree traversal, GetShader per stage
