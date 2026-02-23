# Tasks: Robustness Hardening Fix Batch

## Agent Assignment

| Commit | Agent | Files | Sequential? |
|--------|-------|-------|-------------|
| 1 — fix(daemon): clean shader resources on shutdown | Worktree 1 | `handlers/core.py`, test | Yes (within WT1) |
| 2 — fix(daemon): return -32602 for missing required params | Worktree 1 | `handlers/debug.py`, `handlers/shader_edit.py`, `handlers/pixel.py`, `handlers/script.py`, tests | Yes (within WT1) |
| 3 — fix(daemon): harden transport and server loop | Worktree 1 | `_transport.py`, `daemon_server.py`, tests | Yes (within WT1) |
| 4 — fix(cli): deduplicate call helpers and add connection error handling | Worktree 2 | `commands/_helpers.py`, `commands/pipeline.py`, `commands/resources.py`, `commands/unix_helpers.py`, `commands/info.py` | Independent |
| 5 — fix: harden diff dispatch, session load, and PID check | Worktree 3 | `commands/diff.py`, `session_state.py`, tests | Independent |

Worktree agents 1, 2, and 3 run in parallel. Commits 1–3 are sequential within Worktree 1.

---

## Commit 1: `fix(daemon): clean shader resources on shutdown`

**Agent:** Worktree 1 (Daemon)

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/handlers/core.py` | Add shader cleanup logic to `_handle_shutdown`; call `RemoveReplacement` + `FreeTargetResource` for any tracked replacements before closing the capture |

### Tests Updated

| File | Change |
|------|--------|
| `tests/unit/test_shader_edit_handlers.py` | Add test verifying that shutdown triggers cleanup of active shader replacements; mock `RemoveReplacement` + `FreeTargetResource` and assert they are called |

---

## Commit 2: `fix(daemon): return -32602 for missing required params`

**Agent:** Worktree 1 (Daemon)

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/handlers/debug.py` | Validate `eid`, `x`, `y`, `vtx_id` before use; return `{"code": -32602, "message": "..."}` on missing/invalid |
| `src/rdc/handlers/shader_edit.py` | Validate `source`, `shader_id`, `eid` before use; return `-32602` on missing |
| `src/rdc/handlers/pixel.py` | Validate `x`, `y` before use; return `-32602` on missing |
| `src/rdc/handlers/script.py` | Validate `path` before use; return `-32602` on missing |

### Tests Updated

| File | Tests Added |
|------|-------------|
| `tests/unit/test_debug_handlers.py` | ~5 tests: missing `eid`, missing `x`, missing `y`, missing `vtx_id`, all missing |
| `tests/unit/test_shader_edit_handlers.py` | ~4 tests: missing `source`, missing `shader_id`, missing `eid`, combined missing |
| `tests/unit/test_pixel_history_daemon.py` | ~2 tests: missing `x`, missing `y` |
| `tests/unit/test_script_handler.py` | ~1 test: missing `path` |

---

## Commit 3: `fix(daemon): harden transport and server loop`

**Agent:** Worktree 1 (Daemon)

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/_transport.py` | Add `max_bytes` limit to `recv_line`; raise `ValueError` (or return error) if line exceeds limit before `\n` found |
| `src/rdc/daemon_server.py` | Wrap `sendall` calls in `try/except OSError`; fix shutdown path so an exception during cleanup does not override the original shutdown exception |

### Tests Updated

| File | Tests Added |
|------|-------------|
| `tests/unit/test_transport_robustness.py` (new) | Test that `recv_line` raises/errors when incoming data exceeds `max_bytes`; test `sendall` failure is caught and logged |
| `tests/unit/test_daemon_server_unit.py` | Test shutdown does not swallow original exception; test non-shutdown exception propagates normally |

---

## Commit 4: `fix(cli): deduplicate call helpers and add connection error handling`

**Agent:** Worktree 2 (CLI)

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/commands/_helpers.py` | Add `ConnectionError` / `OSError` handling to `call()`; print a clear error and exit non-zero on connection failure |
| `src/rdc/commands/pipeline.py` | Remove local `_require_session` / `_call` definitions; import `call` from `_helpers` |
| `src/rdc/commands/resources.py` | Remove local `_require_session` / `_call` definitions; import `call` from `_helpers` |
| `src/rdc/commands/unix_helpers.py` | Remove local `_require_session`, `_get_count_value`, `_get_shader_map_rows`; use `call()` from `_helpers` |
| `src/rdc/commands/info.py` | Remove local `_daemon_call`; import `call` from `_helpers`; retain connection-error handling pattern |

### Tests Updated

| File | Tests Added |
|------|-------------|
| `tests/unit/test_pipeline_commands.py` | 1 test: `ConnectionRefusedError` from `send_request` exits cleanly with user-friendly message |
| `tests/unit/test_resources_commands.py` | 1 test: same pattern for resources command |
| `tests/unit/test_unix_helpers_commands.py` | 1 test: same pattern for unix-helper commands |

Existing CLI tests must also continue to pass unchanged.

---

## Commit 5: `fix: harden diff dispatch, session load, and PID check`

**Agent:** Worktree 3 (Minor)

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/commands/diff.py` | Change sequential `if`/`if`/`if`/`if`/`if` mode dispatch to `if`/`elif`/`elif`/`elif`/`elif` chain to prevent multiple branches from firing |
| `src/rdc/session_state.py` | Wrap `load_session` JSON parse in `try/except (json.JSONDecodeError, OSError)`; add process-name check to `is_pid_alive` to guard against PID recycling |

### Tests Updated

| File | Tests Added |
|------|-------------|
| `tests/unit/test_session_state.py` | Test `load_session` with corrupt JSON file; test `is_pid_alive` returns `False` when PID is recycled to a different process |
| `tests/unit/test_diff_command.py` | Verify existing tests still pass; no new tests required unless behavior changes |

---

## File Conflict Analysis

| Worktree | Files Owned |
|----------|-------------|
| Worktree 1 | `src/rdc/handlers/*.py`, `src/rdc/_transport.py`, `src/rdc/daemon_server.py`, related test files |
| Worktree 2 | `src/rdc/commands/_helpers.py`, `src/rdc/commands/pipeline.py`, `src/rdc/commands/resources.py`, `src/rdc/commands/unix_helpers.py`, `src/rdc/commands/info.py` |
| Worktree 3 | `src/rdc/commands/diff.py`, `src/rdc/session_state.py`, `tests/unit/test_session_state.py`, `tests/unit/test_diff_command.py` |

No file overlaps across worktrees. Parallel execution is safe.

---

## Acceptance Criteria

- `pixi run lint && pixi run test` passes with zero failures after all commits are merged
- No regression in existing test suite
- All `-32602` responses use consistent error format matching existing daemon convention
- `recv_line` max-bytes limit is configurable or has a documented constant
- No duplicate `_require_session` / `_call` / `_daemon_call` definitions remain across CLI command modules
