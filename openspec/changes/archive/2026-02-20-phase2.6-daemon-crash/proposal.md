# Phase 2.6: Daemon Crash Fixes (P0)

## Summary

Fix three independent daemon crashes discovered during real-capture testing.

## Motivation

Any unhandled exception in `_handle_request()` kills the TCP server loop, requiring a full daemon restart. These are P0 because they block all subsequent commands.

## Design

### Fix 1: TCP loop exception guard

Wrap `_handle_request()` call at L212 in try/except. On exception, return a JSON-RPC internal error response instead of crashing.

### Fix 2: SDChunk/SDObject iteration

At L1789, `chunk.children` assumes a Python list but real SWIG SDChunk uses `NumChildren()`/`GetChild(i)`. Replace direct iteration with index-based access and use `AsString()`/`AsInt()` for value extraction.

### Fix 3: Counter UUID serialization

At L431, `desc.uuid` may be a SWIG struct (CounterUUID) that is not JSON-serializable. Apply `str()` coercion.

## Files Changed

- `src/rdc/daemon_server.py` — 3 site edits
- `tests/mocks/mock_renderdoc.py` — add NumChildren/GetChild/AsString to SDChunk/SDObject
- `tests/unit/test_daemon_crash_regression.py` — new crash regression tests
