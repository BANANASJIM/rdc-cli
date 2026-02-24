# Tasks: Fix Daemon Lifecycle Bugs B21 + B22 + B23 + B25

## Task 1: Add connection timeout in daemon_server.py (B21)

- **Files**: `src/rdc/daemon_server.py`
- **Changes**:
  - After `conn, addr = server.accept()`, call `conn.settimeout(10.0)`.
  - In the per-connection error handler, add an explicit `except TimeoutError` branch before the existing `except (OSError, ValueError)` clause:
    ```python
    except TimeoutError:
        log.warning("client connected but sent no data within 10s, closing")
        conn.close()
        continue
    ```
  - This prevents a misbehaving or scanning client from blocking the accept loop indefinitely.
- **Depends on**: nothing
- **Estimated complexity**: S

## Task 2: Add port retry loop in open_session() (B22)

- **Files**: `src/rdc/services/session_service.py`
- **Changes**:
  - Define `MAX_PORT_RETRIES = 3` as a module-level constant.
  - Wrap the `pick_port()` + `_start_daemon()` sequence inside `open_session()` with a retry loop:
    ```python
    for attempt in range(MAX_PORT_RETRIES):
        port = pick_port()
        try:
            _start_daemon(port, ...)
            break
        except PortConflictError:
            if attempt == MAX_PORT_RETRIES - 1:
                raise
            log.warning("port %d taken, retrying (%d/%d)", port, attempt + 1, MAX_PORT_RETRIES)
    ```
  - The daemon's existing health-check loop already detects bind failures (non-zero exit); the retry wraps that detection.
  - On the first successful attempt (the common path), behavior is identical to before.
- **Depends on**: nothing
- **Estimated complexity**: S

## Task 3: Append no-replay flag to open_session() success message (B23)

- **Files**: `src/rdc/services/session_service.py`
- **Changes**:
  - In `open_session()`, after constructing the success message, check `_renderdoc_available()`:
    ```python
    if not _renderdoc_available():
        message += " (no-replay mode: renderdoc unavailable)"
    ```
  - The existing `_renderdoc_available()` call that gates `--no-replay` flag passing can be reused; do not call it a second time if it is already evaluated earlier in the function.
- **Depends on**: nothing
- **Estimated complexity**: S

## Task 4: Add stderr warning in open_cmd for no-replay mode (B23)

- **Files**: `src/rdc/commands/session.py`
- **Changes**:
  - In the `open_cmd` Click command, after printing the success message, check for the no-replay suffix:
    ```python
    click.echo(result)
    if "no-replay mode" in result:
        click.echo("warning: session started in no-replay mode — renderdoc is unavailable", err=True)
    ```
  - The warning is emitted to stderr so it is visible even when stdout is piped or redirected.
  - Exit code remains 0 — no-replay is a degraded mode, not an error.
- **Depends on**: Task 3
- **Estimated complexity**: S

## Task 5: Add os.kill fallback in close_session() except block (B25)

- **Files**: `src/rdc/services/session_service.py`
- **Changes**:
  - Add `import signal` to the imports at the top of the file (if not already present).
  - In `close_session()`, replace the bare `pass` in the `except` block with:
    ```python
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
            log.warning("shutdown RPC failed; sent SIGTERM to daemon pid %d", pid)
        except ProcessLookupError:
            pass  # already gone
    ```
  - `os` is already imported; only `signal` needs to be added.
  - `ProcessLookupError` guard handles the race where the daemon exits between the failed RPC and the `os.kill` call.
- **Depends on**: nothing
- **Estimated complexity**: S

## Task 6: Write tests for B21 (connection timeout)

- **Files**: `tests/unit/test_daemon_server_unit.py`
- **Changes**:
  - **`test_run_server_sets_connection_timeout`**: mock `server.accept()` to return a mock connection; verify `mock_conn.settimeout` is called with `10.0`.
  - **`test_recv_line_raises_timeout_on_idle_connection`**: create a real socket pair via `socket.socketpair()`; set `settimeout(0.05)` on the read end; call `recv_line(read_end)` with no data written; assert `TimeoutError` is raised.
- **Depends on**: Task 1
- **Estimated complexity**: S

## Task 7: Write tests for B22 (port retry)

- **Files**: `tests/unit/test_session_service.py`
- **Changes**:
  - **`test_open_session_retries_on_port_conflict`**: patch `pick_port` to return successive ports; patch `_start_daemon` to raise `PortConflictError` on first two calls and succeed on third; assert `pick_port` and `_start_daemon` each called 3 times; assert no exception raised.
  - **`test_open_session_all_retries_fail`**: patch `_start_daemon` to always raise; assert exception raised after exactly 3 attempts.
  - **`test_open_session_first_attempt_succeeds`** (regression): patch `_start_daemon` to succeed immediately; assert `pick_port` called exactly once.
- **Depends on**: Task 2
- **Estimated complexity**: S

## Task 8: Write test for B23 (no-replay warning)

- **Files**: `tests/unit/test_session_commands.py`
- **Changes**:
  - **`test_open_no_replay_mode_warning`**: patch `open_session` to return `"session opened on port 12345 (no-replay mode: renderdoc unavailable)"`; invoke `["open", "test.rdc"]` via `CliRunner(mix_stderr=False)`; assert stdout contains `"no-replay mode"`; assert stderr contains `"warning"` and `"no-replay"`; assert `exit_code == 0`.
  - **`test_open_session_full_replay_no_warning`** (regression): patch `open_session` to return a plain success message; assert stderr does NOT contain `"no-replay"` or `"warning"`.
- **Depends on**: Tasks 3 and 4
- **Estimated complexity**: S

## Task 9: Write test for B25 (SIGTERM fallback)

- **Files**: `tests/unit/test_session_service.py`
- **Changes**:
  - **`test_close_session_fallback_kill_on_shutdown_error`**: patch `send_request` to raise `OSError("connection refused")`; patch `os.kill` to be a mock; set up a mock session with known `pid=99999`; call `close_session(session_token)`; assert `os.kill` called with `(99999, signal.SIGTERM)`; assert no exception raised.
  - **`test_close_session_graceful_shutdown_no_kill`** (regression): patch `send_request` to succeed; assert `os.kill` was NOT called.
- **Depends on**: Task 5
- **Estimated complexity**: S

## Task 10: Run lint and tests

- **Files**: none
- **Changes**:
  - Run `pixi run lint && pixi run test`.
  - Zero failures required before the PR can be submitted.
  - Fix any mypy or ruff issues introduced by the changes.
- **Depends on**: Tasks 1–9
- **Estimated complexity**: S

---

## Parallelism

All implementation tasks are independent of each other and can run in parallel:

- **Task 1** (B21 daemon timeout) touches only `daemon_server.py`.
- **Tasks 2, 3, 5** (B22 retry, B23 message, B25 fallback kill) all touch `session_service.py`. If assigned to separate agents, they must coordinate on this file to avoid conflicts. Recommended split: single agent handles Tasks 2+3+5 together since they are all in `session_service.py`.
- **Task 4** (B23 warning) touches only `session.py` and depends on Task 3 being complete first.

Test tasks depend on their corresponding implementation tasks:

- **Task 6** depends on Task 1
- **Task 7** depends on Task 2
- **Task 8** depends on Tasks 3 and 4
- **Task 9** depends on Task 5

## Implementation order

1. **Phase A (parallel)**: Tasks 1, 2, 3, 5 — core implementation fixes
2. **Phase B**: Task 4 — depends on Task 3 (no-replay message must exist before warning check)
3. **Phase C (parallel)**: Tasks 6, 7, 8, 9 — test coverage (after Phase A+B complete)
4. **Verification**: Task 10 — `pixi run lint && pixi run test` — zero failures required
