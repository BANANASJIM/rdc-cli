# Test Plan: Robustness Hardening Fix Batch

## Overview

This test plan covers unit and integration tests for a batch of robustness fixes across
the daemon server, transport layer, CLI client, and utility modules. No GPU is required
for any of these tests.

Estimated new test cases: ~31
Target: maintain or improve 95% coverage.

---

## New Test Files

### `tests/unit/test_transport_robustness.py`

Covers Groups A3 and A4: `recv_line` memory limit and `sendall` disconnect handling.

**Tests:**

| Test name | Description |
|-----------|-------------|
| `test_recv_line_exceeds_max_bytes_raises` | Input longer than `max_bytes` → `ValueError` raised |
| `test_recv_line_normal_line_passes` | Line well within limit → returned without error |
| `test_recv_line_exact_at_limit_passes` | Line length == `max_bytes` → returned without error |
| `test_sendall_broken_pipe_does_not_crash` | Mock socket raises `BrokenPipeError` on `sendall` → daemon handles gracefully (no uncaught exception) |

---

## Test Updates

### `tests/unit/test_shader_edit_handlers.py` — Group A1 + A2 (shader handlers)

**A1 — Shutdown resource cleanup:**

| Test name | Description |
|-----------|-------------|
| `TestShutdownCleanup::test_shutdown_frees_built_shaders` | `_handle_shutdown` calls `FreeTargetResource` for every entry in `state.built_shaders` |
| `TestShutdownCleanup::test_shutdown_removes_replacements` | `_handle_shutdown` calls `RemoveReplacement` for every entry in `state.shader_replacements` |
| `TestShutdownCleanup::test_shutdown_with_no_resources_succeeds` | Shutdown when both dicts are empty → no error, result `ok` is True |

**A2 — Missing params → -32602 (shader handlers):**

| Test name | Description |
|-----------|-------------|
| `TestShaderBuildMissingParams::test_missing_source_returns_32602` | `shader_build` with no `source` → error code `-32602`, descriptive message |
| `TestShaderReplaceMissingParams::test_missing_shader_id_returns_32602` | `shader_replace` with no `shader_id` → `-32602` |
| `TestShaderReplaceMissingParams::test_missing_eid_returns_32602` | `shader_replace` with no `eid` → `-32602` |
| `TestShaderRestoreMissingParams::test_missing_eid_returns_32602` | `shader_restore` with no `eid` → `-32602` |

---

### `tests/unit/test_debug_handlers.py` — Group A2 (debug handlers)

**A2 — Missing params → -32602:**

| Test name | Description |
|-----------|-------------|
| `TestDebugPixelMissingParams::test_missing_eid_returns_32602` | `debug_pixel` with no `eid` → `-32602` |
| `TestDebugPixelMissingParams::test_missing_x_returns_32602` | `debug_pixel` with no `x` → `-32602` |
| `TestDebugPixelMissingParams::test_missing_y_returns_32602` | `debug_pixel` with no `y` → `-32602` |
| `TestDebugVertexMissingParams::test_missing_eid_returns_32602` | `debug_vertex` with no `eid` → `-32602` |
| `TestDebugVertexMissingParams::test_missing_vtx_id_returns_32602` | `debug_vertex` with no `vtx_id` → `-32602` |

---

### `tests/unit/test_pixel_history_daemon.py` — Group A2 (pixel_history handler)

**A2 — Missing params → -32602:**

| Test name | Description |
|-----------|-------------|
| `TestPixelHistoryMissingParams::test_missing_x_returns_32602` | `pixel_history` with no `x` → `-32602` |
| `TestPixelHistoryMissingParams::test_missing_y_returns_32602` | `pixel_history` with no `y` → `-32602` |

---

### `tests/unit/test_script_handler.py` — Group A2 (script handler)

**A2 — Missing params → -32602:**

| Test name | Description |
|-----------|-------------|
| `TestScriptMissingParams::test_missing_path_returns_32602` | `script` with no `path` → `-32602`, message mentions `path` |

---

### `tests/unit/test_daemon_server_unit.py` — Group A5

**A5 — Shutdown exception override:**

| Test name | Description |
|-----------|-------------|
| `TestHandleRequest::test_shutdown_exception_still_sets_running_false` | If `_handle_request` raises during `shutdown` method dispatch, `running` is forced to `False` |
| `TestHandleRequest::test_non_shutdown_exception_propagates` | If `_handle_request` raises on a non-shutdown method, the exception propagates normally (running is not suppressed to False) |

---

### `tests/unit/test_session_state.py` — Group C2 and C3

**C2 — `is_pid_alive` PID recycling guard:**

| Test name | Description |
|-----------|-------------|
| `test_is_pid_alive_mismatched_cmdline_returns_false` | `/proc/{pid}/cmdline` exists but does not contain daemon signature → `False` |
| `test_is_pid_alive_matching_cmdline_returns_true` | `/proc/{pid}/cmdline` contains daemon signature → `True` |
| `test_is_pid_alive_no_proc_fs_falls_back_to_signal` | Monkeypatch away `/proc` existence → falls back to `os.kill` check, no crash |

**C3 — `load_session` corrupt JSON:**

| Test name | Description |
|-----------|-------------|
| `test_load_session_invalid_json_returns_none` | File contains invalid JSON → returns `None` |
| `test_load_session_missing_required_keys_returns_none` | Valid JSON but missing required keys (e.g., `host`, `port`) → returns `None` |
| `test_load_session_corrupt_file_is_deleted` | Corrupt session file → file is removed from disk after detection |
| `test_load_session_valid_file_still_works` | Normal well-formed session file → loaded correctly (regression) |

---

### `tests/unit/test_pipeline_commands.py` / `tests/unit/test_resources_commands.py` / `tests/unit/test_unix_helpers_commands.py` — Group B2

**B2 — CLI `call()` connection error handling:**

Add one test to each of the three files (or to a single shared helper test if a `_helpers`
test module exists):

| Test name | File | Description |
|-----------|------|-------------|
| `test_pipeline_connection_refused_exits_cleanly` | `test_pipeline_commands.py` | Monkeypatch `send_request` to raise `ConnectionRefusedError` → `exit_code != 0`, user-friendly message in output |
| `test_resources_connection_refused_exits_cleanly` | `test_resources_commands.py` | Same pattern for `resources` command |
| `test_unix_helpers_connection_refused_exits_cleanly` | `test_unix_helpers_commands.py` | Same pattern for unix-helper commands |

---

## Coverage Expectations

| Area | New cases | Notes |
|------|-----------|-------|
| A1 Shutdown cleanup | 3 | Covers both built_shaders and shader_replacements dicts |
| A2 Missing params | 12 | One test per required param across all affected handlers |
| A3 recv_line limit | 3 | Under, at, and over limit |
| A4 sendall disconnect | 1 | BrokenPipeError swallowed cleanly |
| A5 Shutdown exception | 2 | running=False forced; non-shutdown propagates |
| B2 Connection errors | 3 | One per affected CLI module |
| C2 PID recycling | 3 | Mismatch, match, no /proc |
| C3 Corrupt JSON | 4 | Invalid JSON, missing keys, file deleted, regression |
| **Total** | **~31** | |

- B1 (dedup) and C1 (diff elif) require no new tests — existing suites are sufficient.
- All new tests must pass with `pixi run test` (no GPU).
- Existing GPU tests in `tests/integration/test_daemon_handlers_real.py` must continue to pass.
- Overall coverage target: maintain >= 95%.

---

## Test Matrix

| Dimension | Value |
|-----------|-------|
| Python | 3.10, 3.12 (pixi matrix) |
| Platform | Linux (primary); no Windows/macOS required |
| GPU | Not required; all tests are unit/mock-based |
| CI | Standard `pixi run lint && pixi run test` |

### Fixtures and helpers

- Daemon handler tests: use `DaemonState` + `RenderDocAdapter` with `MockReplayController` from `tests/mocks/mock_renderdoc.py`.
- Transport tests: use raw mock socket objects (`unittest.mock.MagicMock` with `recv`/`sendall` side effects).
- CLI tests: use `click.testing.CliRunner` with `monkeypatch` on `load_session` and `send_request`.
- Session state tests: use `tmp_path` fixture and `monkeypatch` for filesystem isolation.
