# Test Plan: Fix Design Deviations in Shader Handlers

## Scope

- **In scope**: Unit tests for `shader_source` debug-info branching and `shader_constants`
  structured variable output. GPU integration tests verifying both handlers against a real
  capture.
- **Out of scope**: Tests for other shader handlers (`shader_disasm`, `shader_reflect`,
  `shader_targets`, `shader_all`, `shader_list_info`, `shader_list_disasm`). No changes
  to those handlers.

## Test Matrix

| Layer | GPU? | File | What |
|-------|------|------|------|
| Unit | No | `test_daemon_shader_extended.py` | Update existing shader_source / shader_constants tests |
| Unit | No | `test_daemon_shader_api_fix.py` | Update debug-info branching tests; add structured-vars tests |
| Integration | Yes | `test_daemon_handlers_real.py` | GPU tests for both fixes against vkcube.rdc |

## Unit Tests — `shader_source`

### `test_shader_source_no_debug_info_returns_disasm`
Setup: PS shader with `debugInfo.files = []`.
Assert: `result["has_debug_info"] is False`, `result["source"]` contains disassembly text,
`result["files"] == []`.

### `test_shader_source_with_debug_info_returns_files`
Setup: PS shader with `debugInfo.files = [SourceFile(filename="main.hlsl", contents="void main() {}")]`.
Assert: `result["has_debug_info"] is True`, `result["files"]` has one entry with
`filename == "main.hlsl"` and `source == "void main() {}"`, `result["source"] == ""`.

### `test_shader_source_with_multiple_debug_files`
Setup: PS shader with two `SourceFile` entries in `debugInfo.files`.
Assert: `result["files"]` has length 2, both filenames present, `has_debug_info is True`.

### `test_shader_source_no_reflection_returns_empty`
(Existing test — must still pass unchanged: `source == ""`, `has_debug_info is False`.)

### `test_shader_source_uses_disassemble_shader` (existing)
Must still pass. With no debug files, disassembly path is taken.

### `test_shader_source_compute_uses_compute_pipeline` (existing)
Must still pass. No debug files in setup, so disassembly path.

## Unit Tests — `shader_constants`

### `test_shader_constants_returns_structured_variables`
Setup: PS shader with one `ConstantBlock("Globals", fixedBindNumber=0)`. Pre-populate
`ctrl._cbuffer_variables[(ShaderStage.Pixel, 0)]` with:
```python
[ShaderVariable(name="g_Color", type="float4", rows=1, columns=4,
                value=ShaderValue(f32v=[1.0, 0.5, 0.0, 1.0] + [0.0]*12))]
```
Assert: `result["constants"][0]["name"] == "Globals"`,
`result["constants"][0]["variables"][0]["name"] == "g_Color"`,
`result["constants"][0]["variables"][0]["value"] == [1.0, 0.5, 0.0, 1.0]` (4 elements),
`result["constants"][0]["variables"][0]["type"] == "float4"`.

### `test_shader_constants_struct_variable_recurses`
Setup: One cbuffer with a nested struct `ShaderVariable` (has `.members` with two child
`ShaderVariable`s, no `.value`).
Assert: top-level variable has `"members"` key with length 2; leaf members have `"value"`.

### `test_shader_constants_empty_cbuffer`
Setup: One `ConstantBlock` but `ctrl._cbuffer_variables` has no entry for that slot
(returns `[]` from `GetCBufferVariableContents`).
Assert: `result["constants"][0]["variables"] == []`.

### `test_shader_constants_multiple_cbuffers`
Setup: Two `ConstantBlock`s in `refl.constantBlocks`. Each has one variable in mock.
Assert: `result["constants"]` has length 2, each entry has correct `name` and one variable.

### `test_shader_constants_calls_get_cbuffer_variable_contents`
Spy on `ctrl.GetCBufferVariableContents`. Verify it is called (not `GetConstantBuffer`).
Assert: spy called at least once; `GetConstantBuffer` is NOT called.

### `test_shader_constants_invalid_stage` (existing — must pass)
### `test_shader_constants_no_adapter` (existing — must pass)

## GPU Integration Tests

Add to `TestDaemonHandlersReal` in `tests/integration/test_daemon_handlers_real.py`.
Use the existing `vkcube.rdc` fixture. Find a draw EID with a PS shader bound.

### `test_shader_source_real_no_debug_info`
Call `shader_source` on a PS stage of vkcube.rdc. Since vkcube is compiled without debug
info, assert: `result["has_debug_info"] is False`, `result["source"]` is non-empty string
(disassembly), `result["files"] == []`.

### `test_shader_source_real_fields_present`
Assert response contains all required keys: `eid`, `stage`, `has_debug_info`, `source`,
`files`.

### `test_shader_constants_real_structured`
Call `shader_constants` on a PS stage. Assert: `result["constants"]` is a list;
each entry has `name`, `bind_point`, `variables`; `variables` is a list (may be empty
if no cbuffer bound, but must not be a hex string).

### `test_shader_constants_real_no_hex_data`
Assert that no entry in `result["constants"]` contains a `"data"` key (old hex field
must be gone entirely).

## Mock Verification

Confirm existing mock types suffice (no mock changes expected):
- `ShaderDebugInfo` has `files: list` field
- `SourceFile` has `filename: str` and `contents: str`
- `ShaderVariable` has `name`, `type`, `rows`, `columns`, `value`, `members`
- `ShaderValue` has `f32v`, `u32v`, `s32v` lists
- `MockPipeState.GetConstantBlock(stage, slot, array_idx)` returns `Descriptor`
- `MockReplayController.GetCBufferVariableContents(...)` returns from `_cbuffer_variables`
- `MockReplayController` does NOT have `GetConstantBuffer` (so the old `hasattr` guard
  will naturally test the fallback path if needed)

## Regression Guard

All tests in `test_daemon_shader_extended.py` and `test_daemon_shader_api_fix.py` must
continue to pass. The `shader_disasm` handler is unchanged and its tests must pass without
modification.

Run: `pixi run lint && pixi run test`
