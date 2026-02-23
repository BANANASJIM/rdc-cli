# Proposal: code-maintainability

## Goal
Eliminate boilerplate and type imprecision that has accumulated across handlers and core modules,
reducing noise in diffs and making future handler additions harder to get wrong.

## Scope
- **P1-MAINT-1**: Add replay-required middleware in `_handle_request()` (`daemon_server.py`).
  Mark the ~5 handlers that do NOT need a loaded adapter (`ping`, `status`, `goto`, `shutdown`,
  and the no-replay branch of `count`) with a `_no_replay = True` attribute. Remove ~70 of the
  74 total `if state.adapter is None` top-of-function guards from handler files (keep 2 in
  `_helpers.py` for internal logic, and 2 in `_handle_count` for its adapter/no-adapter
  branching).
- **P2-MAINT-1**: Extract `_decode_float_components(data, offset, comp_width, comp_count)`
  and `_decode_index_buffer(data, stride)` helpers in `handlers/buffer.py`; replace the
  duplicated `struct.unpack_from` loops in `_handle_vbuffer_decode`, `_handle_mesh_data`,
  and `_handle_ibuffer_decode`.
  **Intentional behavior change**: `_handle_mesh_data` currently returns `0.0` silently for
  `comp_width == 1` (byte components). The new helper will normalize byte values as
  `data[off] / 255.0`, matching the behavior already present in `_handle_vbuffer_decode`.
  The original silent-zero behavior was a latent bug. Golden-value tests for `_handle_mesh_data`
  must account for this correction.
- **P2-ARCH-1**: In `discover.py` `_try_import_from()`, use `sys.path.append()` instead of
  `sys.path.insert(0, …)` so the renderdoc directory never shadows stdlib or project modules.
- **P2-MAINT-2**: In `daemon_server.py`, define a `Handler` TypeAlias for the handler callable
  signature; change `_DISPATCH` and per-module `HANDLERS` dicts from `dict[str, Any]` to
  `dict[str, Handler]`. Tighten `DaemonState.vfs_tree` from `Any` to `VfsTree | None`.

## Non-goals
- Changing handler semantics, JSON-RPC protocol, or public CLI behavior.
- Splitting handler modules further or reorganising the package layout.
- Adding new commands or tests beyond coverage of the changes above.

## Dependencies
- Must be implemented **after `security-hardening-2` is merged** — both PRs touch
  `daemon_server.py` and `handlers/` files; merge order avoids conflicts.
