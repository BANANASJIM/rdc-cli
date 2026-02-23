# Proposal: debug thread — compute shader execution trace

## Problem

`rdc debug` currently supports pixel and vertex shader debugging, but has no support for
compute shaders. Compute workloads (dispatches) are common in modern rendering pipelines
(skinning, culling, post-processing, ray-march passes). When a compute shader produces
incorrect results, developers have no way to trace execution through the CLI — they must
open the full RenderDoc GUI.

## Solution

Add `rdc debug thread <eid> <gx> <gy> <gz> <tx> <ty> <tz>` as a third subcommand under
the existing `debug` group. The command uses `controller.DebugThread((gx,gy,gz),
(tx,ty,tz))` to obtain a `ShaderDebugTrace`, then runs the same `ContinueDebug` /
`FreeTrace` loop already used by `debug pixel` and `debug vertex`. Output formatting
(summary, `--trace` TSV, `--dump-at`, `--json`) reuses the shared helpers that already
exist in `commands/debug.py` and `handlers/debug.py` without modification.

## Design

### CLI signature

```
rdc debug thread <eid> <gx> <gy> <gz> <tx> <ty> <tz>
                 [--trace] [--dump-at LINE] [--json] [--no-header]
```

Positional arguments:

| Argument | Type | Description |
|----------|------|-------------|
| `eid`    | int  | Event ID of the Dispatch call |
| `gx`     | int  | Workgroup ID X component |
| `gy`     | int  | Workgroup ID Y component |
| `gz`     | int  | Workgroup ID Z component |
| `tx`     | int  | Thread ID within workgroup, X component |
| `ty`     | int  | Thread ID within workgroup, Y component |
| `tz`     | int  | Thread ID within workgroup, Z component |

Options mirror `debug pixel` / `debug vertex`:

| Option | Description |
|--------|-------------|
| `--trace` | Print full execution trace as TSV |
| `--dump-at LINE` | Print variable snapshot at source line |
| `--json` | Print full trace object as JSON |
| `--no-header` | Suppress TSV header row |

### JSON-RPC method

Method name: `debug_thread`

Request params:

```json
{
  "eid": 150,
  "gx": 0, "gy": 0, "gz": 0,
  "tx": 0, "ty": 0, "tz": 0
}
```

Response `result` (identical schema to `debug_pixel` / `debug_vertex`):

```json
{
  "eid": 150,
  "stage": "cs",
  "total_steps": 42,
  "inputs":  [{ "name": "gl_GlobalInvocationID", "type": "uint", "rows": 1, "cols": 3, "before": [0,0,0], "after": [0,0,0] }],
  "outputs": [{ "name": "outBuffer", "type": "float", "rows": 1, "cols": 4, "before": [0,0,0,0], "after": [1.0,2.0,3.0,4.0] }],
  "trace": [ ... ]
}
```

### Validation

The handler validates:

1. Required params present: `eid`, `gx`, `gy`, `gz`, `tx`, `ty`, `tz`.
2. Adapter is loaded (`-32002` if not).
3. EID is in range via `_set_frame_event` (`-32002` if not).
4. The action at `eid` has `ActionFlags.Dispatch` set; if not, return `-32602`
   (`"event is not a Dispatch"`). Use `_get_flat_actions(state)` from `_helpers.py`
   and find the action where `action.eventId == eid`, then check
   `action.flags & ActionFlags.Dispatch`.
5. `DebugThread` returns a non-None trace with a non-None debugger; if not, return
   `-32007` (`"thread debug not available"`).

### Shared memory limitation

RenderDoc's compute shader debugger does not fully simulate shared memory (`groupshared`)
across workgroup threads. The trace will reflect only the calling thread's perspective.
This is a RenderDoc limitation and is documented but not treated as a bug.

### Output format

Default summary:

```
stage:   cs
eid:     150
steps:   42
inputs:  gl_GlobalInvocationID = [0 0 0]
outputs: outBuffer = [1.0 2.0 3.0 4.0]
```

`--trace` TSV:

```
STEP    INSTR   FILE            LINE    VAR                     TYPE    VALUE
0       0       shader.comp     12      gl_GlobalInvocationID   uint    0 0 0
1       1       shader.comp     13      temp                    float   0.5
```

`--dump-at LINE`: variable snapshot accumulated up to that source line.

`--json`: the full result dict serialized as JSON.

## Files Changed

| File | Change |
|------|--------|
| `src/rdc/commands/debug.py` | Add `thread_cmd` subcommand to `debug_group` |
| `src/rdc/handlers/debug.py` | Add `_handle_debug_thread`; register in `HANDLERS` |
| `tests/mocks/mock_renderdoc.py` | Add `_debug_thread_map` and `DebugThread()` to `MockReplayController` |
| `tests/unit/test_debug_commands.py` | Add CLI unit tests for `debug thread` |
| `tests/unit/test_debug_handlers.py` | Add handler unit tests for `debug_thread` |
| `src/rdc/daemon_server.py` | No change — `HANDLERS` dict from `debug.py` is already merged |
