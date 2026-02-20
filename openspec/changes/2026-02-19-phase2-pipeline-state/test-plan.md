# Test Plan: phase2-pipeline-state

## Scope

### In scope
- Daemon handlers: pipe_topology, pipe_viewport, pipe_scissor, pipe_blend, pipe_stencil,
  pipe_vinputs, pipe_samplers, pipe_vbuffers, pipe_ibuffer, postvs
- VFS routes: 10 new leaf routes under `/draws/<eid>/pipeline/` + `/draws/<eid>/postvs`
- Tree cache: pipeline subtree expansion with new child nodes
- Mock API additions: MockPipeState new methods (GetPrimitiveTopology, GetViewport, etc.)
- Mock API sync: new struct pairs in test_mock_api_sync.py

### Out of scope
- CLI convenience commands (access via `rdc cat`)
- Binary output (all text)
- Buffer data decode (OpenSpec #2)

## Test Matrix

| Layer | Test Type | Files |
|-------|-----------|-------|
| Unit | Route resolution | test_vfs_router.py |
| Unit | Tree cache expansion | test_vfs_tree_cache.py |
| Unit | Daemon handlers (mock) | test_pipeline_state.py (new) |
| Integration | Mock API sync | test_mock_api_sync.py |
| GPU | Real capture queries | test_daemon_handlers_real.py |

## Cases

### All handlers (shared pattern)
- **No adapter**: → error -32002
- **EID out of range**: → error -32002
- **Valid EID**: → formatted result

### pipe_topology
- **Happy path**: TriangleList → `{"topology": "TriangleList"}`
- **Other topologies**: LineList, PointList, TriangleStrip

### pipe_viewport
- **Happy path**: → `{x, y, width, height, minDepth, maxDepth}`
- **Default viewport**: typical 1920x1080

### pipe_scissor
- **Happy path**: → `{x, y, width, height, enabled}`
- **Disabled scissor**: enabled=false

### pipe_blend
- **Happy path**: single RT → blend state row
- **Multiple RTs**: → multiple rows
- **Blending disabled**: enabled=false

### pipe_stencil
- **Happy path**: → front/back face states
- **Stencil disabled**: all default ops

### pipe_vinputs
- **Happy path**: POSITION + TEXCOORD → 2-row TSV
- **No vertex inputs**: → empty list
- **Per-instance**: instanceRate > 0

### pipe_samplers
- **Happy path**: per-stage sampler list
- **No samplers**: → empty list

### pipe_vbuffers
- **Happy path**: bound VBuffers → slot/resourceId/offset/size/stride rows
- **No VBuffers**: → empty list

### pipe_ibuffer
- **Happy path**: → resourceId/offset/size/stride
- **No index buffer**: non-indexed draw → null/empty

### postvs
- **Happy path**: → vertex data after VS transform
- **No VS output**: → error

## Assertions

- Exit code 0 on success, 1 on error
- Daemon result dict contains expected fields with correct types
- Numeric values are numbers (not strings)
- Enum values are human-readable strings (not raw ints)
- `rdc cat /draws/<eid>/pipeline/<sub>` returns formatted text output
- Error messages to stderr with appropriate error codes

## Risks & Rollback

- **PipeState method availability**: Some methods may not exist on older RenderDoc versions.
  Mitigation: use `hasattr` guards, return "not available" if missing.
- **GetPostVSData complexity**: Returns MeshFormat with vertex data — more complex than other
  handlers. Mitigation: start with metadata only, add full vertex decode later.
- **Large handler count (10)**: Risk of daemon_server.py becoming too large.
  Mitigation: extract handlers into `rdc/handlers/pipeline.py` module if > 100 lines each.
- Rollback: revert branch, no master changes until PR merge.
