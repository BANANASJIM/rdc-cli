# Test Plan: phase2.6-pipeline-extended

## Scope

**In:**
- Unit tests for all 4 new daemon handlers
- VFS tree includes new pipeline children
- Router resolves new paths correctly

**Out:**
- GPU integration tests (real renderdoc capture required, deferred)
- D3D/GL API paths

## Test Matrix

| Layer       | Tool      | Coverage target |
|-------------|-----------|-----------------|
| unit/mock   | pytest    | all 4 handlers  |
| router      | pytest    | 4 new routes    |
| tree cache  | pytest    | 4 new children  |

## Cases

### pipe_push_constants
- Happy path: stage with push constant range returns `{stage, offset, size}`
- No push constants: empty list returned
- No adapter: error -32002
- Stage with no shader bound: skipped

### pipe_rasterizer
- Happy path: rasterizer present, fields serialized correctly
- Enum fields use `.name`
- No rasterizer attribute: returns `{eid}` only
- No adapter: error -32002

### pipe_depth_stencil
- Happy path: depthStencil present, fields serialized correctly
- Enum field (depthFunction) uses `.name`
- No depthStencil attribute: returns `{eid}` only
- No adapter: error -32002

### pipe_msaa
- Happy path: multisample present, numeric fields returned
- No multisample attribute: returns `{eid}` only
- No adapter: error -32002

### Router
- `/draws/10/pipeline/push-constants` -> handler=pipe_push_constants, eid=10
- `/draws/10/pipeline/rasterizer` -> handler=pipe_rasterizer, eid=10
- `/draws/10/pipeline/depth-stencil` -> handler=pipe_depth_stencil, eid=10
- `/draws/10/pipeline/msaa` -> handler=pipe_msaa, eid=10

### VFS Tree
- `build_vfs_skeleton` produces nodes for all 4 new children

## Assertions

- exit code 0, no error key in response
- result contains `eid` field
- push_constants list entries have `stage`, `offset`, `size`
- rasterizer/depth-stencil enum fields are strings, not ints
- msaa numeric fields are int/float

## Risks & Rollback

- Real API attribute names differ from mock: handled with `getattr(..., None)` guards
- Rollback: revert commits on this branch, no schema breakage
