# Test Plan: Fix B17 — Read-Only Queries Mutate current_eid

## Root Cause Summary

`_set_frame_event()` unconditionally sets `state.current_eid = eid`. Four internal
call sites inside `_build_shader_cache._walk()`, `_ensure_shader_populated`,
`_handle_stats`, and `_handle_pass` call this function for read-only seeks, silently
moving the user's replay position. The fix replaces those calls with `_seek_replay()`
which drives the adapter without touching `current_eid`.

---

## New Tests — `tests/unit/test_shader_preload.py`

Add a `TestEidPreservation` class. All tests follow the pattern:

1. Build a minimal `DaemonState` with `current_eid` set to a sentinel value (50).
2. Monkeypatch the adapter so no real RenderDoc calls are made.
3. Call the handler under test.
4. Assert `state.current_eid` is still 50.

### `test_build_shader_cache_preserves_current_eid`

**Verifies:** `_build_shader_cache` does not mutate `state.current_eid`.

- Setup: Build `DaemonState` with a mock adapter that returns 3 actions (two draws,
  one dispatch). Set `state.current_eid = 50`.
- Mock `state.adapter.set_frame_event` to record calls.
- Mock `state.adapter.get_pipeline_state()` to return a mock pipe with `GetShader`
  returning 1 for stage 0 (vs) and 0 for all other stages.
- Call `_build_shader_cache(state)`.
- Assert: `state.current_eid == 50` (not mutated to any action's EID).
- Assert: `state.adapter.set_frame_event` was called (the cache walk did seek internally).
- Assert: `state._shader_cache_built is True`.

### `test_stats_preserves_current_eid`

**Verifies:** `_handle_stats` does not mutate `state.current_eid`.

- Setup: Build `DaemonState` with a mock adapter returning 2 draw actions in 1 pass.
  Set `state.current_eid = 50`.
- Mock `_get_flat_actions` (via `rdc.daemon_server._get_flat_actions`) to return a
  flat list containing those 2 actions with `pass_name="pass0"`.
- Mock `state.adapter.get_pipeline_state()` to return a mock pipe.
- Call `_handle_request({"jsonrpc": "2.0", "id": 1, "method": "stats",
  "params": {"_token": state.token}}, state)` or call `_handle_stats` directly.
- Assert: response has `"result"` key (no error).
- Assert: `state.current_eid == 50`.

### `test_pass_preserves_current_eid`

**Verifies:** `_handle_pass` does not mutate `state.current_eid`.

- Setup: Build `DaemonState` with a mock adapter returning a structured action tree
  that represents 1 render pass (begin EID 5, draw EID 10, end EID 15).
  Set `state.current_eid = 50`.
- Mock `get_pass_detail` (from `rdc.services.query_service`) to return a fake pass
  detail dict with `begin_eid=5`.
- Mock `state.adapter.get_pipeline_state()` to return a mock pipe with
  `GetOutputTargets()` returning `[]` and `GetDepthTarget()` returning a mock with
  `resource=0`.
- Call `_handle_pass` with `params={"_token": state.token, "index": 0}`.
- Assert: response has `"result"` key (no error).
- Assert: `state.current_eid == 50`.

---

## Regression Tests

The following existing tests must continue to pass unchanged. They confirm the fix
does not break the normal (user-seek) path of `_set_frame_event`.

**`test_seek_updates_current_eid`** *(if present in test suite)*
- Existing test verifying that the `seek` command updates `state.current_eid`.
- Must still pass — `_set_frame_event` is still used for user-visible seeks.

**`test_build_shader_cache_populates_caches`** *(existing in `test_shader_preload.py`)*
- Verifies `disasm_cache`, `shader_meta`, and `_pipe_states_cache` are populated.
- Must still pass — the cache walk still works correctly after the fix.

**`test_handle_stats_response_structure`** *(existing stats handler tests)*
- Verifies `stats` returns `total_draws`, `per_pass`, etc.
- Must still pass — the RT enrichment loop still runs; only `current_eid` is protected.

**`test_handle_pass_returns_targets`** *(existing pass handler tests)*
- Verifies `pass` returns `color_targets` and `depth_target`.
- Must still pass — `_handle_pass` still seeks to the pass begin EID for pipeline info.

**`pixi run lint && pixi run test`**
- All 1857+ unit tests must pass.
- Zero lint/mypy errors.

---

## Test Matrix

| Test | Type | File | Covers |
|------|------|------|--------|
| `test_build_shader_cache_preserves_current_eid` | unit | `test_shader_preload.py` | B17 |
| `test_stats_preserves_current_eid` | unit | `test_shader_preload.py` | B17 |
| `test_pass_preserves_current_eid` | unit | `test_shader_preload.py` | B17 |
| `test_build_shader_cache_populates_caches` | regression | `test_shader_preload.py` | B17 |
| `test_handle_stats_response_structure` | regression | existing | B17 |
| `test_handle_pass_returns_targets` | regression | existing | B17 |
