# Tasks: Fix Bugs B10 + B15 + B16

## Task 1: Raise transport max_bytes limit (B10)

- **Files**: `src/rdc/_transport.py`
- **Changes**:
  - In `recv_line`, increase the default `max_bytes` from `10 * 1024 * 1024` (10 MB) to `256 * 1024 * 1024` (256 MB). A compute shader trace of up to 50,000 steps with many changed variables can easily produce a JSON response exceeding 10 MB.
  - Verify that any call site passing an explicit `max_bytes` argument also uses an adequate limit.
- **Depends on**: nothing
- **Estimated complexity**: S

## Task 2: Catch `ValueError` in `call()` for proper error handling (B10)

- **Files**: `src/rdc/commands/_helpers.py`
- **Changes**:
  - In `call()` (line 58-66), the `except OSError` clause must also catch `ValueError`. When `recv_line` raises `ValueError` (e.g., message exceeds max_bytes), it propagates unhandled through Click, and in `--json` mode the process may exit RC=0 instead of RC=1.
  - Change `except OSError as exc:` to `except (OSError, ValueError) as exc:`. This ensures all transport-level failures produce RC=1 with a structured error message in all output modes.
  - Note: `_check_debug_result(result)` already runs before the `if use_json:` branch in all three debug commands (lines 101, 154, 192 of `debug.py`), so no reordering is needed there. The issue is purely that `ValueError` is not caught in `call()`.
- **Depends on**: nothing (independent of Task 1)
- **Estimated complexity**: S

## Task 3: Fix shader-map column mapping for compute dispatches (B15)

- **Files**: `src/rdc/handlers/_helpers.py`, `src/rdc/services/query_service.py`, `src/rdc/daemon_server.py`
- **Changes**:
  Two changes needed — snapshot fix + stage restriction:

  **3a. Snapshot shader IDs in `_build_shader_cache`** (`src/rdc/handlers/_helpers.py`):
  - Root cause: `get_pipeline_state()` returns a **mutable reference** (documented in MEMORY.md). All entries in `_pipe_states_cache` point to the same live object, reflecting only the last event visited.
  - Fix: Replace `state._pipe_states_cache[a.eventId] = pipe` with a snapshot:
    ```python
    stage_snap: dict[int, int] = {}
    for sv in range(6):
        stage_snap[sv] = int(pipe.GetShader(sv))
    state._pipe_states_cache[a.eventId] = stage_snap
    ```
  - Update `_pipe_states_cache` type annotation in `DaemonState` (`daemon_server.py`) to `dict[int, dict[int, int]]`.

  **3b. Restrict stage queries per action type in `_collect_recursive`** (`src/rdc/services/query_service.py`):
  - Since `_pipe_states_cache` now stores `dict[int, int]` snapshots, update `_collect_recursive` to do dict lookups instead of `.GetShader()` calls.
  - For dispatches (`flags & _DISPATCH`): only read stage 5 (cs); set stages 0–4 to `"-"`.
  - For draws (`flags & _DRAWCALL`): only read stages 0–4; set stage 5 (cs) to `"-"`.
  - Note: `_handle_pipeline` and `_handle_bindings` use fresh `get_pipeline_state()` calls (not `_pipe_states_cache`), so they are unaffected.
- **Depends on**: nothing
- **Estimated complexity**: M

## Task 4: Add mesh shader draw classification for MeshDispatch flag (B16)

- **Files**: `src/rdc/services/query_service.py`, `src/rdc/handlers/_helpers.py`
- **Changes**:
  - Add `_MESH_DISPATCH = 0x0008` constant to `query_service.py` alongside the other ActionFlags constants. This corresponds to `ActionFlags.MeshDispatch` in the RenderDoc API (confirmed in `tests/mocks/mock_renderdoc.py`).
  - In `_action_type_str` (`src/rdc/handlers/_helpers.py`): add a branch to import and check `_MESH_DISPATCH` alongside `_DRAWCALL`. If `flags & _MESH_DISPATCH`, return `"Draw"` (mesh draw calls are draw calls for reporting purposes). Insert this check before the `_DISPATCH` branch, since `MeshDispatch` is semantically a draw variant.
  - In `filter_by_type` (`src/rdc/services/query_service.py`): update the `"draw"` entry to match both `_DRAWCALL` and `_MESH_DISPATCH`. Replace `"draw": _DRAWCALL` with a lambda or a combined flag check. Since `filter_by_type` currently uses a simple bitmask `flags & flag`, introduce a helper or change the map to use a combined mask: `"draw": _DRAWCALL | _MESH_DISPATCH`.
  - In `aggregate_stats` (`src/rdc/services/query_service.py`): the `if a.flags & _DRAWCALL:` branch must also cover `_MESH_DISPATCH`. Change to `if a.flags & (_DRAWCALL | _MESH_DISPATCH):`.
  - In `_subtree_has_draws`, `_window_stats`, `_subtree_stats` (all in `query_service.py`): the `flags & _DRAWCALL` checks used for pass stats must also include `_MESH_DISPATCH`.
  - In `get_top_draws` (`src/rdc/services/query_service.py:221`): `[a for a in flat if a.flags & _DRAWCALL]` must also include `_MESH_DISPATCH`.
  - In `_handle_stats` RT enrichment (`src/rdc/handlers/query.py:290`): `a.flags & _DRAWCALL` for `pass_first_draw` must also include `_MESH_DISPATCH`.
  - In `_build_shader_cache` (`src/rdc/handlers/_helpers.py`): the condition `(flags & _DRAWCALL) or (flags & _QS_DISPATCH)` must also include `_MESH_DISPATCH` so mesh draws are included in the shader cache and `_pipe_states_cache`.
  - In `_collect_recursive` (`src/rdc/services/query_service.py`): the condition `(flags & _DRAWCALL) or (flags & _DISPATCH)` must also cover `_MESH_DISPATCH`. Treat mesh draws like graphics draws for stage column purposes (query stages 0–4, not stage 7). Adding a mesh-specific stage column is out of scope for this fix.
- **Depends on**: nothing
- **Estimated complexity**: M

## Task 5: Write tests for B10 (transport overflow + RC masking)

- **Files**: `tests/unit/test_daemon_transport.py`, `tests/unit/test_debug_commands.py`
- **Changes**:
  - In `test_daemon_transport.py`, add:
    - `test_recv_line_default_limit_is_large`: verify that `recv_line` with default `max_bytes` can accumulate at least 50 MB of data without raising (simulate large message by mocking `sock.recv` to return multiple 4096-byte chunks containing no newline, then a final chunk with `\n`).
    - `test_recv_line_explicit_small_limit_raises`: verify that passing `max_bytes=100` still raises `ValueError` on oversized input (regression guard; existing test `test_recv_line_exceeds_max_bytes` already covers this).
  - In `test_debug_commands.py`, add for `thread_cmd`, `pixel_cmd`, and `vertex_cmd`:
    - `test_thread_json_rc_on_incomplete_result`: mock `_daemon_call` to return a dict missing `"total_steps"` (incomplete result); invoke with `--json`; assert `exit_code == 1` (not 0).
    - `test_pixel_json_rc_on_incomplete_result`: same for `debug pixel`.
    - `test_vertex_json_rc_on_incomplete_result`: same for `debug vertex`.
    - Use `CliRunner` and `monkeypatch` (or `unittest.mock.patch`) on `rdc.commands._helpers._daemon_call` (or the appropriate import path used in `debug.py`: `rdc.commands.info._daemon_call`).
- **Depends on**: Task 1, Task 2
- **Estimated complexity**: S

## Task 6: Write tests for B15 (shader-map dispatch column mapping)

- **Files**: `tests/unit/test_count_shadermap.py`
- **Changes**:
  - In `TestShaderMapCollection`, add:
    - `test_shader_map_dispatch_only_shows_cs_column`: create a dispatch action (EID 8) with a pipe state that has ONLY a CS shader bound (e.g., `cs=99`) but whose `GetShader(0)` through `GetShader(4)` would return non-zero values (simulate the stale pipeline bug by setting `vs=10, ps=11, cs=99` in the mock pipe state). Assert that in the resulting row: `cs == 99` and `vs == "-"`, `ps == "-"`. This verifies the fix prevents graphics-stage IDs from leaking into dispatch rows.
    - `test_shader_map_mixed_draw_and_dispatch`: create a list with one draw action (EID 1, vs+ps bound) and one dispatch action (EID 2, cs-only bound). Assert that EID 1 has `vs != "-"` and `cs == "-"`, and EID 2 has `cs != "-"` and `vs == "-"`.
  - These tests require that `MockPipeState.GetShader` be callable and return configured shaders; the existing `_make_pipe_state` helper already supports this.
- **Depends on**: Task 3
- **Estimated complexity**: S

## Task 7: Write tests for B16 (mesh dispatch classification)

- **Files**: `tests/unit/test_draws_events_daemon.py`, `tests/unit/test_query_service.py`
- **Changes**:
  - In `test_draws_events_daemon.py` (or `test_query_service.py`), add:
    - `test_mesh_dispatch_classified_as_draw_in_events`: build an `ActionDescription` with `flags=ActionFlags.MeshDispatch` (value `0x0008`) and EID 10. Create daemon state, send `events` request, assert that the event with EID 10 has `type == "Draw"` (not `"Other"`).
    - `test_mesh_dispatch_included_in_draws_list`: send `draws` request; assert EID 10 appears in `result["draws"]`.
    - `test_mesh_dispatch_counted_in_stats`: send `stats` request; assert `result["total_draws"] >= 1`.
    - `test_filter_by_type_draw_includes_mesh_dispatch`: unit-test `filter_by_type` directly with a `FlatAction` that has `flags=0x0008`; assert it appears in `filter_by_type(flat, "draw")`.
    - `test_action_type_str_mesh_dispatch_returns_draw`: unit-test `_action_type_str(0x0008)` directly; assert it returns `"Draw"`.
  - Use `mrd.ActionFlags.MeshDispatch` (already defined as `0x0008` in `mock_renderdoc.py`) to construct mock actions.
- **Depends on**: Task 4
- **Estimated complexity**: S

---

## Parallelism

All implementation tasks are independent and can run in parallel:

- **Task 1** (transport limit) and **Task 2** (RC masking) touch different files and are fully independent.
- **Task 3** (shader-map dispatch columns) touches only `query_service.py` `_collect_recursive`.
- **Task 4** (mesh dispatch) touches `query_service.py` (different functions from Task 3) and `_helpers.py`. If Task 3 and Task 4 are assigned to the same agent, they must coordinate on `_collect_recursive` changes to avoid conflicts.

Test tasks depend on their corresponding implementation tasks:
- **Task 5** depends on Tasks 1 + 2
- **Task 6** depends on Task 3
- **Task 7** depends on Task 4

## Implementation order

1. **Phase A (parallel)**: Tasks 1, 2, 3, 4 — implementation fixes
2. **Phase B (parallel)**: Tasks 5, 6, 7 — test coverage (after Phase A completes)
3. **Verification**: `pixi run lint && pixi run test` — zero failures required

### Notes for implementers

- **Task 3 + Task 4 conflict**: both modify `query_service.py`. If done by separate agents, split as follows:
  - Task 3 agent: only modifies `_collect_recursive`
  - Task 4 agent: modifies `_MESH_DISPATCH` constant, `_action_type_str`, `filter_by_type`, `aggregate_stats`, `_subtree_has_draws`, `_window_stats`, `_subtree_stats`, `_build_shader_cache`
  - Merge both sets of changes to `query_service.py` carefully before running tests.
- **B15 root cause**: `get_pipeline_state()` returns a **mutable reference** (MEMORY.md gotcha). All entries in `_pipe_states_cache` share the same stale object reflecting only the last event visited. Fix requires **both** snapshotting shader IDs in `_build_shader_cache` (Task 3a) **and** restricting stage queries per action type in `_collect_recursive` (Task 3b).
- **B16 scope**: `vkCmdDrawMeshTasksEXT` sets `ActionFlags.MeshDispatch` (0x0008) only, not `ActionFlags.Drawcall` (0x0002). The fix must not alter the `_DISPATCH` (0x0004) classification — mesh draws are not dispatches.
