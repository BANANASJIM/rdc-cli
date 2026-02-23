# Tasks: code-maintainability

## Test-first tasks
- [ ] Write middleware unit tests: `ping`/`status`/`shutdown` pass with `adapter=None`;
      replay-required handlers blocked by middleware with `adapter=None`
      (`tests/test_daemon_server.py`)
- [ ] Write buffer helper unit tests: `_decode_float_components` and `_decode_index_buffer`
      with all widths, edge cases, and golden-value comparisons for the three refactored handlers
      (`tests/test_handlers_buffer.py`)
- [ ] Write `_try_import_from` unit tests: path appended at end on success, removed on failure
      (`tests/test_discover.py`)

## Implementation tasks

### P1-MAINT-1 — adapter guard middleware
- [ ] `daemon_server.py`: in `_handle_request()`, after resolving `handler`, check
      `getattr(handler, "_no_replay", False)`; if False and `state.adapter is None`,
      return `_error_response(request_id, -32002, "no replay loaded"), True` immediately
- [ ] `handlers/core.py`: set `_handle_ping._no_replay = True`,
      `_handle_status._no_replay = True`, `_handle_goto._no_replay = True`,
      `_handle_shutdown._no_replay = True`, `_handle_count._no_replay = True`
      (count already guards internally and handles `adapter=None` paths explicitly)
- [ ] Remove all top-of-function `if state.adapter is None: return _error_response(…), True`
      guards from `handlers/buffer.py`, `handlers/core.py`, `handlers/debug.py`,
      `handlers/descriptor.py`, `handlers/pipe_state.py`, `handlers/pixel.py`,
      `handlers/query.py`, `handlers/script.py`, `handlers/shader.py`,
      `handlers/shader_edit.py`, `handlers/texture.py`, `handlers/vfs.py`
      (~70 to remove; keep 2 in `_helpers.py` internal logic + 2 in `_handle_count` branching)

### P2-MAINT-1 — buffer decode helpers
- [ ] `handlers/buffer.py`: add module-level helpers:
  ```python
  def _decode_float_components(data: bytes, offset: int, comp_width: int, comp_count: int) -> list[float]: ...
  def _decode_index_buffer(data: bytes, stride: int) -> list[int]: ...
  ```
- [ ] Replace the `struct.unpack_from` loops in `_handle_vbuffer_decode` (lines 237-249),
      `_handle_mesh_data` vertex loop (lines 294-308) and index loop (lines 316-322),
      and `_handle_ibuffer_decode` (lines 362-366) with calls to the new helpers

### P2-ARCH-1 — sys.path insertion order
- [ ] `discover.py` `_try_import_from()`: change `sys.path.insert(0, directory)` (line 77)
      to `sys.path.append(directory)`; update the cleanup pop to `sys.path.remove(directory)`

### P2-MAINT-2 — type aliases
- [ ] `daemon_server.py`: add `Handler = TypeAlias` for
      `Callable[[int, dict[str, Any], DaemonState], tuple[dict[str, Any], bool]]`;
      retype `_DISPATCH: dict[str, Handler]`
- [ ] All handler modules: retype `HANDLERS: dict[str, Handler]` (import `Handler` from
      `daemon_server` or define in a shared `_types.py` to avoid circular import)
- [ ] `daemon_server.py`: retype `DaemonState.vfs_tree` from `Any` to `VfsTree | None`
      (import `VfsTree` from `rdc.vfs.tree_cache` inside `TYPE_CHECKING` block)

### Validation
- [ ] `pixi run lint` — zero new warnings
- [ ] `pixi run test` — no regressions, coverage unchanged
