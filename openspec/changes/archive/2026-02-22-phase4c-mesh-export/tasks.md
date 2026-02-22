# Phase 4C-1: Mesh Export — Tasks

## Implementation

- [x] T1: Create openspec
- [ ] T2: Update mock — enhance GetPostVSData, add MeshDataStage, wire GetBufferData
- [ ] T3: Implement `_handle_mesh_data` in `buffer.py`, register in HANDLERS
- [ ] T4: Implement `mesh_cmd` in new `src/rdc/commands/mesh.py` with OBJ formatter
- [ ] T5: Register `mesh_cmd` in `cli.py`
- [ ] T6: Write handler unit tests (`test_mesh_handler.py`)
- [ ] T7: Write CLI unit tests (`test_mesh_commands.py`)
- [ ] T8: Add GPU integration tests
- [ ] T9: `pixi run lint && pixi run test` — zero failures
- [ ] T10: Code review
- [ ] T11: Commit + Push + PR

## Files

### New
- `src/rdc/commands/mesh.py`
- `tests/unit/test_mesh_handler.py`
- `tests/unit/test_mesh_commands.py`

### Modified
- `src/rdc/handlers/buffer.py` — add handler + HANDLERS entry
- `src/rdc/cli.py` — register mesh_cmd
- `tests/mocks/mock_renderdoc.py` — GetPostVSData enhancement
- `tests/integration/test_daemon_handlers_real.py` — GPU tests
