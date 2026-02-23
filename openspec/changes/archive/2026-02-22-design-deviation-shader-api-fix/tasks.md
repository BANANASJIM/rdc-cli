# Tasks: Fix Design Deviations in Shader Handlers

## Phase 1: Verify mock readiness

- [ ] Confirm `ShaderDebugInfo`, `SourceFile`, `ShaderVariable`, `ShaderValue` in
  `tests/mocks/mock_renderdoc.py` match the API reference (no changes expected)
- [ ] Confirm `MockPipeState.GetConstantBlock(stage, slot, array_idx)` returns `Descriptor`
  directly (not a wrapper) — check the Descriptor field layout vs real API
- [ ] Confirm `MockReplayController.GetCBufferVariableContents` signature matches
  the 8-param real API

## Phase 2: Fix `shader_source` handler

- [ ] In `_handle_shader_source`, after obtaining `refl`, check `refl.debugInfo.files`
- [ ] If files non-empty: build `files` list `[{"filename": f.filename, "source": f.contents}]`,
  set `has_debug_info = True`, set `source = ""`
- [ ] If files empty: call `DisassembleShader` as before, set `has_debug_info = False`,
  set `files = []`
- [ ] Update response dict to include both `source` and `files` keys in all branches
- [ ] Handle `refl is None` case: return `source=""`, `files=[]`, `has_debug_info=False`

## Phase 3: Fix `shader_constants` handler

- [ ] Add `_flatten_shader_var(var) -> dict` private helper in `shader.py`:
  - If `var.members` non-empty: recurse, return `{"name": ..., "type": ..., "rows": ...,
    "columns": ..., "value": None, "members": [...]}`
  - Otherwise: select value array from `var.value` (f32v for float types, u32v for uint,
    s32v for int), slice to `rows * columns` elements
  - Return `{"name": ..., "type": ..., "rows": ..., "columns": ..., "value": [...]}`
- [ ] In `_handle_shader_constants`, replace the `GetConstantBuffer` block with:
  - Get `pipe = get_pipeline_for_stage(pipe_state, stage_val)`
  - Get `shader_id = pipe_state.GetShader(stage_val)`
  - Get `entry = pipe_state.GetShaderEntryPoint(stage_val)`
  - Enumerate `refl.constantBlocks` with index `idx`
  - For each: call `pipe_state.GetConstantBlock(stage_val, idx, 0)` → `bound`
  - Call `controller.GetCBufferVariableContents(pipe, shader_id, stage_val, entry,
    idx, bound.resource, bound.byteOffset, bound.byteSize)`
  - Map results through `_flatten_shader_var`
- [ ] Remove the `hasattr(controller, "GetConstantBuffer")` guard entirely
- [ ] Remove `"data"` (hex) field from response; response has `"variables"` list instead
- [ ] Keep `"name"` and `"bind_point"` fields on each cbuffer entry

## Phase 4: Update unit tests

- [ ] In `test_daemon_shader_extended.py`:
  - Update `test_shader_constants` to assert `variables` list (not `data` hex field)
  - Update `test_shader_source` to assert `files` key present in response
- [ ] In `test_daemon_shader_api_fix.py`:
  - Update `test_shader_source_uses_disassemble_shader` to also assert `files == []`
  - Update `test_shader_source_no_reflection_returns_empty` to assert `files == []`
  - Add `test_shader_source_with_debug_info_returns_files` (mock with `SourceFile`)
  - Add `test_shader_source_with_multiple_debug_files`
  - Add `test_shader_constants_returns_structured_variables` (mock `_cbuffer_variables`)
  - Add `test_shader_constants_struct_variable_recurses`
  - Add `test_shader_constants_empty_cbuffer`
  - Add `test_shader_constants_multiple_cbuffers`
  - Add `test_shader_constants_calls_get_cbuffer_variable_contents` (spy test)

## Phase 5: GPU integration tests

- [ ] In `tests/integration/test_daemon_handlers_real.py`:
  - Add `test_shader_source_real_no_debug_info`
  - Add `test_shader_source_real_fields_present`
  - Add `test_shader_constants_real_structured`
  - Add `test_shader_constants_real_no_hex_data`

## Phase 6: Verify

- [ ] `pixi run lint` — clean
- [ ] `pixi run test` — all unit tests pass, zero regressions
- [ ] `pixi run test-gpu` — GPU integration tests pass
