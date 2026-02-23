# Test Plan: code-maintainability

## Scope
- In scope: middleware guard, buffer decode helpers, sys.path insertion order, type aliases.
- Out of scope: end-to-end GPU tests (no behaviour change), CLI command tests.

## Test Matrix
- Unit: `tests/test_daemon_server.py` — middleware dispatches no-replay vs replay-required
- Unit: `tests/test_handlers_buffer.py` — extracted helpers produce identical output to original loops
- Unit: `tests/test_discover.py` — `_try_import_from` appends rather than prepends to `sys.path`
- Regression: full `pixi run test` suite must pass with zero delta (all existing tests green)

## Cases

### Middleware (P1-MAINT-1)
- `ping` with `adapter=None` → returns `{"ok": True}`, not `-32002`
- `status` with `adapter=None` → returns status dict, not `-32002`
- `goto` with `adapter=None` → propagates to `_set_frame_event` (existing behaviour)
- `shutdown` with `adapter=None` → returns `{"ok": True}`, not `-32002`
- Any replay-required method (`buf_info`, `tex_info`, `shader_list`, …) with `adapter=None`
  → middleware returns `-32002 "no replay loaded"` before handler is called
- Any replay-required method with `adapter` set → handler is called normally

### Buffer decode helpers (P2-MAINT-1)
- `_decode_float_components` with `comp_width=4`: returns same floats as original `struct.unpack_from("<f", …)`
- `_decode_float_components` with `comp_width=2`: returns same values as `struct.unpack_from("<e", …)`
- `_decode_float_components` with `comp_width=1`: returns `data[off] / 255.0`
- `_decode_float_components` with out-of-bounds offset: returns `0.0` without raising
- `_decode_index_buffer` with `stride=2`: unpacks `<H` values
- `_decode_index_buffer` with `stride=4`: unpacks `<I` values
- `_handle_vbuffer_decode` output unchanged vs pre-refactor (golden-value comparison)
- `_handle_ibuffer_decode` output unchanged vs pre-refactor
- `_handle_mesh_data` vertex and index output unchanged vs pre-refactor

### sys.path order (P2-ARCH-1)
- After successful `_try_import_from(path)`, `path` appears at the **end** of `sys.path`,
  not at index 0
- Failed import still removes the directory from `sys.path` entirely

### Type aliases (P2-MAINT-2)
- `mypy --strict` passes on `daemon_server.py` with `Handler` alias in place
- `DaemonState.vfs_tree` annotated `VfsTree | None`; assigning wrong type raises mypy error
