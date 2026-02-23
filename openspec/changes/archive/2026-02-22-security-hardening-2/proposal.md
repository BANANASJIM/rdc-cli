# Proposal: security-hardening-2

## Goal
Fix three security issues: session files written world-readable (P0), GPU temp data leaked on unclean daemon exit (P1), and handler exceptions silently swallowed with no log (P1).

## Scope
- **P0-SEC-1** `src/rdc/session_state.py:59-62` — `save_session` creates `~/.rdc/sessions/<name>.json` via `Path.write_text()`, which inherits the process umask (typically 0644). The file holds the daemon auth token in plaintext. Fix: (1) create parent dir then explicitly `os.chmod(dir, 0o700)` to override umask; (2) write the file through `os.open(..., os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)` so file permissions are set atomically on creation, independent of umask. `Path.mkdir(mode=0o700)` alone is insufficient because `mode` is subject to umask on Linux.
- **P1-SEC-3** `src/rdc/daemon_server.py:174` — `_load_replay` creates a temp dir under `/tmp/` that is only cleaned by the graceful `shutdown` RPC handler. SIGKILL, crashes, and idle-timeout expiry all leave GPU data on disk. Fix: register `atexit.register(_cleanup_temp)` immediately after `mkdtemp`, and install a `signal.signal(signal.SIGTERM, ...)` handler in `main()` that calls `sys.exit(0)` (which triggers atexit).
- **P1-OBS-1** `src/rdc/daemon_server.py:241-249` — the bare `except Exception` in `run_server` returns a generic error response without logging the traceback, making production failures invisible. Fix: extract the per-request try/except block into a new `_process_request(request: dict, state: DaemonState) -> tuple[dict, bool]` helper (replaces the inline try/except in `run_server`). This makes the exception path unit-testable without touching the socket event loop. The helper calls `logging.getLogger("rdc.daemon").exception(...)` before returning the fallback response.

## Non-goals
- Token rotation or encrypted session files
- Secure memory wiping of the token at process exit
- Changing the temp dir location away from `/tmp/`
- Changing the JSON-RPC error codes or response shape
