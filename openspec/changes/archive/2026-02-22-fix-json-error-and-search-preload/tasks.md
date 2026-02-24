# Tasks: fix-json-error-and-search-preload

Two independent bug fixes split across two parallel branches.

---

## Branch A: `fix/json-error-output` (Bug B2)

**Goal**: `--json` flag must affect error output. Currently all error paths in
`_helpers.py` and `assert_ci.py` emit plain-text to stderr regardless of
whether `--json` was passed.

**Files touched** (no overlap with Branch B):
- `src/rdc/commands/_helpers.py`
- `src/rdc/commands/assert_ci.py`
- `tests/unit/test_json_errors.py` (new)

### T-A1 — Add `_json_mode()` to `src/rdc/commands/_helpers.py`

Add a module-level helper that inspects the current Click context for the
`--json` flag. Different command files store the flag under different param
destination names — check all three:

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

The three param names cover all existing `--json` option destinations:
`use_json` (most commands), `output_json` (assert_ci, diff, script),
`as_json` (pipeline, resources, unix_helpers).

Export via `__all__` so `assert_ci.py` can import it.

### T-A2 — Update `require_session()` to use `_json_mode()`

In `src/rdc/commands/_helpers.py`, change the "no active session" error path:

```python
# before
click.echo("error: no active session (run 'rdc open' first)", err=True)

# after
msg = "no active session (run 'rdc open' first)"
if _json_mode():
    click.echo(json.dumps({"error": {"message": msg}}), err=True)
else:
    click.echo(f"error: {msg}", err=True)
```

Add `import json` at the top of the file.

### T-A3 — Update `call()` error paths to use `_json_mode()`

In `src/rdc/commands/_helpers.py`, update both error branches inside `call()`:

**OSError path** (daemon unreachable):
```python
# before
click.echo(f"error: daemon unreachable: {exc}", err=True)

# after
msg = f"daemon unreachable: {exc}"
if _json_mode():
    click.echo(json.dumps({"error": {"message": msg}}), err=True)
else:
    click.echo(f"error: {msg}", err=True)
```

**Daemon error path** (JSON-RPC error in response):
```python
# before
click.echo(f"error: {response['error']['message']}", err=True)

# after
msg = response["error"]["message"]
if _json_mode():
    click.echo(json.dumps({"error": {"message": msg}}), err=True)
else:
    click.echo(f"error: {msg}", err=True)
```

### T-A4 — Update `assert_ci.py`'s `_assert_call()` to use `_json_mode`

In `src/rdc/commands/assert_ci.py`, import `_json_mode` from `_helpers` and
replace all three plain-text `click.echo` error paths:

```python
from rdc.commands._helpers import _json_mode
```

- No-session path: emit `{"error": {"message": "no active session"}}` as JSON when
  `_json_mode()` is True, else keep existing plain-text.
- OSError path: emit `{"error": {"message": f"daemon unreachable: {exc}"}}` as JSON when
  `_json_mode()` is True.
- Daemon error path: emit `{"error": {"message": resp['error']['message']}}` as JSON when
  `_json_mode()` is True.

### T-A5 — Write unit tests in `tests/unit/test_json_errors.py` (new file)

Cover all three error paths × two modes (plain / JSON):

- `test_require_session_plain_error` — monkeypatch `load_session` to return
  `None`, invoke any command without `--json`, assert stderr contains
  `"error: no active session"` as plain text.
- `test_require_session_json_error` — same but with `--json`; assert stderr is
  valid JSON with key `"error"`.
- `test_call_oserror_plain` — monkeypatch `send_request` to raise `OSError`,
  assert stderr plain text contains `"daemon unreachable"`.
- `test_call_oserror_json` — same with `--json`; assert stderr is valid JSON.
- `test_call_daemon_error_plain` — monkeypatch `send_request` to return
  `{"error": {"message": "bad method", "code": -32601}}`, assert plain stderr.
- `test_call_daemon_error_json` — same with `--json`; assert stderr is valid
  JSON `{"error": {"message": "bad method"}}`.

Use `CliRunner(mix_stderr=False)` so stdout and stderr are captured separately.
Monkeypatch on `rdc.commands._helpers` (not on individual command modules).

---

## Branch B: `fix/shaders-preload` (Bug B3)

**Goal**: `shaders/search` (and any handler that calls `_build_shader_cache`)
currently performs O(N_draws) `SetFrameEvent` calls in `_collect_pipe_states`,
then a second O(N_unique_shaders) pass in `_build_shader_cache`. Merge into a
single O(N_draws) pass where disassembly happens inline at first-seen. Also add
a `shaders_preload` RPC and `rdc open --preload` flag.

**Files touched** (no overlap with Branch A):
- `src/rdc/daemon_server.py` — add `_pipe_states_cache` field to `DaemonState`; remove `_collect_pipe_states` import and `__all__` entry
- `src/rdc/handlers/_helpers.py` — rewrite `_build_shader_cache`, remove `_collect_pipe_states`/`_collect_pipe_states_recursive`
- `src/rdc/handlers/query.py` — update `_handle_shader_map`, `_handle_shaders`; add `_handle_preload`; register `"shaders_preload"` handler
- `src/rdc/handlers/core.py` — update `count` handler (`what="shaders"`) to use `_build_shader_cache`
- `src/rdc/commands/session.py` — add `--preload` flag to `open_cmd`
- `tests/unit/test_shader_preload.py` (new)

### T-B0 — Update `DaemonState` in `src/rdc/daemon_server.py`

Two changes in `daemon_server.py`:

1. Add `_pipe_states_cache` dataclass field so `_handle_shader_map` / `_handle_shaders`
   can consume pipe states collected during the cache build:

```python
_pipe_states_cache: dict[int, Any] = field(default_factory=dict)
```

2. Remove `_collect_pipe_states` from the import at line 21 and from `__all__` at line 56 —
   it will no longer exist after T-B1.

### T-B1 — Refactor `_build_shader_cache()` in `src/rdc/handlers/_helpers.py` to single pass

Remove `_collect_pipe_states` and `_collect_pipe_states_recursive` entirely.
Rewrite `_build_shader_cache` to do everything in one tree walk:

```
recurse actions tree:
    for each draw/dispatch action:
        SetFrameEvent(a.eventId)
        pipe = get_pipeline_state()
        for each stage in _STAGE_NAMES:
            sid = pipe.GetShader(stage_val)
            if sid == 0: skip
            record eid in shader_eids[sid]
            if sid not in shader_stages (first time seen):
                shader_stages[sid] = [stage_name]
                shader_first_eid[sid] = eid
                GetShaderReflection + DisassembleShader immediately
                populate disasm_cache[sid] + shader_meta[sid]
            else if stage_name not already in shader_stages[sid]:
                shader_stages[sid].append(stage_name)
        recurse into a.children
```

This eliminates the second `SetFrameEvent` loop over unique shaders; total
`SetFrameEvent` calls drop from O(N_draws) + O(N_unique_shaders) to O(N_draws).

Also populate `state._pipe_states_cache` (added in T-B0) with the pipeline
states collected during the walk, so that `_handle_shader_map` / `_handle_shaders`
can reuse them without re-walking the action tree:

```python
state._pipe_states_cache[a.eventId] = pipe  # store for callers
```

Set `state._shader_cache_built = True` at the end (unchanged).

### T-B2 — Update `_handle_shader_map` in `src/rdc/handlers/query.py`

Remove the import of `_collect_pipe_states` from `_helpers`. Update
`_handle_shader_map` to call `_build_shader_cache(state)` and read
`state._pipe_states_cache` instead of calling `_collect_pipe_states` directly:

```python
def _handle_shader_map(...):
    assert state.adapter is not None
    from rdc.services.query_service import collect_shader_map

    _build_shader_cache(state)
    actions = state.adapter.get_root_actions()
    pipe_states = state._pipe_states_cache
    rows = collect_shader_map(actions, pipe_states)
    return _result_response(request_id, {"rows": rows}), True
```

Remove `_collect_pipe_states` from the import list at the top of `query.py`.

### T-B2b — Update `_handle_shaders` in `src/rdc/handlers/query.py`

`_handle_shaders` currently calls `_collect_pipe_states` then `shader_inventory(pipe_states)`.
Replace with:

```python
def _handle_shaders(...):
    assert state.adapter is not None
    from rdc.services.query_service import shader_inventory
    _build_shader_cache(state)
    rows = shader_inventory(state._pipe_states_cache)
    return _result_response(request_id, {"rows": rows}), True
```

Remove `_collect_pipe_states` from the import list in `query.py`.

### T-B2c — Update `count` handler in `src/rdc/handlers/core.py`

The `count` handler with `what="shaders"` (line 61-68) calls `_collect_pipe_states`
then `shader_inventory`. Replace with:

```python
if what == "shaders":
    _build_shader_cache(state)
    n = len(state.shader_meta)
    return _result_response(request_id, {"count": n}), True
```

Remove the local `_collect_pipe_states` import inside the handler.

### T-B3 — Add `_handle_preload` to `src/rdc/handlers/query.py`

New handler that triggers cache build and reports how many unique shaders were
cached:

```python
def _handle_preload(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    _build_shader_cache(state)
    return _result_response(
        request_id,
        {"done": True, "shaders": len(state.disasm_cache)},
    ), True
```

### T-B4 — Register `"shaders_preload"` in `HANDLERS` dict in `query.py`

Add entry to the `HANDLERS` dict at the bottom of `query.py`:

```python
HANDLERS: dict[str, Handler] = {
    ...
    "shaders_preload": _handle_preload,
}
```

Key uses underscore (`shaders_preload`) to match the existing naming convention
of all other handlers (`shader_map`, `shader_targets`, etc.).

### T-B5 — Add `--preload` option to `open` command in `src/rdc/commands/session.py`

```python
@click.command("open")
@click.argument("capture", type=click.Path(path_type=Path))
@click.option("--preload", is_flag=True, default=False, help="Preload shader cache after open.")
def open_cmd(capture: Path, preload: bool) -> None:
    """Create local default session and start daemon skeleton."""
    ok, message = open_session(capture)
    if not ok:
        click.echo(message, err=True)
        raise SystemExit(1)
    click.echo(message)
    click.echo(f"session: {session_path()}")
    if preload:
        result = call("shaders_preload", {})
        click.echo(f"preloaded {result['shaders']} shader(s)")
```

Add `from rdc.commands._helpers import call` to `session.py` (it is not
currently imported there).

### T-B6 — Write unit tests in `tests/unit/test_shader_preload.py` (new file)

- `test_build_shader_cache_single_pass` — use mock adapter with 3 draw actions
  sharing 2 unique shader IDs; assert `SetFrameEvent` called exactly 3 times
  (once per draw), `DisassembleShader` called exactly 2 times (once per unique
  shader), `state.disasm_cache` has 2 entries, `state._pipe_states_cache` has
  3 entries.
- `test_build_shader_cache_idempotent` — call `_build_shader_cache` twice;
  assert `SetFrameEvent` call count does not increase on second call
  (`_shader_cache_built` guard).
- `test_handle_preload_rpc` — call `_handle_preload` via `_handle_request()`
  with `method="shaders_preload"` and mock adapter; assert response is
  `{"done": True, "shaders": <N>}`.
- `test_handle_shader_map_uses_cache` — call `_handle_shader_map`; assert
  `_build_shader_cache` was invoked (monkeypatch it) and `_collect_pipe_states`
  is NOT called.
- `test_open_preload_flag` — use `CliRunner`, monkeypatch `open_session` to
  return `(True, "ok")` and `rdc.commands.session.call` to return
  `{"done": True, "shaders": 5}`; invoke `open_cmd --preload capture.rdc`;
  assert stdout contains `"preloaded 5 shader(s)"` and `call` was invoked
  with method `"shaders_preload"`.
- `test_open_no_preload_flag` — same without `--preload`; assert `call` is NOT
  invoked.
- `test_handle_shaders_uses_cache` — call `_handle_shaders` with mock adapter;
  assert `_build_shader_cache` was invoked and `_collect_pipe_states` is NOT
  called (monkeypatch both).
- `test_count_shaders_uses_cache` — call `count` handler with `what="shaders"`;
  assert result matches `len(state.shader_meta)` and `_collect_pipe_states`
  is NOT called.

---

## Acceptance Criteria

- [ ] `pixi run lint && pixi run test` — zero failures, coverage unchanged.
- [ ] `rdc <any-cmd> --json` — all error conditions (no session, daemon
      unreachable, daemon error response) emit valid JSON to stderr.
- [ ] `rdc <any-cmd>` without `--json` — error output unchanged (plain text).
- [ ] `rdc shaders/search` on any capture: `SetFrameEvent` call count equals
      N_unique_draw_events, not N_unique_draw_events + N_unique_shaders.
- [ ] `rdc open --preload <capture>` — preloads shader cache and prints count.
- [ ] `rdc open <capture>` (no `--preload`) — behaviour identical to before.
- [ ] `shaders_preload` JSON-RPC method available and returns
      `{"done": true, "shaders": N}`.

## Dependencies

Branch A and Branch B are fully independent — no shared files, no ordering
requirement. They can be implemented in parallel worktrees and merged
independently.
