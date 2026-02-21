# Test Plan — Phase 2.6 Shader API Fixes

## Scope

In scope:
- `shader_source` handler correctness (DisassembleShader path)
- `shader_disasm` handler correctness (DisassembleShader path, explicit target)
- `vfs_ls /shaders` triggers `_build_shader_cache` exactly once
- `vfs_tree /shaders` triggers `_build_shader_cache`
- `build_vfs_skeleton` populates `/passes/<name>/draws` with draw EIDs
- Alias nodes under `/passes/<name>/draws/<eid>`

Out of scope:
- GPU integration (no real RenderDoc capture)
- `_build_shader_cache` internals (existing tests cover it)

## Test Matrix

| Layer | Count |
|-------|-------|
| Unit (mock) | 10 |

## Cases

### shader_source

- PS shader bound → source == DisassembleShader output
- No reflection for stage → source == "", has_debug_info == False
- CS stage → uses GetComputePipelineObject (pipeline id == 2)

### shader_disasm

- PS shader → disasm == DisassembleShader output, target == default
- Explicit `target` param passed through to DisassembleShader
- No reflection → disasm == ""

### vfs_ls /shaders

- First call builds cache, state._shader_cache_built == True, children includes shader ID
- Second call does not re-run DisassembleShader (build_count == 0)

### vfs_tree /shaders

- First call builds cache, result includes shader node

### /passes/*/draws

- Pass with two draws → draws node children == ["42", "43"]
- Alias nodes for each draw exist with kind == "alias"
- Draw outside pass range not included
- Pass with no draws → no pass emitted (children == [])
- vfs_ls on /passes/<name>/draws returns 42, 43

## Assertions

- `resp["result"]["source"]` / `resp["result"]["disasm"]` match mock disasm text
- `state._shader_cache_built` True after first /shaders ls/tree call
- `tree.static["/passes/<name>/draws"].children` contains expected EID strings
- Alias node `.kind == "alias"`
- No error keys in response dicts

## Risks

- `_build_pass_list` returns aggregate stats not per-draw EIDs; must add
  separate helper or modify skeleton builder to collect EIDs directly.
