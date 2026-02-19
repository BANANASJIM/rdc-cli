# Test Plan: phase1-pipeline-shader

## Goals
Validate pipeline/shader read-only queries across service, daemon, and CLI layers.

## Test Layers
- Unit:
  - query_service pipeline/shader extraction helpers
  - formatter output normalization
- Mock daemon:
  - JSON-RPC methods `pipeline`, `bindings`, `shader`, `shaders`
- CLI:
  - command registration
  - no-session and invalid-eid handling

## Happy Path Cases
1. `pipeline` returns stage sections and selected section details.
2. `bindings` returns resources grouped by stage and slot.
3. `shader` returns selected stage metadata for current or provided eid.
4. `shaders` returns deduplicated shader inventory for capture.

## Failure Cases
1. No active session -> consistent error + nonzero exit.
2. Invalid eid -> not found response.
3. Stage not present at eid -> clear empty/not-found semantics.
4. Replay unavailable (`--no-replay` / missing renderdoc) -> graceful error.

## Assertions
- TSV columns stable and documented
- JSON field names stable for automation
- Exit code conventions unchanged

## Regression Risks
- Existing `events/draws/draw/event` queries
- Adapter version-gated calls for root actions and pipeline access
