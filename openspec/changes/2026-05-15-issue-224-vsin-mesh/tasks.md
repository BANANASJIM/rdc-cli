# Tasks: issue-224-vsin-mesh

## Phase A: Mock

- [ ] Add stage int `0` entry to `GetPostVSData` mock in `tests/mocks/mock_renderdoc.py`
      with a minimal `MeshFormat` (position attribute, Triangle topology, ≥3 vertices)
- [ ] Verify `test_mock_api_sync.py` still passes after mock change

## Phase B: Daemon handler

- [ ] Add `"vs-in": 0` to `_MESH_STAGE_MAP` in `src/rdc/handlers/buffer.py`
- [ ] Update the invalid-stage error string (~buffer.py:283) to include `vs-in`
- [ ] Extend `tests/unit/test_buffer_decode.py`:
      - happy-path test for `vs-in` stage
      - empty-MeshFormat test for non-draw eid at stage `0`
      - invalid-stage error message includes `vs-in`
- [ ] Run `pixi run test tests/unit/test_buffer_decode.py` — all pass

## Phase C: CLI

- [ ] Add `"vs-in"` to `--stage` Click `Choice` in `src/rdc/commands/mesh.py`
- [ ] Extend `tests/unit/test_mesh_commands.py` with `vs-in` forwarding case
- [ ] Run `pixi run test tests/unit/test_mesh_commands.py` — all pass

## Phase D: Integration + verification

- [ ] Extend `tests/integration/test_daemon_handlers_real.py` with `@pytest.mark.gpu`
      VS-In test analogous to `test_mesh_data_real`
- [ ] Run `pixi run lint && pixi run test` — all pass, coverage ≥ 80%
- [ ] Run GPU integration test against vkcube capture — passes
- [ ] Code review
