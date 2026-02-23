# Proposal: Mock Accuracy Improvements (Track A)

## Problem

`tests/mocks/mock_renderdoc.py` has several inaccuracies that produce false-positive unit
tests — code that passes the mock but would fail against the real RenderDoc SWIG API.

Root cause: mocks are too permissive, allowing attribute access and behavior that real
objects do not provide.

## Specific Issues

| ID | Mock Inaccuracy | Real API Behavior |
|----|----------------|-------------------|
| T1 | `ResourceId.value` is a real attribute | Real SWIG object has no `.value`; `int(rid)` is the only interface |
| T2 | `SaveTexture` always returns `True` | Can fail; callers must handle `False` return |
| T3 | `GetTextureData`/`GetBufferData` ignore resource_id/offset/length | Real API returns different data per resource; errors are possible |
| T4 | `ContinueDebug` pops batches (consumable, destructive) | Real API steps forward but does not consume data; calling twice should be replayable |
| T5 | `FreeTrace` is a no-op with no tracking | Double-free is detectable; tests should be able to assert correct usage |

## Proposed Changes

### T1 — ResourceId.value → AttributeError
Rename the `value` field in the `ResourceId` dataclass to `_id` (private). Update
`__int__`, `__eq__`, and `__hash__` to use `self._id`. Constructor `ResourceId(42)`
continues to work via positional argument. Any test that accessed `.value` was hiding a real bug.

### T2 — SaveTexture configurable failure
Add `_save_texture_fails: bool = False` to `MockReplayController`. When `True`,
`SaveTexture` returns `False`. Tests can set this to validate error-path handling.

### T3 — GetTextureData/GetBufferData configurable map
Add `_texture_data: dict[int, bytes]` and `_buffer_data: dict[int, bytes]` dicts.
`GetTextureData(rid, sub)` returns `_texture_data.get(int(rid), default_bytes)`.
`GetBufferData(rid, offset, length)` returns `_buffer_data.get(int(rid), default_bytes)[offset:offset+length]`.
Add `_raise_on_texture_id: set[int]` and `_raise_on_buffer_id: set[int]` for error injection.

### T4 — ContinueDebug index-based semantics
Replace the consumable `pop(0)` with index-based access. The real API steps forward each call
but does not destroy data — tests calling the mock twice (e.g., in setup/teardown) should not
lose state. Add `_debug_step_index: dict[int, int]` tracking current step per debugger.
`ContinueDebug` returns `_debug_states[key][index]` and increments index. Calling past the
end returns `[]`. Debugger can be "rewound" by resetting the index.

### T5 — FreeTrace double-free detection
Add `_freed_traces: set[int]` to `MockReplayController`. `FreeTrace(trace)` adds `id(trace)`
to `_freed_traces`. If already present, raise `RuntimeError("double-free of trace")`.
Tests can assert `id(trace) in ctrl._freed_traces`.

## Acceptance Criteria
- All existing unit tests still pass (`pixi run check`)
- 10 new unit tests in `tests/unit/test_mock_renderdoc.py` exercise each behavior change
- No GPU tests required for this track
