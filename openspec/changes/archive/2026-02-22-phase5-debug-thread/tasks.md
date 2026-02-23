# Tasks: debug thread — compute shader execution trace

## Tasks

- [ ] Add `DebugThread(group, thread)` method and `_debug_thread_map` to `MockReplayController` in `tests/mocks/mock_renderdoc.py`
  - `_debug_thread_map: dict[tuple[int, int, int, int, int, int], ShaderDebugTrace]` keyed by `(gx,gy,gz,tx,ty,tz)`
  - Method signature: `def DebugThread(self, group: tuple[int,int,int], thread: tuple[int,int,int]) -> ShaderDebugTrace`
  - Lookup key assembled as `(*group, *thread)`; fallback to empty `ShaderDebugTrace()`

- [ ] Add `_handle_debug_thread` to `src/rdc/handlers/debug.py`
  - Validate required params: `eid`, `gx`, `gy`, `gz`, `tx`, `ty`, `tz` (return `-32602` for each missing)
  - Validate adapter loaded (return `-32002` if not)
  - Call `_set_frame_event`; propagate error if any
  - Look up action flags via `state.adapter.controller` action list; return `-32602` with `"event is not a Dispatch"` if `ActionFlags.Dispatch` not set
  - Call `controller.DebugThread((gx,gy,gz), (tx,ty,tz))`
  - Return `-32007` if trace is None or trace.debugger is None
  - Run `_run_debug_loop(controller, trace)`; call `_extract_inputs_outputs(steps)`
  - Return result dict with `eid`, `stage` (from `_STAGE_NAMES`), `total_steps`, `inputs`, `outputs`, `trace`
  - Register `"debug_thread": _handle_debug_thread` in `HANDLERS`

- [ ] Add `thread_cmd` subcommand to `src/rdc/commands/debug.py`
  - 7 positional Click arguments: `eid`, `gx`, `gy`, `gz`, `tx`, `ty`, `tz` (all `type=int`)
  - Options: `--trace` / `show_trace`, `--dump-at` / `dump_at`, `--json` / `use_json`, `--no-header`
  - Build params dict and call `_daemon_call("debug_thread", params)`
  - Dispatch to `write_json`, `_print_dump_at`, `_print_trace`, or `_print_summary` (same branching as `pixel_cmd`)
  - Decorate with `@debug_group.command("thread")`

- [ ] Write CLI unit tests in `tests/unit/test_debug_commands.py` (DT-01 through DT-13)
  - Add `_THREAD_HAPPY_RESPONSE`, `_THREAD_EMPTY_TRACE`, `_THREAD_MULTI_CHANGE` fixture dicts
  - Add 13 test functions covering summary, trace TSV, dump-at, JSON, no-header, param forwarding, help, error on missing args, group help

- [ ] Write handler unit tests in `tests/unit/test_debug_handlers.py` (DT-14 through DT-28)
  - Add `_make_dispatch_state(ctrl)` helper that sets up a Dispatch-flagged action at EID 150
  - Add 15 test functions covering happy path, all missing-param errors, no-adapter, out-of-range EID, non-dispatch action, no-trace, multiple batches, source mapping, FreeTrace cleanup, stage name, tuple assembly

- [ ] Write GPU integration tests in `tests/gpu/test_debug_thread_gpu.py` (DT-G01 through DT-G06)
  - Session-scoped `dispatch_eid` fixture that finds first Dispatch action or skips
  - 6 test functions: stage=cs, trace shape, JSON schema, dump-at vars, invalid-eid error, double-call no-leak

- [ ] Run `pixi run lint && pixi run test` — zero failures
