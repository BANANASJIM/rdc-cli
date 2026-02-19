# Test Plan: phase1-draws-events

## Scope
- In scope: `rdc info`, `rdc stats`, `rdc events`, `rdc draws`, `rdc event`,
  `rdc draw` commands and their daemon methods.
- Out of scope: GPU integration tests; other Phase 1 commands.

## Test Matrix
- Unit: action tree traversal helpers, stats aggregation logic, TSV output
  formatting for each command.
- Mock: daemon methods with MockReplayController returning canned action
  trees and structured data. CLI end-to-end with mocked daemon.
- Integration: deferred to GPU environment.
- Regression: N/A (first implementation).

## Cases

### rdc info — Happy path
- Returns capture path, API, GPU, driver, resolution, frame number.
- Returns event count, draw call breakdown (indexed/non-indexed/dispatches).
- Returns resource summary by type and memory totals.
- Returns render pass count.

### rdc stats — Happy path
- Per-pass table: PASS, DRAWS, DISPATCHES, TRIANGLES, RT_W, RT_H, ATTACHMENTS.
- Top draws by triangle count (TSV).
- Largest resources by byte size (TSV).
- Footer line to stderr.
- `--no-header` omits headers.

### rdc events — Happy path
- TSV columns: EID, TYPE, NAME.
- `--type draw` filters to draw calls only.
- `--filter Shadow` filters by name glob.
- `--limit 10` truncates output.
- `--range 100:200` filters by EID range.

### rdc draws — Happy path
- TSV columns: EID, TYPE, TRIANGLES, INSTANCES, PASS, MARKER.
- `--pass GBuffer` filters by pass name.
- `--sort triangles` sorts descending.
- `--limit 5` truncates.
- Footer with summary counts to stderr.
- `-q` outputs only EID column.

### rdc event <eid> — Happy path
- Key:value block: EID, API Call, Parameters (indented), Duration.
- Resolves from structured data chunk index.

### rdc draw [eid] — Happy path
- Key:value block matching output format spec: Event, Type, Marker,
  Triangles, Instances, Topology, Viewport, Scissor, Vertex Buffers,
  Index Buffer, Render Targets, Shaders, Descriptor Bindings, Rasterizer,
  Depth/Stencil, Blend.
- Without eid argument: uses current session eid.
- With eid argument: uses specified eid.

### Error paths
- `rdc info` with no active session → error, exit 1.
- `rdc event 99999` with out-of-range EID → error -32002, exit 1.
- `rdc draw` with no active session → error, exit 1.
- `rdc draws --pass NonExistent` → empty output, exit 0.

### Edge cases
- Capture with zero draw calls → info shows 0, draws outputs header only.
- Capture with no markers → MARKER column shows `-`.
- Event with no parameters → Parameters section empty.

## Assertions
- TSV output parseable by `awk -F'\t'`.
- All numeric columns are raw integers (no human formatting).
- Footer/summary lines go to stderr only.
- Exit code 0 on success, 1 on error.
- `--json` produces valid JSON; `--jsonl` one JSON object per line.
- Output matches 设计/输出格式示例 exactly.

## Risks & Rollback
- Depends on phase1-daemon-replay being merged first.
- Mock action tree must cover: nested markers, multiple passes, mixed
  action types (draw/dispatch/clear/copy).
- Rollback: revert branch; daemon-replay layer unaffected.
