# Tasks: security-hardening-2

## Test-first tasks
- [ ] `tests/test_session_state.py`: test `save_session` sets session file mode to `0o600`
- [ ] `tests/test_session_state.py`: test `save_session` sets session dir mode to `0o700`
- [ ] `tests/test_session_state.py`: test `save_session` with umask `0o022` still produces `0o600` / `0o700`
- [ ] `tests/test_session_state.py`: test `save_session` overwrites existing `0o644` file and corrects to `0o600`
- [ ] `tests/test_session_state.py`: test `load_session` reads back data correctly after permission fix
- [ ] `tests/test_daemon_server.py`: test `_load_replay` registers atexit cleanup after `mkdtemp` (mock `atexit.register`)
- [ ] `tests/test_daemon_server.py`: test atexit cleanup callback deletes temp dir; no error if already gone
- [ ] `tests/test_daemon_server.py`: test `main()` installs `SIGTERM` handler that calls `sys.exit(0)` (mock `signal.signal`)
- [ ] `tests/test_daemon_server.py`: test `_process_request` with injected raising handler — `logger.exception` called with method name
- [ ] `tests/test_daemon_server.py`: test `_process_request` error response shape unchanged (`-32603`)
- [ ] `tests/test_daemon_server.py`: test `_process_request` returns `running=True` for non-shutdown on exception

## Implementation tasks
- [ ] `src/rdc/session_state.py:59-62` — replace `path.parent.mkdir(parents=True, exist_ok=True)` with a version that passes `mode=0o700`; replace `path.write_text(...)` with an `os.open` / `os.fdopen` write that creates the file with mode `0o600`, overriding umask via `os.umask` or by using `os.open` flags directly
- [ ] `src/rdc/daemon_server.py:174` — after `mkdtemp`, define `_cleanup_temp` closure (or module-level function) that `shutil.rmtree`s `state.temp_dir` if it exists, then call `atexit.register(_cleanup_temp)`; add `import atexit` and `import shutil` at top of file
- [ ] `src/rdc/daemon_server.py:main()` — add `import signal` (already may be imported); install `signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))` so atexit fires on SIGTERM
- [ ] `src/rdc/daemon_server.py:241-249` — extract the try/except block into `_process_request(request: dict, state: DaemonState) -> tuple[dict, bool]`; inside the except block add `logging.getLogger("rdc.daemon").exception("unhandled exception in handler: %s", request.get("method", ""))` before returning the fallback response; `run_server` calls `_process_request`; add `import logging` at top if not present
- [ ] Run `pixi run lint && pixi run test` — zero failures
