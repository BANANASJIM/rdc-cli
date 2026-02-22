# Feature: phase4a-shader-debug

## Summary

Two new daemon handlers (`debug_pixel`, `debug_vertex`) and two new CLI subcommands
under a new `rdc debug` Click group. Both commands invoke RenderDoc's shader debugger,
step through the trace to completion via `ContinueDebug`, and present results as a
summary, a TSV step trace, a variable snapshot at a source line, or full JSON.

The daemon side shares a `_run_debug_loop(controller, trace)` helper that repeatedly
calls `ContinueDebug(trace.debugger)` until an empty state list is returned, collecting
all `ShaderDebugState` steps. Source line information is extracted from
`trace.instInfo[state.nextInstruction].lineInfo`; variable changes are decoded from
`state.changes[]` using the `f32v`/`u32v`/`s32v` union fields based on the variable's
type and row/column count.

This is the first feature to introduce a Click command group (`rdc debug`), which
becomes the model for future grouped commands.

## Problem

Shader debugging in RenderDoc today is GUI-only. CI pipelines and automated regression
suites have no programmatic way to:

1. Confirm which fragment shader executed at a given pixel and capture its
   input/output variable values.
2. Step through vertex shader execution for a specific vertex and inspect intermediate
   register states.
3. Map execution steps to source lines to pinpoint divergence between shader versions.

The `debug pixel` and `debug vertex` commands expose the full trace programmatically,
enabling regression detection (e.g. output colour change), performance analysis
(step count growth), and automated bisection when a shader modification breaks
rendering.

## Design References

- `设计/命令总览.md` — debug pixel, debug vertex are Phase 4A
- `规划/Roadmap.md` — Phase 4: Debug + Replay
- `工程/API-probe-v1.41.md` — verified API behaviour (probe script: `scripts/probe_phase4_api.py`)

## Design

### Daemon handler: `debug_pixel`

JSON-RPC method name: `debug_pixel`

Parameters:
```json
{"eid": int, "x": int, "y": int, "sample": int, "primitive": int}
```

`sample` and `primitive` default to `0xFFFFFFFF` (RenderDoc sentinel for "auto-select").

Algorithm:
1. Validate replay loaded; raise `-32002` if not.
2. Validate `eid` in `[1, event_count]`; raise `-32002` if out of range.
3. Call `controller.SetFrameEvent(eid, True)`.
4. Build `inputs = rd.DebugPixelInputs(); inputs.sample = sample; inputs.primitive = primitive`.
5. Call `trace = controller.DebugPixel(x, y, inputs)` — **3 args, not 4**.
6. If `trace.debugger is None`, raise `-32007` ("no fragment at pixel").
7. Call `_run_debug_loop(controller, trace)` → `steps: list[StepDict]`.
8. Call `controller.FreeTrace(trace)` — **pass trace object, not trace.debugger**.
9. Return result dict (see Response below).

Error codes:

| Code | Condition |
|------|-----------|
| `-32002` | No replay loaded, or `eid` out of range |
| `-32006` | Debug loop exceeds timeout (> 50 000 steps) |
| `-32007` | `trace.debugger is None` (no fragment at pixel), or debug API unavailable |

### Daemon handler: `debug_vertex`

JSON-RPC method name: `debug_vertex`

Parameters:
```json
{"eid": int, "vtx_id": int, "instance": int, "idx": int, "view": int}
```

`instance`, `idx`, `view` default to `0`.

Algorithm:
1. Validate replay loaded; raise `-32002` if not.
2. Validate `eid` in `[1, event_count]`; raise `-32002` if out of range.
3. Call `controller.SetFrameEvent(eid, True)`.
4. Call `trace = controller.DebugVertex(vtx_id, instance, idx, view)` — **4 args**.
5. If `trace.debugger is None`, raise `-32007` ("debug unavailable for vertex").
6. Call `_run_debug_loop(controller, trace)` → `steps: list[StepDict]`.
7. Call `controller.FreeTrace(trace)`.
8. Return result dict.

Error codes: same table as `debug_pixel`.

### Shared helper: `_run_debug_loop`

```python
def _run_debug_loop(controller, trace) -> list[StepDict]:
    """Step through a shader debug trace to completion."""
    steps: list[StepDict] = []
    MAX_STEPS = 50_000
    while True:
        states = controller.ContinueDebug(trace.debugger)
        if not states:
            break
        for state in states:
            steps.append(_format_step(state, trace))
            if len(steps) > MAX_STEPS:
                raise DebugTimeoutError
    return steps
```

`ContinueDebug` returns a batch of `ShaderDebugState` objects per call; loop until
the returned list is empty.

### Step dict format (`_format_step`)

```python
StepDict = TypedDict("StepDict", {
    "step": int,          # state.stepIndex
    "instruction": int,   # state.nextInstruction
    "file": str,          # lineInfo.fileIndex resolved to filename, or ""
    "line": int,          # lineInfo.lineStart, or -1
    "changes": list[ChangeDict],
})

ChangeDict = TypedDict("ChangeDict", {
    "name": str,          # change.after.name
    "type": str,          # change.after.type (string repr)
    "rows": int,          # change.after.rows
    "cols": int,          # change.after.columns
    "before": list[float | int],  # flattened rows*cols values
    "after":  list[float | int],
})
```

Variable value decoding: inspect `ShaderVariable.type`; if float → read `f32v`,
if uint → read `u32v`, else read `s32v`. Flatten `rows × columns` elements into a
plain list.

Source line resolution: `trace.instInfo[instruction].lineInfo` provides `fileIndex`
and `lineStart`. Resolve `fileIndex` against `trace.sourceFiles[fileIndex].filename`
(empty string if out of range or no source files).

Note: `idx` and `view` default to 0 in the daemon handler and are not exposed as CLI
options in Phase 4A. They exist as daemon-level params for future extensibility.

### Response format (both handlers)

```json
{
  "stage": "ps",
  "eid": 120,
  "total_steps": 80,
  "inputs": [
    {"name": "fragCoord", "type": "float", "rows": 1, "cols": 4,
     "before": [], "after": [512.5, 384.5, 0.0, 1.0]}
  ],
  "outputs": [
    {"name": "outColor", "type": "float", "rows": 1, "cols": 4,
     "before": [], "after": [0.5, 0.3, 0.1, 1.0]}
  ],
  "trace": [
    {"step": 0, "instruction": 0, "file": "shader.glsl", "line": 12,
     "changes": [{"name": "x", "type": "float", "rows": 1, "cols": 1,
                  "before": [0.0], "after": [1.0]}]}
  ]
}
```

`inputs` = changes at step 0 (initial register state).
`outputs` = changes in the final step.
`trace` = full step list from `_run_debug_loop`.

### CLI command group: `rdc debug`

`debug` is a Click group. All subcommands live under it:

```
rdc debug pixel <eid> <x> <y> [OPTIONS]
rdc debug vertex <eid> <vtx_id> [OPTIONS]
```

### Command 1: `rdc debug pixel`

```
rdc debug pixel <eid> <x> <y>
    [--trace]
    [--dump-at LINE]
    [--sample N]
    [--primitive N]
    [--json]
    [--no-header]
```

Options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--trace` | flag | off | Emit full TSV step trace |
| `--dump-at LINE` | int | — | Print variable snapshot accumulated up to first occurrence of source line LINE |
| `--sample N` | int | `0xFFFFFFFF` | MSAA sample index |
| `--primitive N` | int | `0xFFFFFFFF` | Primitive override |
| `--json` | flag | off | Full JSON output |
| `--no-header` | flag | off | Suppress header row in TSV mode |

### Command 2: `rdc debug vertex`

```
rdc debug vertex <eid> <vtx_id>
    [--trace]
    [--dump-at LINE]
    [--instance N]
    [--json]
    [--no-header]
```

Options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--trace` | flag | off | Emit full TSV step trace |
| `--dump-at LINE` | int | — | Print variable snapshot at source line LINE |
| `--instance N` | int | `0` | Instance index |
| `--json` | flag | off | Full JSON output |
| `--no-header` | flag | off | Suppress header row in TSV mode |

### Output modes (both commands)

**Default (summary):**
```
stage:   ps
eid:     120
steps:   80
inputs:  fragCoord = [512.5, 384.5, 0.0, 1.0]
outputs: outColor = [0.5, 0.3, 0.1, 1.0]
```

**`--trace` (TSV):**

One row per variable change, across all steps:
```
STEP	INSTR	FILE	LINE	VAR	TYPE	VALUE
0	0	shader.glsl	12	fragCoord	float	512.5 384.5 0.0 1.0
1	4	shader.glsl	15	x	float	1.0
```

Header suppressed with `--no-header`.

**`--dump-at LINE`:**

Accumulate a variable→value map (last-write wins) across all steps up to and
including the first step whose `line == LINE`. Print as TSV snapshot (no STEP/INSTR
columns):
```
VAR	TYPE	VALUE
fragCoord	float	512.5 384.5 0.0 1.0
x	float	1.0
```

If `LINE` is never reached in the trace, exit 0 with empty output (header only if
`--no-header` is not set).

**`--json`:**

Dump the raw daemon response JSON to stdout.

### Daemon-side error → CLI exit code mapping

| Daemon error code | CLI exit code | Message printed |
|-------------------|---------------|-----------------|
| `-32002` | 1 | `error: <message>` on stderr |
| `-32006` | 1 | `error: debug timeout` on stderr |
| `-32007` | 1 | `error: <message>` on stderr |
| network/session | 1 | `error: <message>` on stderr |

## Changes

### New files

| File | Description |
|------|-------------|
| `src/rdc/handlers/debug.py` | `debug_pixel`, `debug_vertex` handlers + `_run_debug_loop` + `_format_step` |
| `src/rdc/commands/debug.py` | `debug` Click group + `pixel` and `vertex` subcommands |
| `tests/unit/test_debug_handlers.py` | ~50 unit tests for both daemon handlers |
| `tests/unit/test_debug_commands.py` | ~50 unit tests for both CLI commands |

### Modified files

| File | Change |
|------|--------|
| `src/rdc/cli.py` | Import + register `debug` group |
| `src/rdc/daemon_server.py` | Register `debug_pixel`, `debug_vertex` dispatch entries |
| `tests/mocks/mock_renderdoc.py` | Add `DebugPixel`, `DebugVertex`, `ContinueDebug`, `FreeTrace`, `DebugPixelInputs` stubs |
| `tests/integration/test_daemon_handlers_real.py` | GPU integration tests for both handlers |

## Scope

| Component | Lines |
|-----------|-------|
| `src/rdc/handlers/debug.py` | ~120 |
| `src/rdc/commands/debug.py` | ~130 |
| `src/rdc/cli.py` (registration) | ~4 |
| `src/rdc/daemon_server.py` (dispatch) | ~4 |
| `tests/mocks/mock_renderdoc.py` (stubs) | ~40 |
| `tests/unit/test_debug_handlers.py` | ~250 |
| `tests/unit/test_debug_commands.py` | ~250 |
| GPU integration tests | ~80 |
| **Total** | **~878** |

### In scope

- `debug_pixel` daemon handler with `-32002`/`-32006`/`-32007` error codes
- `debug_vertex` daemon handler with the same error codes
- `_run_debug_loop` shared helper with 50 000-step timeout guard
- `_format_step` with f32v/u32v/s32v dispatch and source line resolution
- `rdc debug` Click group (first command group in codebase)
- `rdc debug pixel` with `--trace`, `--dump-at`, `--sample`, `--primitive`, `--json`, `--no-header`
- `rdc debug vertex` with `--trace`, `--dump-at`, `--instance`, `--json`, `--no-header`
- TSV output mode for `--trace` and `--dump-at`
- Mock stubs for `DebugPixel`, `DebugVertex`, `ContinueDebug`, `FreeTrace`, `DebugPixelInputs`
- Unit tests (~100 cases) and GPU integration tests

### Out of scope

- `debug thread` / `debug mesh` (Phase 4B or later)
- `BuildTargetShader` / `ReplaceResource` shader replacement (Phase 4B)
- Source file content retrieval or inline source display
- Breakpoint-style partial stepping (always run to completion)
- SPIR-V disassembly output
