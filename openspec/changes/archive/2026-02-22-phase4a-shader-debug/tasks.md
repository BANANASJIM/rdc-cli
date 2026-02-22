# Phase 4A Shader Debug — Tasks

## Phase A: Tests first

### Mock renderdoc updates
- [ ] In `tests/mocks/mock_renderdoc.py`, add `ShaderEncoding` IntEnum (Unknown=0, DXBC=1, GLSL=2, SPIRV=3, SPIRVAsm=4, HLSL=5, DXIL=6, OpenGLSPIRV=7, OpenGLSPIRVAsm=8, Slang=9)
- [ ] Add `ShaderEvents` IntFlag (NoEvent=0, SampleLoadGather=1, GeneratedNanOrInf=2)
- [ ] Add `DebugPixelInputs` dataclass (sample=0xFFFFFFFF, primitive=0xFFFFFFFF, view=0xFFFFFFFF)
- [ ] Add `LineColumnInfo` dataclass (fileIndex=0, lineStart=0, lineEnd=0, colStart=0, colEnd=0)
- [ ] Add `InstructionSourceInfo` dataclass (instruction=0, lineInfo=LineColumnInfo())
- [ ] Add `SourceVariableMapping` dataclass (name="", type=0, rows=0, columns=0, offset=0, signatureIndex=-1, variables=[])
- [ ] Add `ShaderVariableChange` dataclass (before=ShaderVariable(), after=ShaderVariable())
- [ ] Add `ShaderDebugState` dataclass (stepIndex=0, nextInstruction=0, flags=0, changes=[], callstack=["main"])
- [ ] Add `SourceFile` dataclass (filename="", contents="")
- [ ] Add `ShaderDebugTrace` dataclass (debugger=None, stage=ShaderStage.Pixel, inputs=[], sourceVars=[], instInfo=[], sourceFiles=[], constantBlocks=[], readOnlyResources=[], readWriteResources=[], samplers=[])
- [ ] Add module-level `DebugPixelInputs()` factory and `ShaderCompileFlags()` factory
- [ ] Add MockReplayController: `_debug_pixel_map`, `_debug_vertex_map`, `_debug_states` storage
- [ ] Add MockReplayController methods: `DebugPixel(x, y, inputs)`, `DebugVertex(vtx, inst, idx, view)`, `ContinueDebug(debugger)`, `FreeTrace(trace)`

### Handler unit tests
- [ ] In `tests/unit/test_debug_handlers.py`, create `_make_state()` helper building DaemonState with mock controller (include DebugPixel, DebugVertex, ContinueDebug, FreeTrace, SetFrameEvent on the controller SimpleNamespace)
- [ ] Create `_make_trace(stage, num_steps, source_file, source_lines)` helper to build ShaderDebugTrace with instInfo and debug states
- [ ] Add `test_debug_pixel_happy_path`: 3-step trace → verify response has eid, stage="ps", total_steps=3, steps list
- [ ] Add `test_debug_pixel_no_fragment`: debugger=None → error -32007
- [ ] Add `test_debug_pixel_no_adapter`: state.adapter=None → error -32002
- [ ] Add `test_debug_pixel_eid_out_of_range`: eid=999 > max_eid → error -32002
- [ ] Add `test_debug_pixel_multiple_batches`: 2 batches merged → 4 total steps
- [ ] Add `test_debug_pixel_source_mapping`: instInfo maps to file/line in steps
- [ ] Add `test_debug_pixel_variable_formatting`: float vec4 and uint scalar formatting
- [ ] Add `test_debug_vertex_happy_path`: trace with vertex inputs → stage="vs"
- [ ] Add `test_debug_vertex_no_adapter`: error -32002
- [ ] Add `test_debug_vertex_instance_forwarded`: instance=2 parameter forwarded
- [ ] Add `test_format_var_value_float_vec4`: value formatting test
- [ ] Add `test_format_var_value_uint_scalar`: value formatting test
- [ ] Add `test_free_trace_called_on_error`: FreeTrace called even when ContinueDebug raises

### CLI unit tests
- [ ] In `tests/unit/test_debug_commands.py`, create `_patch(monkeypatch, response)` helper monkeypatching `_daemon_call` in the debug module
- [ ] Create mock response data constants: `_PIXEL_HAPPY_RESPONSE`, `_VERTEX_HAPPY_RESPONSE`
- [ ] Add `test_debug_pixel_default_summary`: verify output has stage, steps, inputs, outputs lines
- [ ] Add `test_debug_pixel_trace_tsv`: --trace flag → TSV header + data rows with STEP\tINSTR\tFILE\tLINE\tVAR\tTYPE\tVALUE
- [ ] Add `test_debug_pixel_trace_empty`: 0 steps → header only
- [ ] Add `test_debug_pixel_dump_at`: --dump-at 22 → accumulated variable snapshot
- [ ] Add `test_debug_pixel_dump_at_no_match`: no step reaches target → empty
- [ ] Add `test_debug_pixel_json`: --json → full JSON structure
- [ ] Add `test_debug_pixel_no_header`: --no-header --trace → no TSV header
- [ ] Add `test_debug_pixel_multiple_changes`: step with 2 changes → 2 TSV rows
- [ ] Add `test_debug_pixel_help`: `rdc debug pixel --help` exits 0
- [ ] Add `test_debug_vertex_default`: verify summary output
- [ ] Add `test_debug_vertex_trace`: --trace TSV output
- [ ] Add `test_debug_vertex_instance_forwarded`: --instance 5 → params include instance=5
- [ ] Add `test_debug_vertex_json`: --json output verified
- [ ] Add `test_debug_vertex_help`: `rdc debug vertex --help` exits 0
- [ ] Add `test_debug_group_help`: `rdc debug --help` lists pixel and vertex
- [ ] Add `test_debug_no_subcommand`: `rdc debug` shows help
- [ ] Add `test_debug_in_main_help`: `rdc --help` contains "debug"

## Phase B: Implementation

### Handler: `src/rdc/handlers/debug.py`
- [ ] Create file with imports: `from __future__ import annotations`, typing, `_helpers` imports
- [ ] Implement `_format_var_value(var)`: reads `.value.f32v[0:columns]` for float, `.value.u32v` for uint, `.value.s32v` for int; rows × columns for matrix
- [ ] Implement `_format_step(state, trace)`: maps ShaderDebugState to dict with step, instruction, file, line, changes
- [ ] Implement `_run_debug_loop(controller, trace) -> list[dict]`: ContinueDebug loop with FreeTrace in finally
- [ ] Implement `_handle_debug_pixel(request_id, params, state)`: validate adapter, _set_frame_event, build DebugPixelInputs, call DebugPixel(x, y, inputs), guard trace.debugger, run debug loop, return result
- [ ] Implement `_handle_debug_vertex(request_id, params, state)`: validate adapter, _set_frame_event, call DebugVertex(vtx_id, instance, params.get("idx", 0), params.get("view", 0)), guard trace.debugger, run debug loop
- [ ] Define `HANDLERS = {"debug_pixel": _handle_debug_pixel, "debug_vertex": _handle_debug_vertex}`

### CLI: `src/rdc/commands/debug.py`
- [ ] Create file with Click group `debug_group`
- [ ] Implement `pixel_cmd`: arguments (eid, x, y), options (--trace, --dump-at, --sample, --primitive, --json, --no-header)
- [ ] Implement default summary mode: stage, steps, inputs, outputs
- [ ] Implement --trace mode: TSV with STEP\tINSTR\tFILE\tLINE\tVAR\tTYPE\tVALUE, one row per variable change
- [ ] Implement --dump-at mode: accumulate variables up to target source line, output VAR\tTYPE\tVALUE
- [ ] Implement `vertex_cmd`: arguments (eid, vtx_id), options (--trace, --dump-at, --instance, --json, --no-header)
- [ ] Add both subcommands to `debug_group`

### Registration
- [ ] In `src/rdc/daemon_server.py`: import `HANDLERS as _DEBUG_HANDLERS` from `rdc.handlers.debug`, add `**_DEBUG_HANDLERS` to `_DISPATCH`
- [ ] In `src/rdc/cli.py`: import `debug_group` from `rdc.commands.debug`, add `main.add_command(debug_group, name="debug")`
- [ ] Verify all Phase A unit tests pass: `pixi run test -k test_debug`

## Phase C: Integration

### GPU integration tests
- [ ] In `tests/integration/test_daemon_handlers_real.py`, add `TestShaderDebugReal` class
- [ ] Add `test_debug_pixel_basic`: find first draw with PS, debug center pixel; assert steps > 0, each step has instruction/changes
- [ ] Add `test_debug_pixel_no_fragment`: debug pixel at (0, 0); assert error -32007 or valid trace
- [ ] Add `test_debug_vertex_basic`: debug vertex 0 of first draw; assert steps > 0, stage == "vs"
- [ ] Add `test_debug_pixel_source_mapping`: verify file/line populated (may be empty without debug info)

### Full test suite
- [ ] Run full unit test suite: `pixi run test` — all tests green, coverage >= 80%
- [ ] Run lint and type check: `pixi run lint` — zero ruff errors, zero mypy strict errors

## Phase D: Verify

- [ ] `pixi run check` passes (= lint + typecheck + test, all green)
- [ ] Archive: move `openspec/changes/2026-02-22-phase4a-shader-debug/` → `openspec/changes/archive/`
- [ ] Update `进度跟踪.md` in Obsidian vault
