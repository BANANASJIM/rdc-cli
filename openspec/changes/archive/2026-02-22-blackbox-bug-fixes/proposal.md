# Proposal: Blackbox Bug Fix Batch (2026-02-22)

## Summary

Six bugs were identified during blackbox testing on 2026-02-22 across four subsystems: shader
debugging (`debug vertex`, `debug pixel`), texture statistics (`tex-stats`), CI assertion
(`assert-state`), script help text (`script`), and the count command (`count`). This proposal
describes targeted fixes for each bug along with the test coverage gaps that must be filled
alongside them. No new features are introduced; the only behavioral change that qualifies as
breaking is the redesign of `assert-state`'s `KEY_PATH` semantics, which is acceptable before any
public release.

---

## Motivation

These bugs directly undermine the reliability of rdc-cli as a CI/scripting tool:

- **CI assertions become unreliable**: `assert-state` always fails even when the pipeline value
  matches, making it unusable in automated regression pipelines.
- **Shell scripting breaks on silent success**: `debug pixel` returning rc=0 on error causes
  pipelines that check exit codes to silently pass over failures.
- **Data correctness violations**: `tex-stats --mip/--slice` silently clamping out-of-bounds inputs
  and reporting the wrong mip level poisons downstream analysis scripts without any warning.
- **Developer experience gaps**: `debug vertex` masking a real RenderDoc API exception as a
  generic `internal error` wastes debugging time; `script` not listing available variables causes
  immediate `NameError` for new users; `count shaders` being rejected as an invalid choice breaks
  documented workflows.

---

## Bug Fixes

| Bug ID | Severity | Component | Root Cause (brief) | Fix Approach |
|--------|----------|-----------|-------------------|--------------|
| BUG-1 | P1 | `handlers/debug.py` | `_handle_debug_vertex` calls `_run_debug_loop(controller, trace)`. Inside `_run_debug_loop` (lines 83-97), `controller.ContinueDebug(trace.debugger)` and `_format_step(s, trace)` are called with no exception handling. These RenderDoc API calls can raise on real GPU traces (malformed state, unsupported shader, etc.). The exception propagates to `_process_request()` which catches it and returns a generic `{"error": "internal error"}`. `_extract_inputs_outputs` itself does not raise on empty steps. The `--trace` CLI flag is display-only and does not change the handler code path; both modes call `_run_debug_loop` identically. | Wrap the RenderDoc API calls inside `_run_debug_loop` (specifically `ContinueDebug` and `_format_step`) in try/except; return `_error_response()` with the exception message instead of letting it propagate to the daemon's catch-all. The same fix applies equally to `_handle_debug_pixel` and `_handle_debug_thread` which share `_run_debug_loop`. |
| BUG-2 | P2 | `commands/debug.py` | `call()` in `_helpers.py` already raises `SystemExit(1)` when the daemon returns a JSON-RPC error response (line 51). Static analysis cannot definitively explain the observed rc=0 in plain-text mode vs rc=1 in JSON mode without reproduction. Root cause is unconfirmed: it may be a handler returning a "success" response with missing fields that the CLI post-processes without error, or a subtle difference in error propagation between output modes. | Defensive audit: ensure all output modes in `pixel_cmd` (plain, `--json`, `--trace`, `--dump-at`) propagate rc=1 on any error condition. Add explicit error checks after `_daemon_call()` before branching into output modes. Apply the same consistency audit to `vertex_cmd` and `thread_cmd`. Do not claim a specific root cause before reproduction. |
| BUG-3 | P2 | `handlers/texture.py` | `_handle_tex_stats` reads `mip` and `slice` from params and passes them directly to `GetMinMax()` without bounds checking. `_handle_tex_export` in the same file already has the correct pattern: `if mip < 0 or mip >= tex.mips: return _error_response(...)`. | Mirror the existing `_handle_tex_export` bounds check pattern: validate `mip` against `tex.mips` and `slice` against `tex.arraysize`; return rc=1 and a descriptive error message on violation. |
| BUG-4 | P2 | `commands/assert_ci.py`, `handlers/query.py` | Two distinct issues. **Issue 1**: Single-segment path (e.g., `topology`) produces `field_path = []`. `_traverse_path(result, [])` returns the entire pipeline section response dict rather than the leaf scalar, so `_normalize_value(dict)` stringifies the whole dict instead of the value. **Issue 2**: Shader stage paths (e.g., `vs.shader`, `ps.entry`) completely fail with `error: key 'shader' not found`. When `section` is a shader stage, `_handle_pipeline` falls through to `pipeline_row()` which wraps the result as `{"row": {..., "section_detail": {...}}}`. `assert_state_cmd` then calls `_traverse_path(result, ["shader"])` on a dict that has only the `"row"` key at the top level, not `"shader"`. | **Issue 1 fix**: When `field_path == []`, extract the leaf value directly from the section response rather than returning the whole dict. For scalar sections like `topology`, the section name is the key in the result dict. **Issue 2 fix**: Fix the routing in `_handle_pipeline` for shader stage sections so the response shape is consistent, OR add special-case extraction in `assert_state_cmd` to unwrap `result["row"]["section_detail"]` for shader stage sections. |
| BUG-5 | P2 | `commands/script.py` | The `script_cmd` docstring states the script "has access to the live ReplayController" but does not list the five injected variable names. Users writing `session` or `ctrl` get `NameError`. The actual variables injected by `handlers/script.py` are: `controller`, `rd`, `adapter`, `state`, `args`. | Update the `script_cmd` docstring to explicitly list all five variables with a one-line description each. No handler changes needed. |
| BUG-6 | P2 | `commands/unix_helpers.py`, `handlers/core.py`, `services/query_service.py` | `_COUNT_TARGETS` is `["draws", "events", "resources", "triangles", "passes", "dispatches", "clears"]`; `"shaders"` is absent so Click rejects it before the handler is reached. In `_handle_count` (core.py), `"resources"` is handled as a special case before falling through to `count_from_actions`. `count_from_actions` validates against `_VALID_COUNT_TARGETS` in `query_service.py` which also does not include `"shaders"`. `shader_inventory()` exists in `query_service.py` and returns unique shader rows, matching the semantics of `rdc shaders`. | Three-file fix: (1) Add `"shaders"` to `_COUNT_TARGETS` in `unix_helpers.py`. (2) Add a `"shaders"` special-case branch in `_handle_count` in `core.py`, analogous to the `"resources"` branch, that calls `shader_inventory()` and returns `len(rows)`. (3) Add `"shaders"` to `_VALID_COUNT_TARGETS` in `query_service.py` (or keep it handler-only and skip `count_from_actions`). `assert-count shaders` inherits the fix automatically via `_COUNT_TARGETS`. |

---

## Response Format Reference (for BUG-4 implementation)

Pipeline section response shapes returned by `_handle_pipeline` / delegated pipe_state handlers:

- **Non-shader sections** (topology, viewport, blend, etc.): each pipe handler returns its own flat
  result directly, e.g.:
  - `topology` → `{"eid": 120, "topology": "TriangleList"}`
  - `viewport` → `{"eid": 120, "x": 0, "y": 0, "width": 1920, "height": 1080, ...}`
  - `blend` → `{"eid": 120, "blends": [{...}, ...]}`
- **Shader stage sections** (vs, ps, cs, hs, ds, gs): currently fall through to `pipeline_row()`
  and are wrapped as `{"row": {"eid": ..., "api": ..., "section": "vs", "section_detail": {...}}}`.
  After fix, shader stage sections should expose their `section_detail` contents at the top level
  so that `_traverse_path` can reach fields like `shader`, `entry`, `ro`, `rw`, `cbuffers`.
  Expected `section_detail` fields: `{"eid": int, "stage": str, "shader": int, "entry": str,
  "ro": int, "rw": int, "cbuffers": int}`.

**Breaking change note**: Only single-segment shorthand resolution is new behavior; existing
two-segment paths (e.g., `topology.topology`) continue to work with no regression to the 13
existing tests that use them.

---

## Test Framework Improvements

Each fix must ship with tests that cover the previously missing scenarios:

| Bug ID | New Test Cases |
|--------|---------------|
| BUG-1 | Unit: mock `ContinueDebug` raising an exception inside `_run_debug_loop`; verify the handler returns a structured error response (not a generic `internal error` from the daemon catch-all). Unit: mock `_format_step` raising an exception; same assertion. Unit: empty `steps` list passes through without error (existing behavior of `_extract_inputs_outputs` is correct). |
| BUG-2 | CLI: `pixel_cmd` when the daemon returns an error response; assert rc=1 in both plain-text and `--json` modes. Use `CliRunner` to confirm no swallowed exits. If a specific swallowing code path is found during reproduction, add a targeted regression test for it. |
| BUG-3 | Unit: `_handle_tex_stats` with `mip=999` on a texture with `mips=1`; assert error response with rc=1. Unit: `slice=999` on a texture with `arraysize=1`; assert error response. Unit: valid boundary values (`mip=0`, `slice=0`) still succeed. |
| BUG-4 | CLI: `assert-state EID topology --expect TriangleList` with a mocked pipeline response returning `{"eid": 120, "topology": "TriangleList"}`; assert pass + rc=0. CLI: shader stage path `vs.shader --expect 12345` with mock returning `{"eid": 120, "stage": "vs", "shader": 12345, ...}`; assert pass. CLI: nested path `blend.blends.0.enabled --expect false`; assert pass. CLI: mismatch on any path; assert fail + rc=1. |
| BUG-5 | CLI: `rdc script --help` output contains `controller`, `rd`, `adapter`, `state`, `args`; assert via `CliRunner`. |
| BUG-6 | CLI: `rdc count shaders` with mock daemon returning `{"value": 3}`; assert rc=0 and output `3`. CLI: `rdc assert-count shaders --expect 3` with mock; assert pass + rc=0. Unit: `_handle_count` with `what="shaders"` calls `shader_inventory` and returns correct count. |

---

## Non-Goals

- No new CLI commands or JSON-RPC methods.
- No changes to the daemon architecture, transport layer, or VFS.
- No changes to other `debug` subcommands (`thread`) beyond the `_run_debug_loop` exception
  handling fix that already benefits all three debug handlers, and the rc propagation audit for
  BUG-2.

---

## Breaking Changes

| Change | Impact | Rationale |
|--------|--------|-----------|
| `assert-state KEY_PATH` semantics (BUG-4 Issue 1): single-segment keys like `topology` now resolve to the leaf scalar rather than the entire section response dict. Shader stage paths like `vs.shader` now correctly resolve via `section_detail` rather than failing. | Any script using `assert-state` is broken today (single-segment paths always fail; shader paths always error), so fixing the semantics is not a regression. Pre-release; no external consumers. | The original design was never functional for leaf comparisons or shader stage traversal; fixing it is the only path to a working command. |
| `rdc script -c "..."` inline mode: already removed prior to this batch. | Accepted. | Pre-release breaking change already recorded. |
