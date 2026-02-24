# Test Plan: Fix Daemon Lifecycle Bugs B21 + B22 + B23 + B25

## B21: Connection timeout on idle client

### Root Cause Summary

`daemon_server.py` calls `server.accept()` then immediately reads from the connection with no timeout. A client that connects but never sends data blocks `recv_line` (and the entire accept loop) indefinitely. The fix adds `conn.settimeout(10.0)` after accept and catches `TimeoutError` to log a warning and continue.

### Unit tests — `tests/unit/test_daemon_server_unit.py`

**`test_run_server_sets_connection_timeout`**
- Inspect the source of `run_server` (or its inner `_handle_connection` helper) via `inspect.getsource` or by directly checking that `settimeout` is called on the accepted socket.
- Alternative: use `unittest.mock.patch("socket.socket")` to mock `server.accept()` returning a mock connection, then verify `mock_conn.settimeout.called` is `True` with argument `10.0`.
- Assert: `conn.settimeout(10.0)` is called exactly once per accepted connection.
- Assert: `TimeoutError` appears in the except clause (source inspection or coverage path check).

**`test_recv_line_raises_timeout_on_idle_connection`**
- Create a real socket pair using `socket.socketpair()`.
- Set `settimeout(0.05)` on the read end (very short timeout for test speed).
- Call `recv_line(read_end)` without writing anything to the write end.
- Assert: `TimeoutError` (or `socket.timeout`) is raised.
- This validates that the underlying `recv_line` propagates the socket's timeout correctly, which the daemon's `except TimeoutError` branch relies on.

---

## B22: Port retry on TOCTOU race

### Root Cause Summary

`pick_port()` binds to port 0 to discover a free port, then closes the socket. Between the close and the daemon's bind, another process can steal the port. The fix adds a retry loop (max 3 attempts) in `open_session()`.

### Unit tests — `tests/unit/test_session_service.py`

**`test_open_session_retries_on_port_conflict`**
- Patch `pick_port` to return successive ports `[50001, 50002, 50003]`.
- Patch `_start_daemon` (or the equivalent daemon-start helper) so that it raises `PortConflictError` (or the equivalent `OSError: Address already in use`) on the first two calls and succeeds on the third.
- Call `open_session(capture_path, ...)`.
- Assert: `pick_port` was called 3 times.
- Assert: `_start_daemon` was called 3 times.
- Assert: the function returns successfully (no exception raised).

**`test_open_session_all_retries_fail`**
- Patch `pick_port` to always return `50001`.
- Patch `_start_daemon` to always raise `PortConflictError`.
- Call `open_session(capture_path, ...)`.
- Assert: `PortConflictError` (or `OSError`) is raised after exactly 3 attempts.
- Assert: the error message contains information identifying the failure (port number or "Address already in use").

---

## B23: No-replay mode warning

### Root Cause Summary

When renderdoc is unavailable, `open_session()` starts the daemon in no-replay mode but returns a generic success message. The user does not know the session is limited. The fix appends `" (no-replay mode: renderdoc unavailable)"` to the success message and adds a `click.echo(..., err=True)` warning in the `open` command.

### Unit tests — `tests/unit/test_session_commands.py`

**`test_open_no_replay_mode_warning`**
- Patch `rdc.commands.session.open_session` to return `"session opened on port 12345 (no-replay mode: renderdoc unavailable)"`.
- Invoke `["open", "test.rdc"]` via `CliRunner(mix_stderr=False)`.
- Assert: `result.output` contains `"no-replay mode"` (the success message is echoed to stdout).
- Assert: `result.stderr` contains `"warning"` and `"no-replay"` (the explicit warning line is echoed to stderr).
- Assert: `result.exit_code == 0` (no-replay is not an error, just a degraded mode).

---

## B25: SIGTERM fallback on shutdown RPC failure

### Root Cause Summary

`close_session()` sends a `shutdown` JSON-RPC. If `send_request` raises, the `except` block does `pass` and the daemon process may still be running. The fix replaces `pass` with `os.kill(pid, signal.SIGTERM)`.

### Unit tests — `tests/unit/test_session_service.py`

**`test_close_session_fallback_kill_on_shutdown_error`**
- Patch `send_request` to raise `OSError("connection refused")`.
- Patch `os.kill` to be a mock (so no real process is killed).
- Set up a mock session with a known `pid` (e.g., `99999`).
- Call `close_session(session_token)`.
- Assert: `os.kill` was called with `(99999, signal.SIGTERM)`.
- Assert: no exception is raised from `close_session` (the fallback is handled internally).

---

## Regression tests

**`test_open_session_full_replay_no_warning`**
- Patch `_renderdoc_available` to return `True`.
- Invoke `["open", "test.rdc"]` via `CliRunner(mix_stderr=False)`.
- Assert: `result.stderr` does NOT contain `"no-replay"` or `"warning"`.
- Ensures the B23 fix does not produce false warnings when renderdoc is available.

**`test_close_session_graceful_shutdown_no_kill`**
- Patch `send_request` to succeed (return normally).
- Patch `os.kill` to be a mock.
- Call `close_session(session_token)`.
- Assert: `os.kill` was NOT called.
- Ensures the B25 fallback is not triggered on the happy path.

**`test_open_session_first_attempt_succeeds`**
- Patch `pick_port` to return `50001` once.
- Patch `_start_daemon` to succeed immediately.
- Call `open_session(capture_path, ...)`.
- Assert: `pick_port` was called exactly once (no spurious retries on success).
- Ensures the B22 retry loop does not change behavior on the common path.

---

## Test matrix

| Test | Type | File | Covers |
|------|------|------|--------|
| `test_run_server_sets_connection_timeout` | unit | `test_daemon_server_unit.py` | B21 |
| `test_recv_line_raises_timeout_on_idle_connection` | unit | `test_daemon_server_unit.py` | B21 |
| `test_open_session_retries_on_port_conflict` | unit | `test_session_service.py` | B22 |
| `test_open_session_all_retries_fail` | unit | `test_session_service.py` | B22 |
| `test_open_no_replay_mode_warning` | unit | `test_session_commands.py` | B23 |
| `test_close_session_fallback_kill_on_shutdown_error` | unit | `test_session_service.py` | B25 |
| `test_open_session_full_replay_no_warning` | regression | `test_session_commands.py` | B23 |
| `test_close_session_graceful_shutdown_no_kill` | regression | `test_session_service.py` | B25 |
| `test_open_session_first_attempt_succeeds` | regression | `test_session_service.py` | B22 |
