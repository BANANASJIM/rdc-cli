# Tasks: issue-224-cbuffer-export

## Phase A: Mock API additions

- [ ] Add `GetBufferData` stub to `mock_renderdoc.py` (anchor: ~line 1356 `GetConstantBlock`).
  The happy-path test must give the mock `Descriptor` (returned via
  `GetConstantBlock(...).descriptor`) a non-null `resource`, `byteOffset`, and `byteSize` —
  these are the fields the raw-path handler keys off (`buffer.py:143-147`).
- [ ] Add `bufferBacked=False` variant to the mock `ConstantBlock` for the push-constant
  clean-error test; this stubs the reflection-level field used to reject non-buffer-backed
  cbuffers before `GetBufferData` is called.

## Phase B: `cbuffer_raw` daemon handler (tests first)

- [ ] Extend `tests/unit/test_buffer_decode.py` with `cbuffer_raw` cases (happy path,
  `bufferBacked=False` error, no-adapter guard)
- [ ] Implement `cbuffer_raw` handler in `src/rdc/handlers/buffer.py` (~line 370,
  adjacent to `HANDLERS` dict)
- [ ] Register `cbuffer_raw` in `HANDLERS`
- [ ] Add VFS `leaf_bin` route for `/draws/<eid>/cbuffer/<set>/<binding>/data` →
  `cbuffer_raw` in `src/rdc/vfs/router.py`, mirroring
  `/buffers/<id>/data` → `buf_raw` (router.py:184)
- [ ] Verify handler unit tests pass

## Phase C: `rdc cbuffer` CLI command (tests first)

- [ ] Write `tests/unit/test_cbuffer_commands.py` (JSON mode, `--raw -o`, no-session error,
  `complete_eid` fallback, `--raw` without `-o` usage error)
- [ ] Implement `src/rdc/commands/cbuffer.py`; raw path calls
  `_export_vfs_path(f"/draws/{eid}/cbuffer/{set}/{binding}/data", output, raw)` from
  `commands/export.py` — no direct handler dispatch
- [ ] Register `cbuffer_cmd` in `src/rdc/cli.py` (~line 138, adjacent to `buffer_cmd`)
- [ ] Verify CLI unit tests pass

## Phase D: Integration + verification

- [ ] Extend `tests/integration/test_daemon_handlers_real.py` with `@pytest.mark.gpu`
  tests for `cbuffer_raw` (Vulkan vkcube capture)
- [ ] Run `pixi run lint && pixi run test` — all pass, coverage ≥ 80% for new paths
- [ ] Run GPU integration tests against real capture — pass
- [ ] Code review

## Phase E: Optional polish (non-blocking)

- [ ] Switch `cbuffer_decode` to use `_flatten_shader_var` from `handlers/_helpers.py`
  instead of `_extract_value` to fix int/uint member degradation
- [ ] Extend `test_buffer_decode.py` with int/uint value assertions
