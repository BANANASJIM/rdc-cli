# Tasks: phase1-daemon-replay

## Test-first tasks
- [x] Extend mock renderdoc module with MockReplayController, MockCaptureFile,
      MockPipeState, MockStructuredFile, MockActionDescription.
- [x] Add unit tests for adapter `RenderDocAPI` wrapper (version detection,
      `get_root_actions` shim, `get_api_properties`).
- [x] Add unit tests for TSV formatter (header, no-header, escape rules,
      empty field as `-`).
- [x] Add unit tests for global output option parsing (--no-header, --json,
      --jsonl, --quiet, --columns, --sort, --limit, --range).
- [x] Add mock tests for daemon replay startup sequence (init → open file →
      open capture → hold controller).
- [x] Add mock tests for `goto` with SetFrameEvent caching (skip redundant,
      incremental replay).
- [x] Add mock tests for `status` returning live capture metadata.
- [x] Add mock tests for `shutdown` sequence (controller.Shutdown →
      cap.Shutdown, no ShutdownReplay).
- [x] Add mock tests for error paths (import failure, OpenCapture failure,
      EID out of range).

## Implementation tasks
- [x] Extend `src/rdc/adapter.py` with `RenderDocAPI` class wrapping
      ReplayController (version shims for GetRootActions etc.).
- [x] Create `src/rdc/formatters/__init__.py`.
- [x] Create `src/rdc/formatters/tsv.py` with TSV output helpers.
- [x] Create `src/rdc/formatters/json_fmt.py` with JSON/JSONL helpers.
- [x] Add global output options as Click decorators/shared options.
- [x] Update `DaemonState` to hold controller, cap, structured_file references.
- [x] Update daemon server startup to call renderdoc lifecycle
      (InitialiseReplay → OpenCaptureFile → OpenCapture).
- [x] Implement SetFrameEvent caching in daemon (track current_eid, skip
      redundant calls).
- [x] Update `goto` handler to call real SetFrameEvent with EID validation.
- [x] Update `status` handler to return live metadata from controller.
- [x] Update `shutdown` handler to call controller.Shutdown() + cap.Shutdown()
      then sys.exit(0).
- [x] Ensure `make check` passes (ruff + mypy strict + pytest ≥ 80%).
