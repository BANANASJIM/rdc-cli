# Test Plan: phase1-daemon-replay

## Scope
- In scope: daemon loads renderdoc (mocked), holds ReplayController, handles
  goto with real SetFrameEvent, returns live status, shuts down cleanly.
  Formatter utilities and global output option parsing.
- Out of scope: specific query commands; GPU integration tests.

## Test Matrix
- Unit: adapter `RenderDocAPI` wrapper, TSV formatter, global option parsing.
- Mock: daemon startup with mock renderdoc module, SetFrameEvent caching,
  status with live metadata, shutdown sequence.
- Integration: deferred to GPU environment (not required for PR merge).

## Cases

### Happy path
- Daemon starts, loads mock capture, `ping` succeeds.
- `status` returns capture path, API name, event count, current_eid.
- `goto 142` calls `SetFrameEvent(142, True)` on mock controller.
- `goto 142` again skips redundant `SetFrameEvent` (cache hit).
- `goto 200` after `goto 142` calls `SetFrameEvent(200, True)` (incremental).
- `shutdown` calls `controller.Shutdown()` then `cap.Shutdown()`.
- TSV formatter produces tab-separated output with header row.
- TSV formatter respects `--no-header`.

### Error path
- Daemon fails to import renderdoc → exit with clear error message.
- `OpenCaptureFile` / `OpenCapture` fails → daemon exits, CLI reports error.
- `SetFrameEvent` with out-of-range EID → JSON-RPC error -32002.
- Invalid token still rejected (existing behavior preserved).

### Edge cases
- Capture with zero draw calls (valid but empty).
- `goto 0` (first event, valid).
- Very large EID at boundary of event count.

## Assertions
- `status` result includes keys: capture, api, gpu, driver, event_count,
  current_eid, opened_at.
- `goto` with invalid EID returns error code -32002.
- `shutdown` does NOT call `rd.ShutdownReplay()`.
- TSV output uses `\t` separator, `\n` line ending, `-` for empty fields.
- All existing Phase 0 tests continue to pass.

## Risks & Rollback
- Mock renderdoc module must be extended to cover ReplayController,
  PipeState, CaptureFile, StructuredFile.
- Rollback: revert branch; Phase 0 skeleton remains functional.
