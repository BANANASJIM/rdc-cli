# Test Plan — Phase 4A: Shader Debug (debug pixel / debug vertex)

## Scope

### In scope
- `_run_debug_loop` shared helper: trace with steps, empty trace, multi-batch merging, FreeTrace called in finally
- `_format_step` / `_format_var_value`: float vec4, uint scalar, int, matrix formatting
- `debug_pixel` handler: happy path, no fragment (error -32007), no adapter (error -32002), eid out of range, multiple batches, source mapping, variable formatting
- `debug_vertex` handler: happy path, no adapter, instance parameter forwarded
- `debug pixel` CLI: default summary, --trace TSV, --dump-at snapshot, --json, --no-header, multiple changes per step, help text
- `debug vertex` CLI: default summary, --trace TSV, --instance forwarded, --json, help text
- `debug` group: --help lists pixel and vertex, no-subcommand shows help
- CLI registration: commands visible in --help
- GPU integration tests on hello_triangle.rdc or vkcube.rdc

### Out of scope
- shader-encodings, shader-build, shader-replace, shader-restore (Phase 4B)
- Performance benchmarking of debug traces
- MSAA-specific debug testing

## Test Matrix

| Layer | Scope | File |
|-------|-------|------|
| Unit | `debug_pixel` handler (7 cases) | `tests/unit/test_debug_handlers.py` |
| Unit | `debug_vertex` handler (3 cases) | `tests/unit/test_debug_handlers.py` |
| Unit | shared helpers (3 cases) | `tests/unit/test_debug_handlers.py` |
| Unit | `debug pixel` CLI command (9 cases) | `tests/unit/test_debug_commands.py` |
| Unit | `debug vertex` CLI command (5 cases) | `tests/unit/test_debug_commands.py` |
| Unit | `debug` group + registration (3 cases) | `tests/unit/test_debug_commands.py` |
| GPU | shader debug on real capture (4 cases) | `tests/integration/test_daemon_handlers_real.py` |

## Cases

### `debug_pixel` handler

1. **Happy path — 3-step trace**: Mock controller with DebugPixel returning trace with debugger, ContinueDebug returning 3 ShaderDebugStates, instInfo with source mapping; verify response has eid, stage="ps", total_steps=3, steps list with step/instruction/file/line/changes
2. **No fragment at pixel**: DebugPixel returns trace with debugger=None; error -32007 "no fragment at pixel"
3. **No adapter**: state.adapter is None; error -32002 "no replay loaded"
4. **EID out of range**: eid > max_eid; error -32002
5. **Multiple batches**: ContinueDebug returns 2 batches of 2 states each; merged into 4 total steps
6. **Source mapping**: instInfo maps instruction indices to file/line; verify file and line fields in steps
7. **Variable formatting**: float vec4, uint scalar — verify value string formatting

### `debug_vertex` handler

8. **Happy path**: DebugVertex returns trace; verify stage="vs", steps present
9. **No adapter**: state.adapter is None; error -32002
10. **Instance parameter forwarded**: params include instance=2; verify DebugVertex called with inst=2

### Shared helpers

11. **_format_var_value float vec4**: ShaderVariable with type VarType.Float, columns=4, rows=1, value.f32v=[1.0, 2.0, 3.0, 4.0] → "1.0 2.0 3.0 4.0"
12. **_format_var_value uint scalar**: columns=1, rows=1, value.u32v=[42] → "42"
13. **FreeTrace in finally**: even when ContinueDebug raises, FreeTrace is called

### `debug pixel` CLI

14. **Default summary output**: mock daemon returns steps with inputs/outputs; output has stage, steps count, inputs line, outputs line
15. **--trace TSV output**: mock daemon returns 3 steps with changes; output has header STEP\tINSTR\tFILE\tLINE\tVAR\tTYPE\tVALUE plus data rows
16. **--trace empty**: daemon returns 0 steps; only header, no data rows
17. **--dump-at snapshot**: daemon returns steps at various lines; --dump-at 22 accumulates variables up to line 22; output has VAR\tTYPE\tVALUE
18. **--dump-at no match**: no step reaches target line; exit 0 with empty output (just header)
19. **--json output**: full JSON structure verified
20. **--no-header with --trace**: suppress TSV header
21. **Multiple changes per step**: one step has 2 variable changes; generates 2 TSV rows
22. **Help text**: `rdc debug pixel --help` exits 0

### `debug vertex` CLI

23. **Default summary**: verify output format
24. **--trace TSV**: verify header + data
25. **--instance forwarded**: --instance 5 is passed to daemon params
26. **--json output**: verified
27. **Help text**: `rdc debug vertex --help` exits 0

### `debug` group + registration

28. **Group help**: `rdc debug --help` lists pixel and vertex subcommands
29. **No subcommand**: `rdc debug` shows help
30. **Commands in main help**: `rdc --help` contains "debug"

## GPU Integration Tests

| # | Test | Setup | Assertion |
|---|------|-------|-----------|
| G1 | `test_debug_pixel_basic` | Find first draw with PS, debug center pixel | steps > 0, each step has instruction/changes |
| G2 | `test_debug_pixel_no_fragment` | Debug pixel at (0, 0) which may have no fragment | error -32007 or valid trace |
| G3 | `test_debug_vertex_basic` | Debug vertex 0 of first draw | steps > 0, stage == "vs" |
| G4 | `test_debug_pixel_source_mapping` | Verify file/line populated in steps | may be empty without debug info |

## Assertions

### Handler contracts
- `debug_pixel` returns {eid, stage, total_steps, inputs, outputs, trace}
- `debug_vertex` returns {eid, stage, total_steps, inputs, outputs, trace}
- Each step: {step, instruction, file, line, changes[]}
- Each change: {name, type, rows, cols, before, after}
- Error -32002 for no adapter / eid out of range
- Error -32007 for no fragment at pixel / debug not available
- FreeTrace always called (even on error) via finally block

### CLI contracts
- Default mode: summary with stage, steps, inputs, outputs
- --trace: TSV with STEP\tINSTR\tFILE\tLINE\tVAR\tTYPE\tVALUE header
- --dump-at: VAR\tTYPE\tVALUE header, accumulated variables up to target line
- --json: full response dict
- --no-header: suppress TSV/dump header

## Risks & Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| Capture has no debug info → empty instInfo | Source file/line will be empty | Gracefully handle missing instInfo; GPU test allows empty source |
| DebugPixel returns None on certain GPUs | Handler crashes | Guard trace is not None before accessing debugger |
| Large shader traces (1000+ steps) | Slow response | No mitigation in 4A; future: add --max-steps |
| ContinueDebug batching differs per GPU | Test expectations fragile | GPU tests check steps > 0, not exact count |
| Rollback | Remove debug.py handler + command, 2 registration lines | Clean removal, no other files affected |
