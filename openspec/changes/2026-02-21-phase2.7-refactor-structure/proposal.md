# Refactor: Code Structure — Handler Modules, Shared Helpers, Deduplication

## Summary

Pure structural refactor addressing 3 P0 and 8 P1 code-quality issues identified in two rounds
of Opus code review (pre- and post-Phase 2.7 feature merges). Zero behavior changes.
All 838 existing tests must pass unchanged after this refactor.

This branch merges **after** the other three Phase 2.7 branches (fix/bug-filters,
feat/resources-filter, feat/pipeline-cli) — all now merged to master.

---

## Problem

### P0-1: `daemon_server.py` — 2255 lines, 40+ handlers in one monolithic `if/elif` chain

`_handle_request` (L269) routes every JSON-RPC method inline across ~1500 lines. Navigating,
reviewing, and testing individual handler groups requires reading through the entire function.

### P0-2: `_require_session()` and `_call()` duplicated in 3 command files

Identical private functions in `resources.py`, `pipeline.py`, and `unix_helpers.py`.
A fourth variant (`_daemon_call`) in `info.py` is imported by 6 other command files.

### P0-3: `STAGE_MAP` dict literal repeated 8 times in `daemon_server.py`

`{"vs": 0, "hs": 1, "ds": 2, "gs": 3, "ps": 4, "cs": 5}` appears 8 times as anonymous
dict literals. Also exists as `_STAGE_MAP` in `query_service.py:25` and as `_SHADER_STAGES`
frozenset in two separate files.

### P1-4: Inconsistent enum-to-string conversion — 3 patterns coexist

1. `_enum_name(v)` (daemon_server L181): `v.name if hasattr(v, "name") else v` — **not str-safe**
2. `v.name if hasattr(v, "name") else str(v)` — used inline 11 times
3. `getattr(v, "name", str(v))` — used 5 times in query_service.py

Pattern 1 can return non-string objects, risking JSON serialization errors.

### P1-5: Guard + set_frame_event + get_pipeline_state boilerplate repeated 25+ times

```python
if state.adapter is None:
    return _error_response(request_id, -32002, "no replay loaded"), True
eid = int(params.get("eid", state.current_eid))
err = _set_frame_event(state, eid)
if err:
    return _error_response(request_id, -32002, err), True
pipe_state = state.adapter.get_pipeline_state()
```

### P1-6: "Get pipeline object for stage" logic duplicated 4 times

```python
pipeline = (
    pipe_state.GetComputePipelineObject()
    if stage_val == 5
    else pipe_state.GetGraphicsPipelineObject()
)
```

### P1-7: GetDisassemblyTargets fallback pattern duplicated 4 times

```python
targets = (
    controller.GetDisassemblyTargets(True)
    if hasattr(controller, "GetDisassemblyTargets")
    else ["SPIR-V"]
)
target = str(targets[0]) if targets else "SPIR-V"
```

### P1-8: Dead code — `_count_events` in daemon_server.py unused

Defined at L151-158, never called. `query_service.py` has the live version.

### P1-9: `_recv_line` duplicated between daemon_client.py and daemon_server.py

Near-identical socket line-reading. daemon_client version lacks empty-response guard.

### P1-10: `_kv_text` (vfs.py) and `_format_kv` (info.py) are near-duplicates

Both format `dict[str, Any]` as aligned key-value text.

### P1-11: Hardcoded magic numbers `0x0002` / `0x0004` in `_collect_pipe_states_recursive`

`query_service.py` defines named constants `_DRAWCALL = 0x0002` and `_DISPATCH = 0x0004`
but daemon_server.py uses raw hex.

---

## Design

### Phase A: Extract shared command helpers

Create `src/rdc/commands/_helpers.py` with `require_session()` and `call()`.
Replace duplicates in `resources.py`, `pipeline.py`, `unix_helpers.py`.

`_daemon_call` in `info.py` is **not** replaced in this refactor to minimize blast radius.

### Phase B: Deduplicate constants and small helpers

**B1: STAGE_MAP** — Rename `_STAGE_MAP` to `STAGE_MAP` in `query_service.py` (public constant).
Replace all 8 inline dict literals and both `_SHADER_STAGES` frozensets with imports.

**B2: _enum_name** — Fix to always return `str`:
```python
def _enum_name(v: Any) -> str:
    return v.name if hasattr(v, "name") else str(v)
```
Replace all 3 inline patterns with calls to the unified helper.

**B3: _recv_line** — Move to `src/rdc/_transport.py`, import from both daemon_client.py
and daemon_server.py. Add empty-response guard to daemon_client's `send_request`.

**B4: Dead code** — Delete unused `_count_events` from daemon_server.py.

**B5: Magic numbers** — Import `_DRAWCALL`, `_DISPATCH` from query_service.py
in `_collect_pipe_states_recursive`.

### Phase C: Split `_handle_request` into handler modules

Create `src/rdc/handlers/` package with dispatch registry pattern.

**Handler type alias** (defined in `src/rdc/handlers/__init__.py`):
```python
HandlerFunc = Callable[[int, dict[str, Any], DaemonState], tuple[dict[str, Any], bool]]
```

**`src/rdc/handlers/_helpers.py`** — Shared handler helpers extracted from daemon_server.py:
- `_result_response`, `_error_response`
- `_set_frame_event`, `_enum_name`, `_sanitize_size`, `_max_eid`
- `_get_flat_actions`, `_action_type_str`, `_build_shader_cache`, `_collect_pipe_states`
- **New**: `require_pipe(params, state, request_id) -> tuple[int, Any] | tuple[dict, bool]`
  — eliminates the 25x boilerplate
- **New**: `get_pipeline_for_stage(pipe_state, stage_val) -> Any`
  — eliminates 4x pipeline object selection
- **New**: `get_default_disasm_target(controller) -> str`
  — eliminates 4x GetDisassemblyTargets fallback

`daemon_server.py` re-exports all helpers for backward compatibility with test imports.

**Handler modules:**

| Module | Methods |
|--------|---------|
| `core.py` | `ping`, `status`, `goto`, `count`, `shutdown` |
| `query.py` | `shader_map`, `pipeline`, `bindings`, `shader`, `shaders`, `resources`, `resource`, `passes`, `pass`, `events`, `draws`, `event`, `draw`, `search` |
| `shader.py` | `shader_targets`, `shader_reflect`, `shader_constants`, `shader_source`, `shader_disasm`, `shader_all`, `shader_list_info`, `shader_list_disasm` |
| `texture.py` | `tex_info`, `tex_export`, `tex_raw`, `rt_export`, `rt_depth` |
| `buffer.py` | `buf_info`, `buf_raw`, `postvs`, `cbuffer_decode`, `vbuffer_decode`, `ibuffer_decode` |
| `pipe_state.py` | all 13 `pipe_*` handlers |
| `descriptor.py` | `descriptors`, `usage`, `usage_all`, `counter_list`, `counter_fetch` |
| `vfs.py` | `vfs_ls`, `vfs_tree` |

**New `_handle_request`:**
```python
_DISPATCH: dict[str, HandlerFunc] = {}  # merged from all HANDLERS dicts at import time

def _handle_request(request, state):
    method = request.get("method", "")
    req_id = request.get("id", 1)
    params = request.get("params", {})
    handler = _DISPATCH.get(method)
    if handler is None:
        return _error_response(req_id, -32601, f"unknown method: {method}"), False
    return handler(req_id, params, state)
```

`DaemonState`, `_load_replay`, `run_server`, `main`, and TCP machinery stay in `daemon_server.py`.

### Phase D: Cleanup (low-risk P1 items)

**D1: _kv_text / _format_kv** — Consolidate into formatters module. Out of scope for this PR
to minimize blast radius — tracked as follow-up.

---

## Scope

### In scope
- Create `src/rdc/handlers/` package with 8 handler modules + `_helpers.py`
- Refactor `_handle_request` to dict-dispatch
- Create `src/rdc/commands/_helpers.py` (dedup `require_session` + `call`)
- Create `src/rdc/_transport.py` (dedup `_recv_line`)
- Replace all inline stage map literals with `STAGE_MAP` import
- Unify `_enum_name` to always return `str`, replace all 3 inline patterns
- Extract `require_pipe`, `get_pipeline_for_stage`, `get_default_disasm_target` helpers
- Delete dead `_count_events`, replace magic numbers with named constants

### Out of scope
- Unifying `_daemon_call` (info.py) with `_call` / `require_session` — separate PR
- Consolidating `_kv_text` / `_format_kv` — separate PR
- `_subtree_stats` / `_window_stats` inner walk dedup — low priority
- Counter enumeration dedup — low priority
- Any behavior change, new feature, or output format change
- Changes to test files (tests must pass as-is)
- Renaming existing public symbols (`DaemonState`, `_handle_request`, etc.)
- Moving `DaemonState`, `_load_replay`, or TCP server code out of `daemon_server.py`
