# Tasks: Fix B17 — Read-Only Queries Mutate current_eid

## Task 1: Add `_seek_replay()` to `_helpers.py`

- **Files**: `src/rdc/handlers/_helpers.py`
- **Changes**:
  - After the `_set_frame_event()` function definition (line ~82), add
    `_seek_replay(state, eid)`.
  - Implementation mirrors `_set_frame_event` exactly, omitting only the
    `state.current_eid = eid` assignment:
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
- **Depends on**: nothing
- **Estimated complexity**: S

## Task 2: Replace `_set_frame_event` with `_seek_replay` in `_build_shader_cache._walk()`

- **Files**: `src/rdc/handlers/_helpers.py`
- **Changes**:
  - In `_build_shader_cache`, inside the inner `_walk()` function (~line 146):
    replace `_set_frame_event(state, a.eventId)` with
    `_seek_replay(state, a.eventId)`.
  - The call to `_set_frame_event` imported from the same module must be
    removed from this call site; `_seek_replay` is available in the same scope.
- **Depends on**: Task 1
- **Estimated complexity**: S

## Task 3: Add restore logic after `_walk()` in `_build_shader_cache`

- **Files**: `src/rdc/handlers/_helpers.py`
- **Changes**:
  - After the `_walk(state.adapter.get_root_actions())` call in
    `_build_shader_cache`, restore the replay head to the user's position:
    ```python
    _walk(state.adapter.get_root_actions())
    if state.current_eid > 0:
        _seek_replay(state, state.current_eid)
    ```
  - This ensures that after shader cache population the adapter is positioned
    at the user's current EID, not the last action visited by the walk.
- **Depends on**: Task 2
- **Estimated complexity**: S

## Task 4: Replace `_set_frame_event` with `_seek_replay` in `_ensure_shader_populated`

- **Files**: `src/rdc/handlers/_helpers.py`
- **Changes**:
  - In `_ensure_shader_populated` (~line 282): replace
    `err = _set_frame_event(state, eid)` with `err = _seek_replay(state, eid)`.
  - No restore is needed. The VFS subtree population seeks to the path's own
    EID; `current_eid` (the user's position) must not change.
- **Depends on**: Task 1
- **Estimated complexity**: S

## Task 5: Replace `_set_frame_event` with `_seek_replay` in `_handle_stats` and add restore

- **Files**: `src/rdc/handlers/query.py`
- **Changes**:
  - Add `_seek_replay` to the import from `rdc.handlers._helpers` (alongside
    the existing `_set_frame_event` import at ~line 20).
  - In `_handle_stats` RT enrichment loop (~line 296): replace
    `err = _set_frame_event(state, draw_eid)` with
    `err = _seek_replay(state, draw_eid)`.
  - After the `for ps in stats.per_pass:` loop ends, add a restore:
    ```python
    if state.current_eid > 0:
        _seek_replay(state, state.current_eid)
    ```
- **Depends on**: Task 1
- **Estimated complexity**: S

## Task 6: Replace `_set_frame_event` with `_seek_replay` in `_handle_pass`

- **Files**: `src/rdc/handlers/query.py`
- **Changes**:
  - In `_handle_pass` (~line 201): replace
    `err = _set_frame_event(state, detail["begin_eid"])` with
    `err = _seek_replay(state, detail["begin_eid"])`.
  - No restore is needed. The seek is scoped to reading pass targets;
    `current_eid` must not change.
- **Depends on**: Task 1, Task 5 (same file — coordinate imports)
- **Estimated complexity**: S

## Task 7: Re-export `_seek_replay` from `daemon_server.py`

- **Files**: `src/rdc/daemon_server.py`
- **Changes**:
  - Add `_seek_replay` to the `from rdc.handlers._helpers import (...)` block
    (alongside `_set_frame_event` at ~line 26).
  - Add `"_seek_replay"` to the `__all__` list (~line 64), immediately after
    `"_set_frame_event"` for alphabetical ordering.
- **Depends on**: Task 1
- **Estimated complexity**: S

## Task 8: Add `TestEidPreservation` tests to `test_shader_preload.py`

- **Files**: `tests/unit/test_shader_preload.py`
- **Changes**:
  Add a new `TestEidPreservation` class with 3 test methods:

  **`test_build_shader_cache_preserves_current_eid`**
  - Build a mock `DaemonState` with `current_eid=50`.
  - Provide a mock adapter with `get_root_actions()` returning 3 actions
    (two draws at EIDs 10, 20; one dispatch at EID 30) and
    `get_pipeline_state()` returning a mock pipe whose `GetShader(sv)` returns
    1 for `sv==0` (vs) and 0 otherwise.
  - Call `_build_shader_cache(state)`.
  - Assert `state.current_eid == 50`.
  - Assert `state._shader_cache_built is True`.
  - Assert `state.adapter.set_frame_event` was called at least once (the
    internal walk did seek).

  **`test_stats_preserves_current_eid`**
  - Build a mock `DaemonState` with `current_eid=50`.
  - Monkeypatch `_get_flat_actions` to return a flat list with 2 draw actions
    both in `pass_name="pass0"`, `eid` values 10 and 20.
  - Mock `state.adapter.get_pipeline_state()` to return a mock pipe with
    `GetOutputTargets()` returning `[]` and `GetDepthTarget().resource == 0`.
  - Call `_handle_stats(1, {"_token": state.token}, state)`.
  - Assert response contains `"result"` key.
  - Assert `state.current_eid == 50`.

  **`test_pass_preserves_current_eid`**
  - Build a mock `DaemonState` with `current_eid=50`.
  - Monkeypatch `get_pass_detail` (from `rdc.services.query_service`) to
    return `{"begin_eid": 5, "end_eid": 15, "name": "pass0", "draws": 1,
    "dispatches": 0, "triangles": 100}`.
  - Mock `state.adapter.get_pipeline_state()` to return a mock pipe with
    `GetOutputTargets()` returning `[]` and `GetDepthTarget().resource == 0`.
  - Call `_handle_pass(1, {"_token": state.token, "index": 0}, state)`.
  - Assert response contains `"result"` key.
  - Assert `state.current_eid == 50`.

- **Depends on**: Tasks 2–6
- **Estimated complexity**: M

## Task 9: Run lint and test

- **Files**: none
- **Changes**: none
- **Action**:
  ```
  pixi run lint && pixi run test
  ```
  Zero failures required before PR creation.
- **Depends on**: Tasks 1–8
- **Estimated complexity**: S

---

## Parallelism

Tasks 1–7 are implementation tasks; Tasks 8–9 are test and verification.

- **Task 1** must complete before Tasks 2, 3, 4, 5, 6, 7 (all depend on the
  new function).
- **Tasks 2, 3, 4** all touch `src/rdc/handlers/_helpers.py` — assign to one
  agent to avoid conflicts.
- **Tasks 5, 6, 7** can run in parallel with Tasks 2–4 if assigned to
  separate agents (different files). Tasks 5 and 6 both touch `query.py` and
  must be combined into one agent.
- **Task 7** touches only `daemon_server.py` and is fully independent of
  Tasks 2–6.
- **Task 8** depends on all implementation tasks (2–6) being complete.
- **Task 9** depends on Task 8.

## Recommended implementation order

1. **Phase A**: Task 1 (add `_seek_replay`) — single change, unblocks all others.
2. **Phase B (parallel)**:
   - Agent A: Tasks 2, 3, 4 (`_helpers.py` changes)
   - Agent B: Tasks 5, 6 (`query.py` changes)
   - Agent C: Task 7 (`daemon_server.py` re-export)
3. **Phase C**: Task 8 (write tests, after Phase B complete).
4. **Phase D**: Task 9 (lint + test).
