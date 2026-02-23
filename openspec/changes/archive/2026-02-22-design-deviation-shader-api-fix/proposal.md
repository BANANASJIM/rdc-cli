# Proposal: Fix Design Deviations in Shader Handlers

## Problem

Two handlers in `src/rdc/handlers/shader.py` deviate from their design specification.

### Deviation 1: `shader_source` ignores debug info (P2)

**Current behavior**: Always calls `controller.DisassembleShader()` and always returns
`has_debug_info: False`, regardless of whether the shader has embedded source files.

**Design spec** (`设计/命令总览.md` line 66): `rdc shader [eid] [stage] --source` should
return "源码（需 debug info，否则 fallback 反汇编）". The handler must check whether debug
info is present and return actual source files when available, falling back to disassembly
only when not. The `has_debug_info` field must accurately reflect reality.

### Deviation 2: `shader_constants` uses wrong API (P2)

**Current behavior**: Calls `controller.GetConstantBuffer(stage_val, bind_point)` which
returns raw binary data. The result is an opaque hex string with no variable names or
types — useless for inspection.

**Design spec** (`设计/API 实现映射.md`): Should use
`controller.GetCBufferVariableContents(pipe, shader_id, stage, entry, cb_idx, resource,
offset, size)` which returns a structured `ShaderVariable` list with names, types, and
decoded values. This is the correct API for returning human-readable constant buffer
contents.

## Solution

### `shader_source` fix

Check `refl.debugInfo.files`. If the list is non-empty, return the source file contents
concatenated (or a list of files), and set `has_debug_info: True`. If the list is empty,
fall back to disassembly as before, with `has_debug_info: False`.

For multi-file debug info, return a `files` list; for single-file or disassembly fallback,
return a single `source` string. The `has_debug_info` flag drives the consumer's behavior.

### `shader_constants` fix

Replace the `GetConstantBuffer` call with `GetCBufferVariableContents` (8 params). For
each cbuffer in `refl.constantBlocks`, resolve the bound descriptor via
`pipe_state.GetConstantBlock(stage_val, idx, 0)` to get the `resource`, `byteOffset`,
and `byteSize`. Then call `GetCBufferVariableContents` and recursively walk the returned
`ShaderVariable` tree to produce structured output.

## Design

### Response shape — `shader_source`

```json
{
  "eid": 10,
  "stage": "ps",
  "has_debug_info": true,
  "files": [
    {"filename": "shader.hlsl", "source": "..."}
  ],
  "source": ""
}
```

When `has_debug_info` is `false`, `files` is `[]` and `source` contains the disassembly.
When `has_debug_info` is `true`, `source` is `""` and `files` contains one or more entries.

### Response shape — `shader_constants`

```json
{
  "eid": 10,
  "stage": "ps",
  "constants": [
    {
      "name": "Globals",
      "bind_point": 0,
      "variables": [
        {"name": "g_Color", "type": "float4", "rows": 1, "columns": 4,
         "value": [1.0, 0.0, 0.0, 1.0]},
        {"name": "g_Transform", "type": "float4x4", "rows": 4, "columns": 4,
         "value": [1.0, 0.0, 0.0, 0.0,  0.0, 1.0, 0.0, 0.0, ...]},
        {"name": "g_Params", "type": "struct", "rows": 0, "columns": 0, "value": null,
         "members": [...]}
      ]
    }
  ]
}
```

### `_flatten_shader_var` helper

A module-private recursive function that converts a `ShaderVariable` (and its `.members`
tree) to a dict. Value selection: if `var.members` is non-empty, recurse; otherwise pick
from `var.value.f32v`, `var.value.u32v`, or `var.value.s32v` according to `var.type`
(float/int/uint heuristic), and slice to `rows * columns` elements.

### `GetCBufferVariableContents` call pattern

```python
pipe = get_pipeline_for_stage(pipe_state, stage_val)
shader_id = pipe_state.GetShader(stage_val)
entry = pipe_state.GetShaderEntryPoint(stage_val)

for idx, cb_def in enumerate(refl.constantBlocks):
    bound = pipe_state.GetConstantBlock(stage_val, idx, 0)
    # GetConstantBlock returns a Descriptor directly — access .resource/.byteOffset/.byteSize
    cbuffer_vars = controller.GetCBufferVariableContents(
        pipe,
        shader_id,
        stage_val,
        entry,
        idx,
        bound.resource,
        bound.byteOffset,
        bound.byteSize,
    )
    variables = [_flatten_shader_var(v) for v in cbuffer_vars]
```

## Files Changed

### Modified
- `src/rdc/handlers/shader.py` — fix `_handle_shader_source` and `_handle_shader_constants`
- `tests/unit/test_daemon_shader_extended.py` — update `test_shader_constants` and
  `test_shader_source` to assert new behavior
- `tests/unit/test_daemon_shader_api_fix.py` — update to assert `has_debug_info` logic
- `tests/mocks/mock_renderdoc.py` — verify `ShaderDebugInfo.files`, `SourceFile`,
  `ShaderVariable`, `ShaderValue` are all already present (no changes expected)
- `tests/integration/test_daemon_handlers_real.py` — add GPU tests for both fixes
