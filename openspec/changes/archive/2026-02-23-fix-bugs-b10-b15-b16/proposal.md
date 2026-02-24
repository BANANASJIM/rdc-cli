# Fix Bugs B10 + B15 + B16

## Summary

Three bugs in the query and debug subsystems: B10 causes `debug thread` to crash with a transport overflow for large compute shader traces (and masks the error in `--json` mode); B15 causes `shader-map` to report incorrect stage columns for Dispatch events due to stale pipeline references; B16 causes `vkCmdDrawMeshTasksEXT` draw calls to be classified as "Other" instead of "Draw" because the `MeshDispatch` action flag is not recognized.

## Motivation

B10 makes compute shader debugging completely unusable — the most common use case for `debug thread`. B15 makes `shader-map` output misleading for any capture with mixed draw+dispatch (e.g., physics or particle simulations). B16 makes `events`, `draws`, `info`, and all stats incorrect for any mesh shading capture; mesh shading is a modern GPU feature that will become increasingly common.

---

## Bug Analysis

### B10: `debug thread` transport overflow (P1)

#### Current behavior

Running `rdc debug thread <eid> <gx> <gy> <gz> <tx> <ty> <tz>` against a compute-heavy shader raises:

```
ValueError: recv_line: message exceeds max_bytes limit
```

- Default mode: exits RC=1 (unhandled `ValueError` propagates, Python exits with non-zero).
- `--trace` mode: exits RC=1 (same path).
- `--json` mode: exits RC=0 — the error is silently swallowed, making the failure invisible to scripts.

#### Root cause

Two separate defects:

**Defect 1 — response too large.**
`src/rdc/handlers/debug.py:88` (`_run_debug_loop`) collects up to `_MAX_STEPS = 50_000` step dicts. Each step contains a `changes` list of variable dicts with `before`/`after` float arrays. A complex compute shader can easily produce 50,000 steps × multiple variables per step, yielding a JSON response well above 10 MB.

`src/rdc/daemon_client.py:19` calls `_recv_line(sock)` (imported from `src/rdc/_transport.py:8`) with the default `max_bytes=10 * 1024 * 1024` (10 MB hard cap). When the serialized JSON response exceeds this, `_transport.py:29` raises `ValueError("recv_line: message exceeds max_bytes limit")`.

**Defect 2 — `ValueError` not caught, RC wrong in `--json` mode.**
`src/rdc/commands/_helpers.py:58-66` (`call()`) only catches `OSError`; `ValueError` propagates unhandled. Click's `standalone_mode=True` does not catch arbitrary exceptions and re-raises them. Depending on Click version and context teardown order, the process may exit RC=0 instead of RC=1 when the exception escapes from inside a Click command — this is the RC=0 masked failure in `--json` mode.

#### Proposed fix

**Fix 1 — raise the transport limit to 256 MB.**
Change `src/rdc/_transport.py:8`:

```python
# before
def recv_line(sock: socket.socket, max_bytes: int = 10 * 1024 * 1024) -> str:

# after
def recv_line(sock: socket.socket, max_bytes: int = 256 * 1024 * 1024) -> str:
```

256 MB is a practical upper bound for a single JSON-RPC response; any legitimate debug trace will be smaller. This unblocks all failing modes immediately.

**Fix 2 — catch `ValueError` in `call()` with proper RC.**
Change `src/rdc/commands/_helpers.py:58-66`:

```python
    try:
        response = send_request(host, port, payload)
    except (OSError, ValueError) as exc:
        msg = f"daemon unreachable: {exc}"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1) from exc
```

This ensures any transport-level failure (including future limit breaches) always exits RC=1 in all modes, with a structured JSON error in `--json` mode.

---

### B15: `shader-map` Dispatch EID column mapping (P2)

#### Current behavior

For `compute_nbody.rdc` (which has both Draw and Dispatch events), `rdc shader-map` shows non-zero shader IDs in the VS and PS columns for Dispatch EIDs 8 and 11, when those EIDs use compute pipelines that have no VS or PS shader bound. The CS shader ID may appear in VS/PS columns or unrelated shader IDs appear.

#### Root cause

`src/rdc/handlers/_helpers.py:140-195` (`_build_shader_cache`) walks all draw/dispatch actions in sequence, calling `_set_frame_event(state, a.eventId)` then storing the result of `state.adapter.get_pipeline_state()` in `state._pipe_states_cache[a.eventId]`.

`src/rdc/adapter.py:39-41` shows `get_pipeline_state()` calls `controller.GetPipelineState()` which — per the RenderDoc API gotcha documented in MEMORY.md — returns a **mutable reference** to a single live object. Every entry stored in `_pipe_states_cache` is the same Python/SWIG proxy object; after the walk completes, it reflects only the pipeline state of the **last** event visited.

`src/rdc/services/query_service.py:300-322` (`_collect_recursive`) then iterates the cached entries and calls `state.GetShader(stage_val)` on each — but all `state` values are the same stale object. For `stage_cols = {0: "vs", 1: "hs", 2: "ds", 3: "gs", 4: "ps", 5: "cs"}`, calling `GetShader(0..5)` on a compute pipeline (the last-visited state) returns the compute shader for slot 5, and may return non-zero garbage or the CS shader ID for slots 0–4 depending on the Vulkan/RenderDoc pipeline abstraction.

#### Proposed fix

Stop caching the live pipeline reference. Instead, during `_build_shader_cache`, snapshot the shader IDs per stage immediately and store a plain dict. Modify `_build_shader_cache` in `src/rdc/handlers/_helpers.py` to store a snapshot dict instead of the live pipeline:

```python
# Replace:
state._pipe_states_cache[a.eventId] = pipe

# With: snapshot shader IDs immediately while pipeline is live
stage_snap: dict[int, int] = {}
for sv in range(6):
    stage_snap[sv] = int(pipe.GetShader(sv))
state._pipe_states_cache[a.eventId] = stage_snap  # type: ignore[assignment]
```

Update `_collect_recursive` in `src/rdc/services/query_service.py:300-322` to read from the snapshot dict (no more `.GetShader()` calls — just dict lookups):

```python
def _collect_recursive(
    actions: list[Any],
    pipe_states: dict[int, dict[int, int]],
    rows: list[dict[str, Any]],
) -> None:
    stage_cols = {0: "vs", 1: "hs", 2: "ds", 3: "gs", 4: "ps", 5: "cs"}
    for a in actions:
        flags = int(a.flags)
        if (flags & _DRAWCALL) or (flags & _DISPATCH):
            eid = a.eventId
            snap = pipe_states.get(eid)
            if snap is not None:
                row: dict[str, Any] = {"eid": eid}
                for stage_val, col in stage_cols.items():
                    sid_int = snap[stage_val]
                    row[col] = sid_int if sid_int != 0 else "-"
                rows.append(row)
        if a.children:
            _collect_recursive(a.children, pipe_states, rows)
```

Note: `_handle_pipeline` and `_handle_bindings` in `src/rdc/handlers/query.py` call `get_pipeline_state()` fresh (they do NOT use `_pipe_states_cache`), so they are unaffected. The only consumer of `_pipe_states_cache` is `collect_shader_map` via `_collect_recursive`. The `_pipe_states_cache` type annotation should change to `dict[int, dict[int, int]]`.

Also note: for Dispatch EIDs, stages 0–4 (VS/HS/DS/GS/PS) should display as `"-"`. Since a compute pipeline binds only CS (stage 5), the snapshot will have `0` for all graphics stages, which correctly renders as `"-"` in the output.

---

### B16: `vkCmdDrawMeshTasksEXT` draw classification (P2)

#### Current behavior

For `mesh_shading.rdc`, `rdc events` shows EID 10 with `TYPE=Other`, `rdc draws` does not include EID 10, and `rdc info` does not count EID 10 as a draw call.

#### Root cause

RenderDoc sets `ActionFlags.MeshDispatch = 0x0008` for `vkCmdDrawMeshTasksEXT` actions (confirmed by `tests/mocks/mock_renderdoc.py:53`). This flag is distinct from `ActionFlags.Drawcall = 0x0002`.

All classification logic in `src/rdc/services/query_service.py` only tests `_DRAWCALL = 0x0002`:

- `_action_type_str` in `src/rdc/handlers/_helpers.py:104`: `if flags & _DRAWCALL` → returns `"Draw"` or `"DrawIndexed"`, otherwise falls through to `"Other"`. EID 10 has `0x0008` only, so it returns `"Other"`.
- `filter_by_type` in `src/rdc/services/query_service.py:133-138`: `type_map = {"draw": _DRAWCALL, ...}` — only checks `0x0002`.
- `_triangles_for_action` at line 182: `if not (a.flags & _DRAWCALL)` — returns 0 for mesh draws.
- `aggregate_stats` at lines 193, 221: counts only `_DRAWCALL` for `total_draws`.
- `get_top_draws` at line 221: `[a for a in flat if a.flags & _DRAWCALL]` — misses mesh draws.
- `_subtree_has_draws` at line 440: checks only `_DRAWCALL`.
- `_collect_recursive` at line 308: already includes `_DISPATCH` but not `_MESHDRAW`.
- `_build_shader_cache` in `src/rdc/handlers/_helpers.py:144`: `(flags & _DRAWCALL) or (flags & _QS_DISPATCH)` — misses mesh draws.
- `_handle_stats` RT enrichment in `src/rdc/handlers/query.py:290`: `a.flags & _DRAWCALL` for `pass_first_draw` — misses mesh draws.

#### Proposed fix

Add `_MESHDRAW = 0x0008` constant to `src/rdc/services/query_service.py` alongside existing constants, then update all affected locations to treat `_MESHDRAW` as a draw variant:

```python
# src/rdc/services/query_service.py — add constant
_MESHDRAW = 0x0008
```

Update `_action_type_str` in `src/rdc/handlers/_helpers.py`:

```python
# import _MESHDRAW alongside _DRAWCALL
if flags & (_DRAWCALL | _MESHDRAW):
    return "DrawIndexed" if flags & _INDEXED else "Draw"
```

Update `filter_by_type` in `src/rdc/services/query_service.py`:

```python
type_map = {"draw": _DRAWCALL | _MESHDRAW, "dispatch": _DISPATCH, "clear": _CLEAR, "copy": _COPY}
```

Update `_triangles_for_action`:

```python
if not (a.flags & (_DRAWCALL | _MESHDRAW)):
    return 0
```

Update `aggregate_stats` draw counting:

```python
if a.flags & (_DRAWCALL | _MESHDRAW):
    stats.total_draws += 1
    ...
```

Update `_subtree_has_draws`:

```python
if int(action.flags) & (_DRAWCALL | _MESHDRAW):
    return True
```

Update `_collect_recursive` (already fixed for B15; ensure mesh draws are included):

```python
if (flags & _DRAWCALL) or (flags & _DISPATCH) or (flags & _MESHDRAW):
```

Update `_build_shader_cache` in `src/rdc/handlers/_helpers.py`:

```python
from rdc.services.query_service import _MESHDRAW as _QS_MESHDRAW
...
if (flags & _DRAWCALL) or (flags & _QS_DISPATCH) or (flags & _QS_MESHDRAW):
```

Also update `get_top_draws` (query_service.py:221) and `_handle_stats` RT enrichment (query.py:290 `pass_first_draw`) to include mesh draws.

Mesh draws do not have index-based triangle counts (`numIndices` is 0); `_triangles_for_action` should return 0 for them (or a mesh-specific estimate if available), which is already handled by returning `(0 // 3) * num_instances = 0` — acceptable.

---

## Risk Assessment

**B10 fix 1 (raise `max_bytes`):** Low risk. The limit is a safety guard against runaway data; 256 MB is still a hard cap. No behavioral change for normal responses. The daemon's `sendall` already handles large writes correctly.

**B10 fix 2 (catch `ValueError`):** Very low risk. Adds `ValueError` to an existing `except OSError` clause. No behavior change for the normal path.

**B15 fix (snapshot shader IDs):** Medium risk. Changes the type of `_pipe_states_cache` values from a live pipeline object to `dict[int, int]`. Any handler that uses `_pipe_states_cache` as a live pipeline (e.g., `_handle_pipeline`, `_handle_bindings`) will break unless also updated. Must audit all usages of `state._pipe_states_cache` in `src/rdc/handlers/query.py` and other handlers. The `_collect_recursive` and `_build_shader_cache` paths are fully controlled; risk is limited to missed usages.

**B16 fix (add `_MESHDRAW`):** Low risk for new captures; zero risk for existing non-mesh captures. The `0x0008` flag is only set by `vkCmdDrawMeshTasksEXT`; no existing action type reuses it. The triangle count for mesh draws will be 0 (correct, since mesh shaders don't use index buffers).

## Alternatives Considered

**B10 — chunked/streaming transport:** Replace `recv_line` with a length-prefixed framing protocol to eliminate the size cap entirely. Rejected: requires protocol breaking change and daemon/client coordination changes across all callers. The 256 MB bump achieves the same practical result with minimal change.

**B10 — server-side trace truncation:** Cap `_MAX_STEPS` lower or paginate the trace response. Rejected: the existing `_MAX_STEPS = 50_000` guard is already present; the problem is the response size cap, not the step count. Lowering `_MAX_STEPS` further would degrade the debugging experience.

**B15 — call `_set_frame_event` inside `_collect_recursive`:** Re-run the replay seek per EID during the shader-map collection. Rejected: this is a O(N) replay seeks during output formatting, causing severe performance regression for large captures. Snapshotting during `_build_shader_cache` (which already seeks) is the correct approach.

**B16 — string-match on action name:** Detect `vkCmdDrawMeshTasksEXT` by action name string. Rejected: fragile, not portable across API backends (DX12 has `DispatchMesh`), and the flag-based approach is the canonical RenderDoc pattern already used for all other action types.
