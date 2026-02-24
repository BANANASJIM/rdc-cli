# Proposal: fix-json-error-and-search-preload

## Summary

Fix two bugs from 待解决.md:

- **B2**: `--json` flag does not affect error output — errors always go to stderr as plain text even when the caller requested JSON.
- **B3**: `shaders/search` (and all callers of `_build_shader_cache`) triggers O(N_draws) `SetFrameEvent` calls in pass 1 and then another O(unique_shaders) calls in pass 2. On large captures this is the dominant latency on first search.

---

## Problem Statement

### B2 — JSON error output inconsistency

Commands with `--json` output their success results as JSON to stdout. However, when `require_session()` or `call()` encounters an error (no session, daemon unreachable, RPC error), it writes a plain-text string to stderr regardless of the flag. Scripts and CI pipelines that parse JSON output receive mixed formats depending on whether the command succeeded or failed.

Similarly, `assert_ci.py`'s `_assert_call` has its own copy of session-loading and error-handling logic that does not participate in the helpers at all.

### B3 — Double-pass SetFrameEvent in shader cache build

`_build_shader_cache` currently:

1. **Pass 1** — calls `_collect_pipe_states`, which recursively walks the full action tree. For every draw/dispatch event it calls `SetFrameEvent` + `GetPipelineState`. This is O(N_draws) API calls.
2. **Pass 2** — for each unique shader ID found in pass 1, calls `SetFrameEvent` again to the shader's first EID, then `GetPipelineState` + `GetShaderReflection` + `DisassembleShader`.

Both passes are necessary conceptually, but they can be merged into one traversal. The current two-pass structure means a frame with 500 draws containing 30 unique shaders produces 500 + 30 = 530 `SetFrameEvent` calls when 500 would suffice (or fewer, thanks to the EID cache).

Additionally, `_handle_shader_map` in `query.py` and `_handle_shaders` call `_collect_pipe_states` directly, bypassing the shader cache entirely and repeating the same O(N_draws) walk independently.

---

## B2 Proposed Solution — JSON-aware error output

### New helper: `_json_mode() -> bool`

Add to `src/rdc/commands/_helpers.py`:

```python
def _json_mode() -> bool:
    """Return True if the current Click context has a JSON output flag set."""
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return False
    params = ctx.params
    return bool(
        params.get("use_json")
        or params.get("output_json")
        or params.get("as_json")
    )
```

The three param names (`use_json`, `output_json`, `as_json`) cover all existing `--json` option spellings used across command modules (confirmed by audit of all command files).

### Error format

When `_json_mode()` is True, errors are written to stderr as:

```json
{"error": {"message": "<human-readable message>"}}
```

This mirrors the daemon's own JSON-RPC error body structure and is easy to parse unconditionally.

### Modified `require_session()`

```python
def require_session() -> tuple[str, int, str]:
    session = load_session()
    if session is None:
        msg = "no active session (run 'rdc open' first)"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1)
    return session.host, session.port, session.token
```

### Modified `call()`

```python
def call(method: str, params: dict[str, Any]) -> dict[str, Any]:
    host, port, token = require_session()
    payload = _request(method, 1, {"_token": token, **params}).to_dict()
    try:
        response = send_request(host, port, payload)
    except OSError as exc:
        msg = f"daemon unreachable: {exc}"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1) from exc
    if "error" in response:
        msg = response["error"]["message"]
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1)
    return cast(dict[str, Any], response["result"])
```

### Modified `_assert_call()` in `assert_ci.py`

`_assert_call` in `assert_ci.py` currently duplicates session-loading and error-output logic. After this fix it imports `_json_mode` and applies the same JSON-aware formatting. It retains `sys.exit(2)` (not `SystemExit(1)`) because CI assertions use exit code 2 for infrastructure errors vs. exit code 1 for assertion failures.

```python
from rdc.commands._helpers import _json_mode

def _assert_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    session = load_session()
    if session is None:
        msg = "no active session"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        sys.exit(2)
    payload = _request(method, 1, {"_token": session.token, **(params or {})}).to_dict()
    try:
        resp = send_request(session.host, session.port, payload)
    except Exception as exc:
        msg = f"daemon unreachable: {exc}"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        sys.exit(2)
    if "error" in resp:
        msg = resp["error"]["message"]
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        sys.exit(2)
    return resp["result"]
```

`__all__` in `_helpers.py` is updated to export `_json_mode`.

---

## B3 Proposed Solution — single-pass shader cache + preload

### Part 1 — Merge loops in `_build_shader_cache`

The current two-pass structure separates pipeline-state collection (pass 1) from reflection+disassembly (pass 2). These can be merged: when a shader is encountered for the first time during the action tree walk, immediately call `GetShaderReflection` and `DisassembleShader` at that EID. Subsequent encounters of the same shader ID are tracked only for the use-count and EID list — no additional API calls are needed.

New single-pass structure (conceptual):

```
_build_shader_cache(state):
    seen: dict[int, bool]  # shader_id → reflection already done
    shader_eids: dict[int, list[int]]
    shader_stages: dict[int, list[str]]
    shader_meta: dict[int, dict]

    _walk(actions):
        for a in actions:
            if draw_or_dispatch:
                set_frame_event(a.eventId)        # cached; no-op if same EID
                pipe = get_pipeline_state()
                for stage_val, stage_name in _STAGE_NAMES:
                    sid = int(pipe.GetShader(stage_val))
                    if sid == 0: continue
                    shader_eids[sid].append(a.eventId)
                    shader_stages[sid].add(stage_name)
                    if sid not in seen:
                        seen[sid] = True
                        refl = pipe.GetShaderReflection(stage_val)
                        disasm = controller.DisassembleShader(pipeline, refl, target)
                        state.disasm_cache[sid] = disasm or ""
                        # shader_meta will be finalized after walk
            if a.children:
                _walk(a.children)

    # finalize meta after walk (uses count is now known)
    for sid in seen:
        state.shader_meta[sid] = {
            "stages": sorted(shader_stages[sid]),
            "uses": len(shader_eids[sid]),
            "first_eid": shader_eids[sid][0],
            ...
        }
```

This eliminates pass 2 entirely. The EID cache in `_set_frame_event` (`state._eid_cache`) prevents redundant `SetFrameEvent` calls when consecutive draws share the same EID (which is common in multi-stage passes).

`_collect_pipe_states` and `_collect_pipe_states_recursive` are removed from `_helpers.py` after all callers are migrated (see below).

### Callers of `_collect_pipe_states` that need updating

| Location | Current usage | After fix |
|----------|--------------|-----------|
| `handlers/_helpers.py` | `_build_shader_cache` calls `_collect_pipe_states` in pass 1 | Eliminated — merged into single pass |
| `handlers/query.py` — `_handle_shader_map` | calls `_collect_pipe_states` directly then `collect_shader_map` | Change to call `_build_shader_cache(state)` and derive the needed `pipe_states` from `state.shader_meta` / rework `collect_shader_map` to accept cached data |
| `handlers/query.py` — `_handle_shaders` | calls `_collect_pipe_states` then `shader_inventory` | Change to call `_build_shader_cache(state)` then derive inventory from `state.shader_meta` |
| `handlers/core.py` — `count` handler (what="shaders") | calls `_collect_pipe_states` then `shader_inventory` | Change to call `_build_shader_cache(state)` and return `len(state.shader_meta)` |

Note: `collect_shader_map` and `shader_inventory` in `query_service.py` may need lightweight adapters or refactors to accept `state.shader_meta` instead of raw `pipe_states`. The exact approach is left to implementation; the invariant is that `_collect_pipe_states` must have zero callers after this change.

### Part 2 — `shaders_preload` RPC method

Add a new daemon handler in `handlers/shader.py` (or `handlers/query.py`):

**Method:** `shaders_preload`

**Params:** none

**Handler logic:**

```python
def _handle_shaders_preload(request_id, params, state):
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True
    _build_shader_cache(state)
    return _result_response(request_id, {
        "done": True,
        "shaders": len(state.shader_meta),
    }), True
```

**Response:**

```json
{"done": true, "shaders": 42}
```

This RPC is idempotent: if the cache is already built, `_build_shader_cache` returns immediately and the response reflects the already-cached count.

### Part 3 — `--preload` flag on `rdc open`

Add to `src/rdc/commands/session.py`:

```python
@click.command("open")
@click.argument("capture", type=click.Path(path_type=Path))
@click.option("--preload", is_flag=True, help="Preload shader cache after opening.")
def open_cmd(capture: Path, preload: bool) -> None:
    ok, message = open_session(capture)
    if not ok:
        click.echo(message, err=True)
        raise SystemExit(1)
    click.echo(message)
    click.echo(f"session: {session_path()}")
    if preload:
        result = call("shaders_preload", {})
        click.echo(f"Preloaded {result['shaders']} shaders")
```

This is synchronous and blocking. The user sees the preload message only after all shaders are disassembled. No background threading is used.

### Why no background thread

The RenderDoc Python replay API is not documented as thread-safe. All replay calls (`SetFrameEvent`, `GetPipelineState`, `GetShaderReflection`, `DisassembleShader`) must happen on the same thread that opened the capture. The daemon already serializes all RPC requests on the main loop thread, so a background preload thread would require a synchronization mechanism that introduces more complexity than it removes. Background preload is deferred.

---

## Files Changed

| File | Change |
|------|--------|
| `src/rdc/commands/_helpers.py` | Add `_json_mode()`, update `require_session()` and `call()`, add `json` import, update `__all__` |
| `src/rdc/commands/assert_ci.py` | Import `_json_mode` from `_helpers`, apply to `_assert_call` |
| `src/rdc/commands/session.py` | Add `--preload` flag to `open_cmd`, import `call`, call `shaders_preload` RPC |
| `src/rdc/daemon_server.py` | Add `_pipe_states_cache` field to `DaemonState`; remove `_collect_pipe_states` import and `__all__` entry |
| `src/rdc/handlers/_helpers.py` | Rewrite `_build_shader_cache` as single-pass, populate `state._pipe_states_cache`, remove `_collect_pipe_states` and `_collect_pipe_states_recursive` |
| `src/rdc/handlers/query.py` | Update `_handle_shader_map`, `_handle_shaders` to use `_build_shader_cache` + `state._pipe_states_cache`; add `_handle_preload`; register `"shaders_preload"` |
| `src/rdc/handlers/core.py` | Update `count` handler (`what="shaders"`) to use `_build_shader_cache` + `len(state.shader_meta)` |

---

## Non-Goals / Deferred

- **Background/async preload**: blocked on thread-safety of RenderDoc Python API. Deferred to a future phase.
- **Progress streaming**: no streaming protocol exists in the current JSON-RPC transport.
- **Per-target disassembly cache**: the current cache uses the default target. Multi-target caching is a separate concern.
- **Cache invalidation**: cache is session-scoped and lives until `rdc close`. No invalidation needed.
- **Normalizing `--json` param names across commands**: the three existing names (`use_json`, `output_json`, `as_json`) are deliberately preserved to avoid touching every command file. `_json_mode()` handles all three.
