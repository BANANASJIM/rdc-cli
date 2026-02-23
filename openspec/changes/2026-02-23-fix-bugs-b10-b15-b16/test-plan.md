# Test Plan: Fix Bugs B10 + B15 + B16

## B10: Transport overflow for `debug thread`

### Root Cause Summary

`send_request` in `daemon_client.py` calls `recv_line(sock)` with the default
`max_bytes=10 * 1024 * 1024` (10 MB). Large compute shader debug traces (many
steps × many variables) serialize to JSON that exceeds this limit, raising
`ValueError: recv_line: message exceeds max_bytes limit`. The fix must raise
the limit or stream the response differently. A secondary defect is that when
`_daemon_call` receives an error response (via `SystemExit` or the raw error
dict path), the `--json` mode does not propagate `rc=1`.

### Unit tests — `tests/unit/test_daemon_transport.py`

**`test_recv_line_large_message_at_limit`**
- Create a mock socket returning a single chunk of exactly `max_bytes` bytes
  containing a newline at the end.
- Call `recv_line(sock, max_bytes=N)`.
- Assert: returns the decoded string without raising.

**`test_recv_line_large_message_just_over_limit`**
- Mock socket emits two chunks; combined length is `max_bytes + 1`.
- Assert: `ValueError` with message matching `"max_bytes"`.

**`test_recv_line_multi_chunk_large_valid`**
- Mock socket returns 3 chunks totalling less than `max_bytes`, newline in
  final chunk.
- Assert: result equals the expected decoded string.

**`test_recv_line_default_limit_is_large_enough_for_debug`**
- Construct a JSON payload resembling a debug trace with 2000 steps and 10
  variables per step (~1 MB of JSON).
- Encode as bytes + `\n`, serve via a mock socket in 4096-byte chunks.
- Call `recv_line(sock)` (default limit).
- Assert: does not raise; returns the full JSON string.

### Unit tests — `tests/unit/test_debug_commands.py`

These extend the existing `_patch_helpers` pattern in the file.

**`test_debug_thread_error_json_rc1`**
- Patch `_helpers.send_request` to return `_ERROR_RESPONSE`.
- Invoke `["debug", "thread", "150", "0", "0", "0", "0", "0", "0", "--json"]`.
- Assert: `result.exit_code == 1`.
- Rationale: B10 symptom says `--json` mode returns `rc=0` on daemon error;
  this must become `rc=1`.

**`test_debug_thread_error_trace_rc1`**
- Same error response, invoke with `["...", "--trace"]`.
- Assert: `result.exit_code == 1`.

**`test_debug_thread_error_plain_rc1`**
- Same error response, plain invocation.
- Assert: `result.exit_code == 1`.

**`test_debug_thread_success_json_rc0`**
- Patch to return `{"result": _THREAD_HAPPY_RESPONSE}`.
- Invoke with `["...", "--json"]`.
- Assert: `result.exit_code == 0`; output is valid JSON with `stage == "cs"`.

**`test_debug_thread_transport_error_json_rc1`**
- Patch `_helpers.send_request` to raise `ValueError("recv_line: message exceeds max_bytes limit")`.
- Invoke with `["debug", "thread", "150", "0", "0", "0", "0", "0", "0", "--json"]`.
- Assert: `result.exit_code == 1`; stderr contains an informative message.

**`test_debug_thread_transport_error_plain_rc1`**
- Same `ValueError` raise, plain invocation.
- Assert: `result.exit_code == 1`.

**`test_call_catches_value_error`**
- Directly test the `call()` function in `_helpers.py` with `send_request` raising `ValueError`.
- Assert: `SystemExit(1)` is raised. This covers all commands since `call()` is shared.

### Integration tests — `tests/unit/test_debug_handlers.py`

**`test_debug_thread_large_trace_handler_level`**
- Build a dispatch state with a mock controller whose `ContinueDebug` returns
  a list of 2000 `ShaderDebugState` objects, each with 10 variable changes.
- Call `_handle_request(_req("debug_thread", {...}), state)`.
- Assert: `"result" in resp`; `resp["result"]["total_steps"] == 2000`.
- This validates the handler does not truncate internally; overflow only occurs
  in the transport layer.

### GPU tests — `tests/integration/test_daemon_handlers_real.py`

No new GPU test is required for B10 because the transport limit is a
protocol-layer concern tested above. If a `compute_nbody.rdc` fixture is
available, add:

**`test_debug_thread_compute_nbody`** *(conditional, skip if fixture absent)*
- `pytest.importorskip` / `pytest.mark.skipif` guards.
- Call `_call(state, "debug_thread", {"eid": <dispatch_eid>, "gx": 0, ...})`.
- Assert: `"total_steps"` key present; no exception raised.

---

## B15: `shader-map` Dispatch EID column mapping

### Root Cause Summary

`collect_shader_map` in `query_service.py` uses `STAGE_MAP` (integer keys
`0..5`). When iterating `stage_cols = {0: "vs", ..., 5: "cs"}`, it calls
`state.GetShader(stage_val)` for every stage regardless of pipeline type. For
a Dispatch action the compute pipeline only binds `cs` (stage 5), yet
`GetShader(4)` (PS) accidentally returns the CS shader ID because the mock (or
real API) falls back to a non-zero value. The fix must ensure that for
Dispatch-flagged actions only the `cs` column is populated, and for Draw-
flagged actions only graphics columns (`vs`, `hs`, `ds`, `gs`, `ps`) are
populated.

### Unit tests — `tests/unit/test_count_shadermap.py`

Add inside `TestShaderMapCollection`:

**`test_shader_map_dispatch_only_populates_cs`**
- Build actions with one `_dispatch(eid=8, ...)`.
- Build `pipe_states = {8: _make_pipe_state(cs=99)}` where `vs=ps=0`.
- Call `collect_shader_map(actions, pipe_states)`.
- Assert: `rows[0]["cs"] == 99`.
- Assert: `rows[0]["vs"] == "-"` and `rows[0]["ps"] == "-"`.

**`test_shader_map_dispatch_no_graphics_shader_leak`**
- Build actions with one `_dispatch(eid=11, ...)`.
- Build a `MockPipeState` where `GetShader(4)` (PS stage) returns a non-zero
  ID (simulating the bug: CS shader leaking into PS slot).
- Call `collect_shader_map(actions, pipe_states)`.
- Assert: `rows[0]["ps"] == "-"` (the fix must enforce this for Dispatch).
- Assert: `rows[0]["cs"]` is the expected non-zero value.

**`test_shader_map_mixed_draw_and_dispatch`**
- Actions: `[_indexed_draw(8, "draw"), _dispatch(11, "dispatch")]`.
- `pipe_states`: draw has VS+PS shaders, dispatch has only CS shader.
- Call `collect_shader_map(actions, pipe_states)`.
- Assert: row for EID 8 has `vs != "-"`, `ps != "-"`, `cs == "-"`.
- Assert: row for EID 11 has `cs != "-"`, `vs == "-"`, `ps == "-"`.

**`test_shader_map_draw_does_not_show_cs`**
- Build a `_indexed_draw(42, ...)` with a `MockPipeState` where `GetShader(5)`
  (CS) would return a non-zero sentinel (bug scenario for graphics draws).
- Call `collect_shader_map(actions, pipe_states)`.
- Assert: `rows[0]["cs"] == "-"` (CS must not appear for a Draw action).

### Integration tests — daemon handler level

**`test_shader_map_dispatch_columns_daemon`** in `tests/unit/test_count_shadermap.py`
inside `TestDaemonShaderMapMethod`:

- Build actions with both a draw (EID 8, VS+PS) and a dispatch (EID 11, CS).
- Set up adapter mocks so `get_root_actions` returns both actions and
  `get_pipeline_state` returns the correct state per EID.
- Call `_handle_request({"method": "shader_map", ...}, state)`.
- Assert: row for EID 8 has non-null `vs` and `ps`, `cs == "-"`.
- Assert: row for EID 11 has non-null `cs`, `vs == "-"`, `ps == "-"`.

### GPU tests

**`test_shader_map_compute_nbody_dispatch_columns`** *(skip if fixture absent)*
- Load `compute_nbody.rdc`; it contains 2 Dispatch + 3 Draw actions.
- Call `_call(state, "shader_map")`.
- Assert: rows for EIDs 8 and 11 (Dispatch) have `cs != "-"`, `vs == "-"`, `ps == "-"`.
- Assert: rows for Draw EIDs have `ps != "-"`, `cs == "-"`.

---

## B16: `vkCmdDrawMeshTasksEXT` classified as "Other"

### Root Cause Summary

`_action_type_str` in `handlers/_helpers.py` checks for `_DRAWCALL (0x0002)`,
`_DISPATCH (0x0004)`, `_CLEAR`, `_COPY`, `_BEGIN_PASS`, `_END_PASS` and falls
through to `"Other"`. RenderDoc sets `ActionFlags.MeshDispatch (0x0008)` for
`vkCmdDrawMeshTasksEXT`. This flag is not `_DRAWCALL`, so the action is never
classified as a draw. The fix must:
1. Add `MeshDispatch` recognition in `_action_type_str` → return `"Draw"` (or
   `"MeshDraw"`).
2. Add `_MESH_DISPATCH = 0x0008` constant in `query_service.py` and include it
   in the draw-detection predicate used by `filter_by_type`, `aggregate_stats`,
   `count_from_actions`, and `collect_shader_map`.

### Unit tests — `tests/unit/test_draws_events_daemon.py`

**`test_mesh_dispatch_action_type_str`**
- Import `_action_type_str` from `rdc.handlers._helpers`.
- Call with `flags = 0x0008` (MeshDispatch only).
- Assert: return value is `"Draw"` or `"MeshDraw"` (not `"Other"`).

**`test_mesh_dispatch_classified_as_draw_in_events`**
- Build a single `ActionDescription(eventId=10, flags=ActionFlags.MeshDispatch, _name="vkCmdDrawMeshTasksEXT")`.
- Build `DaemonState` with this action tree.
- Call `_handle_request({"method": "events", ...}, state)`.
- Assert: the event row for EID 10 has `"type"` not equal to `"Other"`.
- Assert: `"type"` equals `"Draw"` or `"MeshDraw"`.

**`test_mesh_dispatch_included_in_draws_list`**
- Same action tree.
- Call `_handle_request({"method": "draws", ...}, state)`.
- Assert: `resp["result"]["draws"]` contains an entry with `"eid" == 10`.

**`test_mesh_dispatch_counted_as_draw`**
- Same action tree.
- Call `_handle_request({"method": "count", "params": {"_token": "tok", "what": "draws"}}, state)`.
- Assert: `resp["result"]["value"] == 1`.

**`test_mesh_dispatch_in_info_draw_calls`**
- Call `_handle_request({"method": "info", ...}, state)`.
- Assert: `"Draw Calls"` field in result contains `"1"` (not `"0"`).

**`test_mesh_dispatch_not_classified_as_dispatch`**
- Call `count` with `what="dispatches"` on a mesh-dispatch-only action tree.
- Assert: `value == 0` (mesh draw is not a compute dispatch).

### Unit tests — `tests/unit/test_count_shadermap.py`

**`test_count_mesh_dispatch_as_draw`** in `TestCountAggregation`:
- Build actions with one `ActionDescription(flags=ActionFlags.MeshDispatch)`.
- Call `count_from_actions(actions, "draws")`.
- Assert: returns `1`.

**`test_shader_map_includes_mesh_dispatch`** in `TestShaderMapCollection`:
- Build actions with one `ActionDescription(flags=ActionFlags.MeshDispatch, eventId=10)`.
- Build `pipe_states = {10: _make_pipe_state(vs=1, ps=2)}`.
- Call `collect_shader_map(actions, pipe_states)`.
- Assert: `len(rows) == 1`; `rows[0]["eid"] == 10`.

### Unit tests — `tests/unit/test_draws_events_cli.py` (or new file)

**`test_events_mesh_draw_type`**
- Patch `_daemon_call` to return events with `type="MeshDraw"` or `"Draw"` for EID 10.
- Invoke `["events"]` via `CliRunner`.
- Assert: EID 10 appears in output; `"Other"` does not appear for it.

**`test_draws_mesh_draw_included`**
- Patch `_daemon_call` to return draws including EID 10.
- Invoke `["draws"]` via `CliRunner`.
- Assert: EID 10 appears in draw output.

### GPU tests

**`test_events_mesh_shading_type`** *(skip if `mesh_shading.rdc` absent)*
- Load `mesh_shading.rdc`.
- Call `_call(state, "events")`.
- Assert: the event for EID 10 (`vkCmdDrawMeshTasksEXT`) has `type != "Other"`.

**`test_draws_includes_mesh_shading_eid`** *(skip if fixture absent)*
- Call `_call(state, "draws")`.
- Assert: EID 10 appears in `draws` list.

**`test_info_counts_mesh_draw`** *(skip if fixture absent)*
- Call `_call(state, "info")`.
- Assert: `"Draw Calls"` contains `"1"` (not `"0"`).

---

## Regression tests

**`test_recv_line_eof_still_returns_empty`**
- Existing test in `test_daemon_transport.py`; verify it still passes unchanged.

**`test_recv_line_within_limit`**
- Existing test; verify the small-message path is unaffected by any limit change.

**`test_debug_thread_happy_path`**
- Existing test in `test_debug_handlers.py`; must still pass — the fix must not
  break the successful 2-step trace.

**`test_debug_pixel_error_json_rc1`**
- Already present in `test_debug_commands.py`; must still pass (regression guard
  for `debug pixel`'s `--json` exit-code fix, analogous to B10 for `debug thread`).

**`test_shader_map_basic`**
- Existing test in `test_count_shadermap.py`; must still pass — the Draw-only
  path must not be broken by the B15 fix.

**`test_shader_map_compute_only`**
- Existing test; must still pass — the CS-only path is the canonical positive
  case for B15.

**`test_count_draws`** / **`test_count_dispatches`**
- Existing tests; must still pass to confirm B16 fix does not double-count.

---

## Test matrix

| Test | Type | File | Covers |
|------|------|------|--------|
| `test_recv_line_large_message_at_limit` | unit | `test_daemon_transport.py` | B10 |
| `test_recv_line_large_message_just_over_limit` | unit | `test_daemon_transport.py` | B10 |
| `test_recv_line_multi_chunk_large_valid` | unit | `test_daemon_transport.py` | B10 |
| `test_recv_line_default_limit_is_large_enough_for_debug` | unit | `test_daemon_transport.py` | B10 |
| `test_debug_thread_error_json_rc1` | unit | `test_debug_commands.py` | B10 |
| `test_debug_thread_error_trace_rc1` | unit | `test_debug_commands.py` | B10 |
| `test_debug_thread_error_plain_rc1` | unit | `test_debug_commands.py` | B10 |
| `test_debug_thread_success_json_rc0` | unit | `test_debug_commands.py` | B10 |
| `test_debug_thread_transport_error_json_rc1` | unit | `test_debug_commands.py` | B10 |
| `test_debug_thread_transport_error_plain_rc1` | unit | `test_debug_commands.py` | B10 |
| `test_debug_thread_large_trace_handler_level` | unit | `test_debug_handlers.py` | B10 |
| `test_debug_thread_compute_nbody` | gpu | `test_daemon_handlers_real.py` | B10 |
| `test_shader_map_dispatch_only_populates_cs` | unit | `test_count_shadermap.py` | B15 |
| `test_shader_map_dispatch_no_graphics_shader_leak` | unit | `test_count_shadermap.py` | B15 |
| `test_shader_map_mixed_draw_and_dispatch` | unit | `test_count_shadermap.py` | B15 |
| `test_shader_map_draw_does_not_show_cs` | unit | `test_count_shadermap.py` | B15 |
| `test_shader_map_dispatch_columns_daemon` | unit | `test_count_shadermap.py` | B15 |
| `test_shader_map_compute_nbody_dispatch_columns` | gpu | `test_daemon_handlers_real.py` | B15 |
| `test_mesh_dispatch_action_type_str` | unit | `test_draws_events_daemon.py` | B16 |
| `test_mesh_dispatch_classified_as_draw_in_events` | unit | `test_draws_events_daemon.py` | B16 |
| `test_mesh_dispatch_included_in_draws_list` | unit | `test_draws_events_daemon.py` | B16 |
| `test_mesh_dispatch_counted_as_draw` | unit | `test_draws_events_daemon.py` | B16 |
| `test_mesh_dispatch_in_info_draw_calls` | unit | `test_draws_events_daemon.py` | B16 |
| `test_mesh_dispatch_not_classified_as_dispatch` | unit | `test_draws_events_daemon.py` | B16 |
| `test_count_mesh_dispatch_as_draw` | unit | `test_count_shadermap.py` | B16 |
| `test_shader_map_includes_mesh_dispatch` | unit | `test_count_shadermap.py` | B16 |
| `test_events_mesh_draw_type` | unit | `test_draws_events_cli.py` | B16 |
| `test_draws_mesh_draw_included` | unit | `test_draws_events_cli.py` | B16 |
| `test_events_mesh_shading_type` | gpu | `test_daemon_handlers_real.py` | B16 |
| `test_draws_includes_mesh_shading_eid` | gpu | `test_daemon_handlers_real.py` | B16 |
| `test_info_counts_mesh_draw` | gpu | `test_daemon_handlers_real.py` | B16 |
| `test_recv_line_eof_still_returns_empty` | regression | `test_daemon_transport.py` | B10 |
| `test_recv_line_within_limit` | regression | `test_daemon_transport.py` | B10 |
| `test_debug_thread_happy_path` | regression | `test_debug_handlers.py` | B10 |
| `test_debug_pixel_error_json_rc1` | regression | `test_debug_commands.py` | B10 |
| `test_shader_map_basic` | regression | `test_count_shadermap.py` | B15 |
| `test_shader_map_compute_only` | regression | `test_count_shadermap.py` | B15 |
| `test_count_draws` | regression | `test_count_shadermap.py` | B15/B16 |
| `test_count_dispatches` | regression | `test_count_shadermap.py` | B15/B16 |
