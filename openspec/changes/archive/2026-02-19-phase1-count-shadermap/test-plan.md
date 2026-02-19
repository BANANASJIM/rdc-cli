# Test Plan: phase1-count-shadermap

## Scope
- In scope: `rdc count` and `rdc shader-map` commands + daemon methods.
- Out of scope: GPU integration; other Phase 1 commands.

## Test Matrix
- Unit: count aggregation logic, shader-map collection logic.
- Mock: daemon methods with mock action tree + mock PipeState per draw.
- Integration: deferred to GPU environment.

## Cases

### rdc count — Happy path
- `rdc count draws` → single integer matching total draw calls.
- `rdc count triangles` → sum of all triangles across draws.
- `rdc count resources` → total resource count.
- `rdc count draws --pass GBuffer` → draws in that pass only.
- `rdc count triangles --pass Shadow` → triangles in that pass only.
- `rdc count dispatches` → dispatch count.
- `rdc count passes` → render pass count.
- Output is exactly one line containing a decimal integer, no whitespace prefix.

### rdc shader-map — Happy path
- TSV with header: EID, VS, HS, DS, GS, PS, CS.
- Each draw call has one row.
- Stages without a bound shader show `-`.
- `--no-header` omits header row.
- Output is joinable: `join -t$'\t' <(rdc draws) <(rdc shader-map)`.

### Error paths
- `rdc count` with no active session → error, exit 1.
- `rdc count unknown_target` → error message, exit 1.
- `rdc shader-map` with no active session → error, exit 1.

### Edge cases
- Capture with zero draws → `rdc count draws` outputs `0`.
- Capture with zero draws → `rdc shader-map` outputs header only (or nothing
  with `--no-header`).
- Compute-only dispatch → shader-map row has CS filled, others `-`.

## Assertions
- `rdc count` output is parseable by `$(...)` shell substitution.
- `rdc shader-map` TSV parseable by `awk -F'\t'`.
- Exit code 0 on success, 1 on error.

## Risks & Rollback
- Depends on phase1-daemon-replay (shared layer).
- `shader-map` requires iterating all draws with SetFrameEvent + GetShader
  per stage — performance concern on large captures. Document expected latency.
- Rollback: revert branch; no impact on other features.
