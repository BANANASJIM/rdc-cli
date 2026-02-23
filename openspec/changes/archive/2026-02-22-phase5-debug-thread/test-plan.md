# Test Plan: debug thread — compute shader execution trace

## Unit Tests

### tests/unit/test_debug_commands.py — new `debug thread` CLI tests

All tests monkeypatch `_daemon_call` on `rdc.commands.debug` (same pattern as existing
pixel/vertex tests). Use `CliRunner().invoke(main, ["debug", "thread", ...])`.

**Fixture data:**

`_THREAD_HAPPY_RESPONSE` — 3-step CS trace with `gl_GlobalInvocationID` input and
`outBuffer` output, `stage="cs"`, `eid=150`, `total_steps=3`.

`_THREAD_EMPTY_TRACE` — zero-step response (`total_steps=0`, empty lists).

`_THREAD_MULTI_CHANGE` — one step with two variable changes.

| ID | Test | Assertion |
|----|------|-----------|
| DT-01 | `test_debug_thread_default_summary` | Summary output contains `stage:`, `cs`, `steps:`, `inputs:`, `outputs:` |
| DT-02 | `test_debug_thread_trace_tsv` | `--trace` first line is TSV header; subsequent lines contain variable names; line count = header + changes |
| DT-03 | `test_debug_thread_trace_empty` | `--trace` with zero-step response prints only the TSV header line |
| DT-04 | `test_debug_thread_dump_at` | `--dump-at 13` first line is `VAR\tTYPE\tVALUE`; `gl_GlobalInvocationID` and intermediate var present |
| DT-05 | `test_debug_thread_dump_at_no_match` | `--dump-at 9999` prints header; all accumulated vars present (no early exit) |
| DT-06 | `test_debug_thread_json` | `--json` output parses as JSON; `stage == "cs"`, `total_steps == 3`, keys `trace`/`inputs`/`outputs` present |
| DT-07 | `test_debug_thread_no_header` | `--trace --no-header` first line does NOT start with `STEP\tINSTR` |
| DT-08 | `test_debug_thread_params_forwarded` | Captured params contain `eid=150`, `gx=1`, `gy=2`, `gz=0`, `tx=3`, `ty=4`, `tz=5` |
| DT-09 | `test_debug_thread_method_name` | Captured method name is `"debug_thread"` |
| DT-10 | `test_debug_thread_help` | `--help` output contains `EID`, `GX`, `GY`, `GZ`, `TX`, `TY`, `TZ`, `--trace` |
| DT-11 | `test_debug_thread_missing_arg_exits_nonzero` | Invoking with fewer than 7 positional args exits with code 2 |
| DT-12 | `test_debug_thread_multiple_changes` | `--trace` with two changes in one step produces header + 2 data rows |
| DT-13 | `test_debug_group_help_includes_thread` | `debug --help` output contains `thread` |

### tests/unit/test_debug_handlers.py — new `debug_thread` handler tests

All tests use `_handle_request(_req("debug_thread", {...}), state)` with a `DaemonState`
built from `MockReplayController`. Dispatch actions are set up with
`ActionFlags.Dispatch`.

**Helper additions:**

- `_make_dispatch_state(ctrl)` — like `_make_state` but action has `flags=ActionFlags.Dispatch` and `eventId=150`.

| ID | Test | Assertion |
|----|------|-----------|
| DT-14 | `test_debug_thread_happy_path` | 2-step CS trace; `result.stage == "cs"`, `total_steps == 2`, trace list has 2 entries, inputs/outputs populated |
| DT-15 | `test_debug_thread_missing_eid` | Response error code `-32602`, message contains `"eid"` |
| DT-16 | `test_debug_thread_missing_gx` | Response error code `-32602`, message contains `"gx"` |
| DT-17 | `test_debug_thread_missing_tx` | Response error code `-32602`, message contains `"tx"` |
| DT-18 | `test_debug_thread_no_adapter` | No adapter loaded → error code `-32002` |
| DT-19 | `test_debug_thread_eid_out_of_range` | EID 9999 → error code `-32002` |
| DT-20 | `test_debug_thread_not_a_dispatch` | Action at EID has `ActionFlags.Drawcall` → error code `-32602`, message contains `"not a Dispatch"` |
| DT-21 | `test_debug_thread_no_trace` | `DebugThread` returns empty trace (no debugger) → error code `-32007`, message contains `"thread debug not available"` |
| DT-22 | `test_debug_thread_multiple_batches` | `ContinueDebug` returns 2 batches (2 + 1 states) → `total_steps == 3` |
| DT-23 | `test_debug_thread_source_mapping` | `instInfo` + `sourceFiles` populated → step has correct `file` and `line` |
| DT-24 | `test_debug_thread_free_trace_called_on_success` | `FreeTrace` called exactly once after successful loop |
| DT-25 | `test_debug_thread_free_trace_called_on_exception` | `FreeTrace` still called when `ContinueDebug` raises |
| DT-26 | `test_debug_thread_cs_stage_name` | `trace.stage == ShaderStage.Compute` → result `stage == "cs"` |
| DT-27 | `test_debug_thread_group_and_thread_assembled` | Mock records the `(group, thread)` tuples passed to `DebugThread`; verifies `group == (1,2,3)` and `thread == (4,5,6)` |
| DT-28 | `test_debug_thread_all_required_params` | All 7 params (`eid`, `gx`..`gz`, `tx`..`tz`) missing individually each produce `-32602` |

## GPU Integration Tests

GPU tests require a real RenderDoc capture containing at least one Dispatch event.
These run only under `@pytest.mark.gpu` and require `RENDERDOC_PYTHON_PATH` to be set.

Target file: `tests/gpu/test_debug_thread_gpu.py`

Session-scoped fixture `dispatch_eid` finds the first action with `ActionFlags.Dispatch`
in the capture loaded by the session fixture. If none exists the test is `pytest.skip`-ped.

| ID | Test | Assertion |
|----|------|-----------|
| DT-G01 | `test_debug_thread_returns_cs_stage` | Invoke `debug thread <eid> 0 0 0 0 0 0`; response `stage == "cs"` and `total_steps > 0` |
| DT-G02 | `test_debug_thread_trace_has_steps` | `--trace` output has at least 2 lines (header + 1 step); each line is tab-delimited with 7 fields |
| DT-G03 | `test_debug_thread_json_schema` | `--json` output is valid JSON; contains keys `eid`, `stage`, `total_steps`, `inputs`, `outputs`, `trace` |
| DT-G04 | `test_debug_thread_dump_at_produces_vars` | `--dump-at 1` outputs at least 1 variable row (VAR/TYPE/VALUE columns) |
| DT-G05 | `test_debug_thread_invalid_eid_error` | Non-dispatch EID (e.g. a Draw) returns error; CLI exits non-zero or JSON error code `-32602` |
| DT-G06 | `test_debug_thread_free_trace_no_leak` | Calling `debug thread` twice in sequence does not crash (FreeTrace properly cleans up) |
