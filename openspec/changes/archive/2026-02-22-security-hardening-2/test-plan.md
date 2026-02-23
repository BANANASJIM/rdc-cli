# Test Plan: security-hardening-2

## Scope
- In scope: file permission bits on session file and session dir, atexit/SIGTERM temp dir cleanup, daemon exception logging
- Out of scope: token confidentiality end-to-end, encrypted storage, network interception

## Test Matrix
- Unit: `tests/test_session_state.py` — permission bits, atexit registration, logging output
- Unit: `tests/test_daemon_server.py` — exception branch logs and returns correct response
- Integration: none required (all fixes are testable with mocks and `tmp_path`)

## Cases

### P0-SEC-1 — session file permissions
- `save_session` on a fresh path: assert `stat(session_file).st_mode & 0o777 == 0o600`
- `save_session` on a fresh path: assert `stat(session_dir).st_mode & 0o777 == 0o700`
- `save_session` with umask 0o022 set explicitly: permissions are still `0o600` / `0o700` (umask not respected)
- `save_session` with an existing file of wrong permissions (0o644): file is overwritten and permissions are corrected to `0o600`
- `load_session` still reads back the written data correctly after the fix

### P1-SEC-3 — temp dir cleanup on unclean exit
- `_load_replay` with `--no-replay` skipped (mocked): after `mkdtemp`, atexit registry contains `_cleanup_temp` (inspect `atexit._atexit` or use `unittest.mock.patch("atexit.register")` and assert called with the cleanup function)
- Calling the atexit callback directly: temp dir is deleted if it exists, no error if already removed
- SIGTERM handler in `main()`: patch `signal.signal`; assert it is called with `signal.SIGTERM` and a handler that calls `sys.exit(0)`

### P1-OBS-1 — handler exception logging
- Inject a handler raising `RuntimeError("boom")` into `_DISPATCH`; call `_process_request(request, state)` directly: assert `logging.getLogger("rdc.daemon").exception` was called with the method name in the message
- `_process_request` returns response dict with `error.code == -32603` (existing shape unchanged)
- `_process_request` returns `running=True` for a non-shutdown method after swallowed exception
