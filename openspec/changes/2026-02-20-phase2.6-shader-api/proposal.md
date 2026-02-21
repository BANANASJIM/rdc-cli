# Phase 2.6 Shader API Fixes

## Summary

Fix three correctness bugs introduced in Phase 2 shader handlers:

1. `shader_source` and `shader_disasm` call non-existent APIs (`GetDebugSource`,
   `GetDisassembly`, `GetShaderDisassembly`). The correct API is
   `DisassembleShader(pipeline, refl, target)` as used in `_build_shader_cache`.

2. `vfs_ls /shaders` and `vfs_tree /shaders` return empty listings because
   `_build_shader_cache` is not triggered before the VFS node is read.

3. `/passes/<name>/draws` is always empty; `build_vfs_skeleton` does not
   populate it with the draw EIDs belonging to each pass.

## Design

### Issue 4 — shader_source / shader_disasm

Replace both handlers with the same pattern as `_build_shader_cache`:

```python
pipe_state = state.adapter.get_pipeline_state()
refl = pipe_state.GetShaderReflection(stage_val)
if refl is None:
    return empty result
pipeline = pipe_state.GetGraphicsPipelineObject()   # stage_val < 5
         / pipe_state.GetComputePipelineObject()    # stage_val == 5
targets = controller.GetDisassemblyTargets(True)
target = str(targets[0]) if targets else "SPIR-V"
disasm = controller.DisassembleShader(pipeline, refl, target)
```

`shader_source` returns `{"source": disasm, "has_debug_info": False}`.
`shader_disasm` uses the caller-supplied `target` param (or first available).

### Issue 5 — /shaders triggers cache build

In `_handle_vfs_ls` and inside `_handle_vfs_tree._subtree`, add a guard:

```python
if path.startswith("/shaders") and not state._shader_cache_built:
    _build_shader_cache(state)
```

Called before the VFS node lookup so the node already has its children.

### Issue 5b — /passes/*/draws populated

Add helper `_collect_pass_draw_eids` to `query_service.py` that mirrors
`_build_pass_list_recursive` but returns `list[int]` of draw/dispatch EIDs
per pass instead of aggregate counts.

`build_vfs_skeleton` calls this helper to populate each pass's `/draws` dir.
