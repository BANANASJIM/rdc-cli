# Tasks: phase1-daemon-replay

## Test-first tasks
- [ ] Extend mock renderdoc module with MockReplayController, MockCaptureFile,
      MockPipeState, MockStructuredFile, MockActionDescription.
- [ ] Add unit tests for adapter `RenderDocAPI` wrapper (version detection,
      `get_root_actions` shim, `get_api_properties`).
- [ ] Add unit tests for TSV formatter (header, no-header, escape rules,
      empty field as `-`).
- [ ] Add unit tests for global output option parsing (--no-header, --json,
      --jsonl, --quiet, --columns, --sort, --limit, --range).
- [ ] Add mock tests for daemon replay startup sequence (init → open file →
      open capture → hold controller).
- [ ] Add mock tests for `goto` with SetFrameEvent caching (skip redundant,
      incremental replay).
- [ ] Add mock tests for `status` returning live capture metadata.
- [ ] Add mock tests for `shutdown` sequence (controller.Shutdown →
      cap.Shutdown, no ShutdownReplay).
- [ ] Add mock tests for error paths (import failure, OpenCapture failure,
      EID out of range).

## Implementation tasks
- [ ] Extend `src/rdc/adapter.py` with `RenderDocAPI` class wrapping
      ReplayController (version shims for GetRootActions etc.).
- [ ] Create `src/rdc/formatters/__init__.py`.
- [ ] Create `src/rdc/formatters/tsv.py` with TSV output helpers.
- [ ] Create `src/rdc/formatters/json_fmt.py` with JSON/JSONL helpers.
- [ ] Add global output options as Click decorators/shared options.
- [ ] Update `DaemonState` to hold controller, cap, structured_file references.
- [ ] Update daemon server startup to call renderdoc lifecycle
      (InitialiseReplay → OpenCaptureFile → OpenCapture).
- [ ] Implement SetFrameEvent caching in daemon (track current_eid, skip
      redundant calls).
- [ ] Update `goto` handler to call real SetFrameEvent with EID validation.
- [ ] Update `status` handler to return live metadata from controller.
- [ ] Update `shutdown` handler to call controller.Shutdown() + cap.Shutdown()
      then sys.exit(0).
- [ ] Ensure `make check` passes (ruff + mypy strict + pytest ≥ 80%).
