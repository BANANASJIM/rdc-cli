# Proposal: Robustness Hardening — P1/P2 Bug Fix Batch

**Date:** 2026-02-22
**Phase:** Post-4C maintenance
**Status:** Draft

---

## Summary

Fix 10 confirmed P1/P2 bugs across the daemon server and CLI layers. No new features, no protocol changes. All fixes are narrowly scoped to eliminate resource leaks, opaque error messages, crash-on-disconnect, and duplicated code.

---

## Problem Statement

Code review identified three classes of defects:

1. **Silent resource leaks**: The shutdown handler never cleans up GPU-allocated shaders or active replacements, leaking GPU memory on every daemon exit when shader edit-replay was used.

2. **Opaque internal errors**: Missing required params cause a `KeyError` that is swallowed by the blanket `except Exception` in `run_server`, returning `-32603 internal error` with no actionable information. Twelve call sites across four handler files are affected.

3. **Crash and correctness issues in the server transport layer**: `recv_line` has no memory cap, `sendall` is unguarded against client disconnect, and the blanket exception handler unconditionally resets `running = True`, preventing shutdown from completing if GPU cleanup raises.

4. **Duplicated CLI helpers**: `_require_session()` and `_call()` are copy-pasted into `pipeline.py`, `resources.py`, and `unix_helpers.py`, none of which wrap `send_request` in a try/except. Users get Python tracebacks when the daemon is down.

5. **Minor correctness issues**: `diff.py` uses `if/if/if` instead of `if/elif/elif` in a mode dispatch chain; `is_pid_alive` can return `True` for recycled PIDs; `load_session` does not handle corrupt JSON files.

---

## Scope

### Group A — Daemon Server (5 bugs)

**A1: Shutdown leaks GPU resources (P1)**
- File: `src/rdc/handlers/core.py`, `_handle_shutdown`
- Fix: Before `adapter.shutdown()`, iterate `state.shader_replacements` calling `controller.RemoveReplacement(rid)`, then iterate `state.built_shaders` calling `controller.FreeTargetResource(rid)`, then clear both dicts. This mirrors the logic already in `_handle_shader_restore_all` in `shader_edit.py`.

**A2: Missing params return opaque -32603 (P1)**
- Files: `handlers/debug.py`, `handlers/shader_edit.py`, `handlers/pixel.py`, `handlers/script.py`
- Fix: Add an explicit required-param guard at the top of each affected handler. Return `-32602` with message `"missing required param: <name>"` when a required key is absent. Affected params:
  - `debug_pixel`: `eid`, `x`, `y`
  - `debug_vertex`: `eid`, `vtx_id`
  - `shader_build`: `source`
  - `shader_replace`: `shader_id`, `eid`
  - `shader_restore`: `eid`
  - `pixel_history`: `x`, `y`
  - `script`: `path`

**A3: `recv_line` no memory cap (P2)**
- File: `src/rdc/_transport.py`, `recv_line`
- Fix: Add `max_bytes: int = 10 * 1024 * 1024` parameter. Track accumulated byte length; raise `ValueError("request too large")` when exceeded.

**A4: `sendall` crash on client disconnect (P2)**
- File: `src/rdc/daemon_server.py` lines 233 and 244
- Fix: Wrap both `conn.sendall(...)` calls in `try/except OSError` that logs and continues, so a mid-request disconnect does not propagate.

**A5: Shutdown exception overrides `running = False` (P2)**
- File: `src/rdc/daemon_server.py` lines 235–244
- Fix: Extract `running` from the handler return value before the blanket `except`. If the method name is `"shutdown"`, force `running = False` regardless of whether an exception was raised during cleanup.

### Group B — CLI Client (2 bugs)

**B1: Duplicated `_require_session` / `_call` helpers (P1)**
- Files: `commands/pipeline.py`, `commands/resources.py`, `commands/unix_helpers.py`
- Fix: Remove the local `_require_session()` and `_call()` definitions (or `_get_count_value` / `_get_shader_map_rows` in `unix_helpers.py`). Import `require_session` and `call` from `commands/_helpers.py` instead, or rewrite the two unix helper functions to delegate through `call()`.

**B2: No `ConnectionRefusedError` handling — traceback on daemon-down (P1)**
- Files: same as B1 (all callers of the duplicated `_call`)
- Fix: Extend `call()` in `commands/_helpers.py` to catch `ConnectionRefusedError` and `OSError`, print `error: daemon unreachable: <exc>` to stderr, and raise `SystemExit(1)`. B1's dedup means all callers inherit this fix automatically. Pattern to follow: `info.py`'s `_daemon_call`.

### Group C — Minor (3 bugs)

**C1: `diff_cmd` `if/if/if` should be `if/elif/elif` (P2)**
- File: `commands/diff.py` lines ~161–210
- Fix: Change the four subsequent `if mode ==` / `if mode in` checks to `elif`, making fall-through structurally impossible regardless of whether handlers call `sys.exit()`.

**C2: `is_pid_alive` susceptible to PID recycling (P2)**
- File: `session_state.py` lines 86–93
- Fix: After `os.kill(pid, 0)` succeeds, read `/proc/{pid}/cmdline` (Linux) and check for the daemon signature string (e.g. `daemon_server` or `rdc`). If the cmdline check fails, return `False`. Guard the `/proc` read with `try/except OSError` for portability; add a comment noting the limitation on non-Linux systems.

**C3: `load_session` unhandled corrupt JSON (P2)**
- File: `session_state.py` lines 36–49
- Fix: Wrap `json.loads(...)` and the field accesses in `try/except (json.JSONDecodeError, KeyError, ValueError)`. On any parse or field error, delete the corrupt file and return `None`.

---

## Non-Goals

- Adding new JSON-RPC methods or CLI commands
- Changing the JSON-RPC wire protocol or error code conventions beyond correcting `-32603` to `-32602` for missing params
- Refactoring the handler dispatch architecture (`_DISPATCH` table, `_handle_request`)
- Performance optimization or coverage improvements beyond what these fixes naturally exercise
- Fixing any issues not listed above

---

## Changes Summary

| ID | File(s) | Severity | Type |
|----|---------|----------|------|
| A1 | `handlers/core.py` | P1 | Resource leak |
| A2 | `handlers/debug.py`, `shader_edit.py`, `pixel.py`, `script.py` | P1 | Error quality |
| A3 | `_transport.py` | P2 | DoS / OOM |
| A4 | `daemon_server.py` | P2 | Crash on disconnect |
| A5 | `daemon_server.py` | P2 | Shutdown correctness |
| B1 | `commands/pipeline.py`, `resources.py`, `unix_helpers.py` | P1 | Code duplication |
| B2 | `commands/_helpers.py` (+ B1 callers) | P1 | UX / crash |
| C1 | `commands/diff.py` | P2 | Logic fragility |
| C2 | `session_state.py` | P2 | Correctness |
| C3 | `session_state.py` | P2 | Crash on corrupt state |
