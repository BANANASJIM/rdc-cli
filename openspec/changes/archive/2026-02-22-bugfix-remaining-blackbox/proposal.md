# Proposal: Remaining Blackbox Bug Fixes + JSON Error Coverage (2026-02-22)

## Summary

Five blackbox bugs (B1, B6-B9) discovered during end-to-end testing remain open after PR #84 and
PR #85. Additionally, PR #84's JSON error output fix left several error paths in `assert_ci.py`
still outputting plain text regardless of `--json`. This proposal targets all six issues with
minimal, focused changes across five source files. No new features or API surface are introduced.

---

## Motivation

- **B6 (P1)**: `log --json/--jsonl/--no-header/-q` always returns an empty array. The
  `GetDebugMessages()` API is consume-once; calling it a second time in the same session returns
  nothing. Any structured output format that re-routes through a second call silently loses all
  messages, making `rdc log` unreliable for CI pipelines that parse structured output.
- **B1 (P2)**: `debug vertex` (and `debug pixel`, `debug thread`) return a generic `internal error`
  in default and `--json` modes on real GPU traces. The root cause is `trace.stage` being accessed
  after `_run_debug_loop()` frees the trace object in its `finally` block, causing an exception
  that is caught by the daemon's generic handler.
- **B7 (P2)**: `stats` always shows `-`/`0` for `RT_W`, `RT_H`, and `ATTACHMENTS` columns.
  `aggregate_stats()` initializes these fields to zero and never updates them; the pipeline state
  query needed to populate render-target info is never performed.
- **B8 (P2)**: `stats --no-header` suppresses column headers as intended but still prints section
  titles ("Per-Pass Breakdown:", "Top Draws:") to stderr unconditionally.
- **B9 (P3)**: `stats` has no `--jsonl` or `-q` output mode. The command uses a custom decorator
  instead of `@list_output_options`, leaving structured output unsupported.
- **PR #84 incomplete**: `assert_ci.py` error paths in `_traverse_path()`, `assert_pixel_cmd`
  validation, and `assert_state_cmd` section validation still emit plain text even when `--json`
  is passed, inconsistent with the fix applied elsewhere in PR #84.

---

## Changes

### B6: Cache debug messages in `DaemonState`

**Root cause**: `controller.GetDebugMessages()` consumes the internal message queue on first call.
Any subsequent call within the same session returns an empty list. When `--json`, `--jsonl`,
`--no-header`, or `-q` is used, the handler or CLI re-reads messages via a second code path that
calls the API again, receiving nothing.

**Files**:
- `src/rdc/daemon_server.py`: Add `_debug_messages_cache: list[Any] | None = None` to
  `DaemonState`.
- `src/rdc/handlers/query.py` (`_handle_log`): On first call, invoke `GetDebugMessages()` and
  store the result in `state._debug_messages_cache`. On subsequent calls within the same session,
  return the cached list. Cache is scoped to the session lifetime (invalidated on
  `session_open`/`session_close`).

**Scope**: Handler change only. No CLI changes needed; the empty-array symptom disappears once the
handler returns the correct data on all calls.

---

### B1: Extract `trace.stage` before `_run_debug_loop()`

**Root cause**: In `_handle_debug_vertex` (and the pixel/thread equivalents),
`stage_name = _STAGE_NAMES.get(int(trace.stage), ...)` is evaluated after `_run_debug_loop()`.
`_run_debug_loop()` calls `controller.FreeTrace(trace)` in its `finally` block, invalidating the
trace object. On real GPU traces, accessing any attribute of a freed trace raises a native
exception, which propagates to the daemon's catch-all and surfaces as `"internal error"`.

**Files**:
- `src/rdc/handlers/debug.py`:
  - Move `stage_name` extraction to immediately after the `DebugVertex`/`DebugPixel`/`DebugThread`
    call and before `_run_debug_loop()` in all three handlers.
  - Wrap the `controller.DebugVertex`/`DebugPixel`/`DebugThread` call itself in a try/except and
    return a structured error response (not a generic exception) if the API call fails.

**Scope**: Three handler functions in one file. No CLI changes; the fix corrects the data flow.

---

### B7: Populate RT_W/RT_H/ATTACHMENTS in `_handle_stats`

**Root cause**: `aggregate_stats()` produces per-pass rows with `rt_w`, `rt_h`, and `attachments`
initialized to `0` and never updated. The pipeline-state query needed to retrieve framebuffer
dimensions and attachment counts for each pass is never performed inside `_handle_stats`.

**Files**:
- `src/rdc/handlers/query.py` (`_handle_stats`): After `aggregate_stats()`, iterate over each
  pass row and query `controller.GetPipelineState()` at a representative event within that pass
  (e.g., the first draw EID). Extract framebuffer dimensions and color/depth attachment counts
  from the pipeline state and enrich the pass row in-place. Follow the existing `_build_pass_list`
  pattern for event selection.

**Scope**: Handler enrichment loop only. Output schema is unchanged; previously-zero fields now
carry real values.

---

### B8: Gate section titles on `not no_header`

**Root cause**: "Per-Pass Breakdown:" and "Top Draws:" section titles are written to stderr
unconditionally in `stats_cmd`, bypassing the `--no-header` flag that already suppresses column
headers.

**Files**:
- `src/rdc/commands/info.py` (`stats_cmd`): Wrap each `sys.stderr.write(...)` section-title call
  in `if not no_header:`.

**Scope**: Two-line guard addition. No handler changes.

---

### B9: Add `--jsonl`/`-q` support to `stats`

**Root cause**: `stats_cmd` uses a custom `@click.option` set instead of `@list_output_options`,
so it has `--json` but no `--jsonl` or `-q`. The handler already returns a list-shaped response,
so adding the decorator and routing its output modes is straightforward.

**Files**:
- `src/rdc/commands/info.py` (`stats_cmd`):
  - Replace the custom `--json`/`--no-header` options with `@list_output_options` (which provides
    `--json`, `--jsonl`, `-q`, `--no-header`).
  - Update the function signature and output routing to handle all four modes.

**Scope**: One command function. Handler unchanged.

---

### PR #84: Apply JSON error formatting to remaining `assert_ci.py` paths

**Root cause**: PR #84 added `_json_mode()` / `_json_error()` helpers and applied them to the
main response paths, but three sets of error paths were missed:
1. `_traverse_path()` key-not-found and index-out-of-range errors (lines 102, 107, 111).
2. `assert_pixel_cmd` argument validation errors (lines 141-147, 153).
3. `assert_state_cmd` invalid-section error (line 299).

All three still call `click.echo(f"error: ...")` unconditionally, so `--json` output is malformed
when these paths are hit.

**Files**:
- `src/rdc/commands/assert_ci.py`:
  - In `_traverse_path()`: call `_json_error(ctx, msg)` when `--json` is active, else fall back
    to `click.echo`.
  - In `assert_pixel_cmd` validation block: same pattern.
  - In `assert_state_cmd` invalid-section block: same pattern.

**Scope**: Error-path formatting only; no behavioral changes to success paths.

---

## Risk Assessment

| Bug | Risk of Fix | Notes |
|-----|------------|-------|
| B6 cache | Low | Cache scoped to session; cleared on open/close; no thread-safety concern (single-threaded daemon) |
| B1 stage extraction | Low | Reordering two lines; no new logic |
| B7 RT enrichment | Medium | New pipeline-state queries per pass; tested only on mock; GPU test needed |
| B8 no-header gate | Minimal | Two-line guard; no logic change |
| B9 list_output_options | Low | Decorator is already used by other commands; adding it here is mechanical |
| PR#84 assert_ci | Low | Error paths only; success paths untouched |

---

## Backward Compatibility

All changes are internal behavior fixes on commands that were returning incorrect or incomplete
data. No CLI flags are removed. B9 adds new flags (`--jsonl`, `-q`) to `stats`, which is purely
additive. The B8 fix changes stderr output only when `--no-header` is explicitly passed, which
previously produced inconsistent output anyway. No JSON-RPC method signatures change.
