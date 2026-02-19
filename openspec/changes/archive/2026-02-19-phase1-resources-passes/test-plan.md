# Test Plan: phase1-resources-passes

## Test Layers
- **Unit**: 
  - `query_service`: formatting resource lists, building pass trees from Action list.
- **Mock Daemon**: 
  - Validate JSON-RPC responses for `resources`, `resource`, `passes`.
- **CLI**:
  - Argument parsing (`--type` filter for resources?).
  - Error handling (invalid resource ID).
  - Output formatting (TSV/JSON).

## Scenarios
1. **List Resources**:
   - `rdc resources` returns list of textures/buffers.
   - Verify columns: ID, Type, Name, Res, Format.
2. **Resource Details**:
   - `rdc resource 123` returns key-value details.
   - Error on non-existent ID.
3. **List Passes**:
   - `rdc passes` returns indented tree or flat list with depth.
   - Verify hierarchical structure matches mock action tree.

## Regression Risks
- `query_service` logic sharing with existing `count` or `events` commands.
