# Fix B17: Read-Only Queries Mutate current_eid

## Summary

Four internal call sites — inside `_build_shader_cache._walk()`, `_ensure_shader_populated`,
`_handle_stats`, and `_handle_pass` — call `_set_frame_event(state, eid)`, which
unconditionally sets `state.current_eid = eid` (line 81 of `src/rdc/handlers/_helpers.py`).
These are all read-only queries; none of them intend to change the user's replay position.
The result is that invoking `stats`, `pass`, `shader-map`, or any VFS read that triggers
shader population silently moves `state.current_eid` away from the position the user set
with `seek`. Subsequent user commands then operate on the wrong event.

This is a P1 data-corruption bug: the user's replay position changes without their
knowledge, making all position-sensitive outputs (pipeline state, bindings, cbuffer values)
unreliable after any stats or pass query.

## Motivation

`state.current_eid` is the single authoritative user-visible replay position. Commands
like `pipeline`, `bindings`, `cbuffer`, and `diff` all default to `state.current_eid`
when no explicit `eid` param is provided. Any code that silently modifies `current_eid`
as a side effect of a read-only query is a bug.

Examples of broken sequences:
- User runs `seek 50` → then `stats` → then `pipeline` (no eid arg): pipeline now shows
  EID from the last pass checked by `_handle_stats`, not EID 50.
- User runs `seek 50` → then `vfs read /draws/10/shader/ps`: `_ensure_shader_populated`
  moves `current_eid` to 10 as a side effect.
- User runs `seek 50` → then `shader-map`: `_build_shader_cache` walks all actions and
  leaves `current_eid` at whatever the last action's EID was.

---

## Root Cause Analysis

`_set_frame_event(state, eid)` in `src/rdc/handlers/_helpers.py` does two distinct things:

1. **Drives the replay head**: calls `state.adapter.set_frame_event(eid)` and updates
   `state._eid_cache` to avoid redundant seeks.
2. **Updates user position**: sets `state.current_eid = eid`.

Action 1 is needed by every caller — including read-only queries — because the RenderDoc
adapter must be at the right EID before calling `get_pipeline_state()` or `GetShader()`.
Action 2 is only correct for explicit user seek commands (`seek`, `pipeline <eid>`,
`bindings <eid>`, etc.).

The four internal call sites that trigger action 2 incorrectly:

| Call site | File | Line | Correct intent |
|-----------|------|------|----------------|
| `_walk()` inner loop | `src/rdc/handlers/_helpers.py` | ~146 | Seek for snapshot — read-only |
| `_ensure_shader_populated` | `src/rdc/handlers/_helpers.py` | ~282 | Seek to populate VFS node — read-only |
| `_handle_stats` RT enrichment loop | `src/rdc/handlers/query.py` | ~296 | Seek per pass for RT info — read-only |
| `_handle_pass` target query | `src/rdc/handlers/query.py` | ~201 | Seek to pass begin EID — read-only |

---

## Proposed Fix

### New function: `_seek_replay()`

Add `_seek_replay(state, eid)` to `src/rdc/handlers/_helpers.py`, alongside
`_set_frame_event`. It drives the adapter and eid_cache identically to `_set_frame_event`
but does **not** touch `state.current_eid`:

```python
def _seek_replay(state: DaemonState, eid: int) -> str | None:
    """Drive the replay head without mutating current_eid."""
    if eid < 0:
        return "eid must be >= 0"
    if state.max_eid > 0 and eid > state.max_eid:
        return f"eid {eid} out of range (max: {state.max_eid})"
    if state.adapter is not None:
        if state._eid_cache != eid:
            state.adapter.set_frame_event(eid)
            state._eid_cache = eid
    return None
```

### Call-site changes

**`_build_shader_cache._walk()` in `src/rdc/handlers/_helpers.py`:**

Replace:
```python
_set_frame_event(state, a.eventId)
```
With:
```python
_seek_replay(state, a.eventId)
```

After `_walk()` returns, restore the replay head to the user's position:
```python
_walk(state.adapter.get_root_actions())
# Restore replay head to user's position
if state.current_eid > 0:
    _seek_replay(state, state.current_eid)
```

**`_ensure_shader_populated` in `src/rdc/handlers/_helpers.py`:**

Replace:
```python
err = _set_frame_event(state, eid)
```
With:
```python
err = _seek_replay(state, eid)
```

No restore needed here — `_ensure_shader_populated` already seeks to a specific `eid`
derived from the VFS path, which is an explicit request for that event's data. `current_eid`
must not be moved.

**`_handle_stats` RT enrichment loop in `src/rdc/handlers/query.py`:**

Replace:
```python
err = _set_frame_event(state, draw_eid)
```
With:
```python
err = _seek_replay(state, draw_eid)
```

After the loop, restore:
```python
# Restore replay head
if state.current_eid > 0:
    _seek_replay(state, state.current_eid)
```

**`_handle_pass` in `src/rdc/handlers/query.py`:**

Replace:
```python
err = _set_frame_event(state, detail["begin_eid"])
```
With:
```python
err = _seek_replay(state, detail["begin_eid"])
```

No restore needed — `_handle_pass` is already seeking to a specific EID as part of
fetching the pass detail. The seek is scoped to the response. `current_eid` must not
be moved.

### Re-export from `daemon_server.py`

Add `_seek_replay` to the imports and `__all__` in `src/rdc/daemon_server.py` for
backward-compatibility (other modules import from `daemon_server`):

```python
from rdc.handlers._helpers import (
    ...
    _seek_replay,
    _set_frame_event,
)
...
__all__ = [
    ...
    "_seek_replay",
    "_set_frame_event",
    ...
]
```

---

## Files Modified

| File | Change |
|------|--------|
| `src/rdc/handlers/_helpers.py` | Add `_seek_replay()`; replace call in `_walk()`; add restore after `_walk()`; replace call in `_ensure_shader_populated` |
| `src/rdc/handlers/query.py` | Replace calls in `_handle_stats` and `_handle_pass`; add restore loop in `_handle_stats`; import `_seek_replay` |
| `src/rdc/daemon_server.py` | Import and re-export `_seek_replay` |
| `tests/unit/test_shader_preload.py` | Add `TestEidPreservation` class with 3 new tests |

---

## Risk Assessment

**`_seek_replay` introduction:** Very low risk. It is a strict subset of `_set_frame_event`
(identical logic minus one assignment). All existing `_set_frame_event` call sites are
unaffected.

**`_build_shader_cache` restore:** Low risk. The restore seek is a no-op when
`current_eid == 0` (nothing loaded yet). For loaded sessions it re-issues a single
`set_frame_event` call, which is idempotent if the user's EID is already cached.

**`_handle_stats` restore:** Same reasoning as above. The restore seek occurs after the
enrichment loop, once, and is idempotent.

**`_handle_pass` and `_ensure_shader_populated`:** No restore added. These seek to a
user-specified EID (the pass begin EID or the VFS path EID) and do not iterate. Not
restoring is correct because the final EID they seek to is not meaningful to preserve —
only `current_eid` (unchanged) matters for the next user command.

## Alternatives Considered

**Always restore inside `_set_frame_event`:** Would require passing a "read-only" flag
parameter, making the API more complex and error-prone for future callers. The two-function
approach (`_set_frame_event` for user seeks, `_seek_replay` for internal seeks) is
clearer.

**Cache the pipeline state snapshot immediately in `_set_frame_event`:** Solves B15 but
not B17. The EID mutation problem is orthogonal to caching.

**Remove `current_eid` mutation from `_set_frame_event` entirely:** Would break the
`seek` command and every handler that relies on `_set_frame_event` to update user
position. The existing callers that do intend to move `current_eid` (`seek`, `pipeline`,
`bindings`, `descriptor`, etc.) would need to add an explicit assignment — more churn
with no benefit.
