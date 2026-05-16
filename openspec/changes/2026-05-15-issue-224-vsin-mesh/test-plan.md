# Test Plan: issue-224-vsin-mesh

## Scope

### In scope
- Daemon handler `_handle_mesh_data` accepting `vs-in` as a valid stage
- `GetPostVSData` mock keyed at stage int `0` in `mock_renderdoc.py`
- CLI `rdc mesh --stage vs-in` option acceptance and forwarding
- Integration test against a real Vulkan capture (vkcube)

### Out of scope
- Multi-stream IA decoding
- Non-Triangle topology OBJ export
- D3D12 captures (Linux dev box; deferred to reporter verification)
- `GetVertexInputs` / `GetVBuffers` / `GetIBuffer` lower-level fallback

## Test Matrix

| Layer | Test Type | File |
|-------|-----------|------|
| Unit | Handler: vs-in stage accepted, MeshFormat decoded | `tests/unit/test_buffer_decode.py` (extend) |
| Unit | Handler: invalid stage still errors with vs-in in message | `tests/unit/test_buffer_decode.py` (extend) |
| Unit | CLI: `--stage vs-in` forwarded to daemon | `tests/unit/test_mesh_commands.py` (extend) |
| Unit | CLI: `--stage` rejects unknown values | `tests/unit/test_mesh_commands.py` (extend) |
| Integration | Real Vulkan capture: vs-in OBJ export round-trip | `tests/integration/test_daemon_handlers_real.py` (extend) |

## Cases

### Handler: `_handle_mesh_data` with `vs-in`

- **Happy path**: request `{"stage": "vs-in"}` at a valid draw eid → `GetPostVSData` called
  with stage int `0`; response contains vertex positions.
- **Empty MeshFormat (non-draw)**: mock returns `MeshFormat` with zero `vertexResourceId`
  at stage `0` → handler returns JSON-RPC error `-32001` `"no PostVS data at this event"`
  (same contract as `vs-out`/`gs-out`).
- **Invalid stage string**: request `{"stage": "hs-out"}` → error response; error text
  includes `vs-in`, `vs-out`, `gs-out`.

### Mock: `GetPostVSData` at stage 0

- Mock in `tests/mocks/mock_renderdoc.py` stores per-stage `MeshFormat` keyed by stage int.
- Confirm stage key `0` is populated with a minimal `MeshFormat` (position attribute,
  Triangle topology, at least 3 vertices).
- Confirm stage keys `1` and `2` are unaffected.

### CLI: `--stage vs-in`

- Extend `test_mesh_stage_forwarded` in `tests/unit/test_mesh_commands.py`:
  invoke `rdc mesh <eid> --stage vs-in` → assert daemon request contains `"stage": "vs-in"`.
- Invoke `rdc mesh <eid> --stage bad-stage` → assert Click validation error, exit code 2.
- Invoke `rdc mesh <eid>` (no `--stage`) → default behavior unchanged (existing test).

### Integration (`@pytest.mark.gpu`)

- Analogous to `test_mesh_data_real` (~line 1573 in `test_daemon_handlers_real.py`).
- Open a vkcube Vulkan capture; pick a draw eid known to have vertex data.
- Call handler with `stage=vs-in`; assert OBJ output is non-empty and vertex count > 0.
- Assert OBJ contains `v ` lines; count matches reported vertex count from `MeshFormat`.

## Assertions

- Exit code 0 on success, non-zero on error.
- VS-In response vertex count equals the value reported in the returned `MeshFormat`.
- OBJ vertex lines (`v x y z`) are well-formed floats.
- Error messages for invalid stage name appear on stderr and include all three valid stage
  names (`vs-in`, `vs-out`, `gs-out`).
- Coverage gate: `pixi run test` overall coverage stays ≥ 80%.

## Risks

- **Mock key alignment**: `GetPostVSData` mock currently uses stage int keys; confirm key
  `0` is explicitly exercised or the test will silently pass against a wrong code path.
- **D3D12 gap**: integration test runs Vulkan only; D3D12 path is untested on this machine.
  Mitigation: document in test as `# D3D12: verified by @Misaka-Mikoto-Tech on real capture`.
