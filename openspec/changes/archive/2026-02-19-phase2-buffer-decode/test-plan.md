# Test Plan: phase2-buffer-decode

## Scope

### In scope
- Daemon handlers: cbuffer_decode, vbuffer_decode, ibuffer_decode
- VFS routes: `/draws/<eid>/cbuffer/...`, `/draws/<eid>/vbuffer`, `/draws/<eid>/ibuffer`
- CLI commands: `rdc cbuffer`, `rdc vbuffer`, `rdc ibuffer`
- Mock API additions: GetCBufferVariableContents, ShaderVariable, VertexInputAttribute
- TSV output formatting

### Out of scope
- Raw buffer export (already done in OpenSpec #1)
- PostVS data (OpenSpec #3)
- Buffer format auto-detection for unknown layouts

## Test Matrix

| Layer | Test Type | Files |
|-------|-----------|-------|
| Unit | Route resolution | test_vfs_router.py |
| Unit | Tree cache expansion | test_vfs_tree_cache.py |
| Unit | Daemon handlers (mock) | test_buffer_decode.py (new) |
| Unit | CLI commands | test_cli_buffer_decode.py (new) |
| Integration | Mock API sync | test_mock_api_sync.py |
| GPU | Real capture decode | test_daemon_handlers_real.py |

## Cases

### cbuffer_decode
- **Happy path**: decode cbuffer at valid eid/set/binding → TSV with variable names+values
- **Nested structs**: ShaderVariable with members → recursive TSV output
- **Multiple cbuffers**: list all constant blocks at set level
- **No shader bound**: eid with no active shader → error
- **Invalid set/binding**: out-of-range → error
- **No adapter**: state.adapter is None → error -32002

### vbuffer_decode
- **Happy path**: decode vertex buffer at valid eid → per-vertex TSV
- **Multiple VBuffers**: multiple bindings → combined output
- **No vertex buffers**: eid with no VBuffer bound → empty/error
- **Various formats**: R32G32B32_FLOAT, R32G32_FLOAT, R8G8B8A8_UNORM

### ibuffer_decode
- **Happy path**: decode index buffer → sequential TSV
- **uint16 format**: 2-byte indices
- **uint32 format**: 4-byte indices
- **No index buffer**: non-indexed draw → error/empty

### CLI commands
- `rdc cbuffer <eid>` → sends request, formats TSV
- `rdc vbuffer <eid>` → sends request, formats TSV
- `rdc ibuffer <eid>` → sends request, formats TSV
- Missing session → error

## Assertions

- Exit code 0 on success, 1 on error
- TSV output: tab-separated, header row, consistent column count
- cbuffer values: correct float/int/vec/mat formatting
- vbuffer: one row per vertex, columns match IA layout
- ibuffer: one row per index, sequential numbering
- Error messages to stderr

## Risks & Rollback

- **GetCBufferVariableContents signature**: Complex 8-parameter API, mock must match exactly.
  Mitigation: test_mock_api_sync.py validates mock vs real.
- **ShaderVariable recursive structure**: Deep nesting possible.
  Mitigation: limit recursion depth to 8, flatten with dot notation.
- **IA format decoding**: Many possible vertex formats.
  Mitigation: start with common formats (R32_FLOAT, R32G32_FLOAT, R32G32B32_FLOAT,
  R32G32B32A32_FLOAT, R8G8B8A8_UNORM), add more as needed.
- Rollback: revert branch, no master changes until PR merge.
