# Test Plan: JSON Error Output + Shader Search Preload

## Scope

**B2 (in):** `_json_mode()` helper, `require_session()` JSON error path, `call()` JSON error
paths (OSError + daemon error), `_assert_call()` JSON error path.

**B3 (in):** Single-pass `_build_shader_cache()` with `SetFrameEvent` call-count verification,
`"shaders_preload"` RPC handler, `--preload` flag on `rdc open`.

**Out:** GPU integration tests (B3 perf improvement is not observable without real capture),
shell completion, VFS formatter, existing search/shader tests (unchanged).

## Test Matrix

| # | Test name | File | Layer | Bug |
|---|-----------|------|-------|-----|
| 1 | `test_require_session_no_json_plain_error` | `test_json_errors.py` | Unit/CLI | B2 |
| 2 | `test_require_session_json_error` | `test_json_errors.py` | Unit/CLI | B2 |
| 3 | `test_call_oserror_plain_error` | `test_json_errors.py` | Unit/CLI | B2 |
| 4 | `test_call_oserror_json_error` | `test_json_errors.py` | Unit/CLI | B2 |
| 5 | `test_call_daemon_error_plain` | `test_json_errors.py` | Unit/CLI | B2 |
| 6 | `test_call_daemon_error_json` | `test_json_errors.py` | Unit/CLI | B2 |
| 7 | `test_assert_ci_json_error_no_session` | `test_json_errors.py` | Unit/CLI | B2 |
| 7b | `test_assert_ci_plain_error_no_session` | `test_json_errors.py` | Unit/CLI | B2 |
| 8 | `test_json_mode_false_without_context` | `test_json_errors.py` | Unit | B2 |
| 9 | `test_build_shader_cache_single_pass` | `test_shader_cache.py` | Unit/Daemon | B3 |
| 10 | `test_build_shader_cache_idempotent` | `test_shader_cache.py` | Unit/Daemon | B3 |
| 11 | `test_build_shader_cache_populates_caches` | `test_shader_cache.py` | Unit/Daemon | B3 |
| 12 | `test_handle_preload_builds_cache` | `test_shader_cache.py` | Unit/Daemon | B3 |
| 13 | `test_handle_preload_idempotent` | `test_shader_cache.py` | Unit/Daemon | B3 |
| 14 | `test_open_preload_flag_calls_rpc` | `test_shader_cache.py` | Unit/CLI | B3 |
| 15 | `test_handle_shaders_uses_cache` | `test_shader_cache.py` | Unit/Daemon | B3 |
| 16 | `test_count_shaders_uses_cache` | `test_shader_cache.py` | Unit/Daemon | B3 |

Total new tests: **16** across 2 new test files.

## B2: JSON Error Output

### Files

- `tests/unit/test_json_errors.py` (new)
- Source under test: `src/rdc/commands/_helpers.py`, `src/rdc/commands/assert_ci.py`

### Approach

Use a minimal dummy Click command that declares `--json` (param name `output_json`) and invokes
`require_session()` or `call()` internally. Run it via `CliRunner`. Monkeypatch
`rdc.commands._helpers.load_session` and `rdc.commands._helpers.send_request` as existing CLI
tests do.

For `_assert_call()` tests, monkeypatch `rdc.commands.assert_ci.load_session` directly (the
module uses its own imports).

### Test Cases

#### 1. `test_require_session_no_json_plain_error`

Setup:
- Dummy command with no `--json` option calls `require_session()`.
- Monkeypatch `load_session` to return `None`.

Assertions:
- `result.exit_code == 1`
- `result.output` (stderr mixed via `mix_stderr=True` default) contains `"error:"` as plain text.
- `result.output` does not start with `{`.

#### 2. `test_require_session_json_error`

Setup:
- Dummy command with `@click.option("--json", "output_json", is_flag=True)` calls
  `require_session()`.
- Monkeypatch `load_session` to return `None`.
- Invoke with `["--json"]`.

Assertions:
- `result.exit_code == 1`
- Stderr content (capture via `CliRunner(mix_stderr=False)`) is valid JSON.
- Parsed JSON has shape `{"error": {"message": <str>}}`.
- `"message"` value is non-empty string.

#### 3. `test_call_oserror_plain_error`

Setup:
- Dummy command (no `--json`) calls `call("ping", {})`.
- Monkeypatch `load_session` to return a fake session object.
- Monkeypatch `send_request` to raise `OSError("connection refused")`.

Assertions:
- `result.exit_code == 1`
- Output contains `"daemon unreachable"` as plain text.
- Output does not start with `{`.

#### 4. `test_call_oserror_json_error`

Setup:
- Dummy command with `--json` option calls `call("ping", {})`.
- Monkeypatch `load_session` to return a fake session.
- Monkeypatch `send_request` to raise `OSError("connection refused")`.
- Invoke with `["--json"]`.

Assertions:
- `result.exit_code == 1`
- Stderr is valid JSON `{"error": {"message": <str>}}`.
- `"message"` contains `"unreachable"` or `"daemon"`.

#### 5. `test_call_daemon_error_plain`

Setup:
- Dummy command (no `--json`) calls `call("ping", {})`.
- Monkeypatch `load_session` to return a fake session.
- Monkeypatch `send_request` to return `{"error": {"message": "no capture loaded"}}`.

Assertions:
- `result.exit_code == 1`
- Output contains `"no capture loaded"` as plain text.
- Output does not start with `{`.

#### 6. `test_call_daemon_error_json`

Setup:
- Dummy command with `--json` calls `call("ping", {})`.
- Monkeypatch as above (daemon error response).
- Invoke with `["--json"]`.

Assertions:
- `result.exit_code == 1`
- Stderr is valid JSON `{"error": {"message": "no capture loaded"}}`.

#### 7. `test_assert_ci_json_error_no_session`

Setup:
- Monkeypatch `rdc.commands.assert_ci.load_session` to return `None`.
- Call `CliRunner().invoke(main, ["assert-count", "draws", "--expect", "1", "--json"])`.

Assertions:
- `result.exit_code == 2`
- Stderr is valid JSON `{"error": {"message": <str>}}` (not plain text).

Note: `_assert_call()` uses `sys.exit(2)` not `SystemExit(1)`.

#### 7b. `test_assert_ci_plain_error_no_session`

Setup:
- Monkeypatch `rdc.commands.assert_ci.load_session` to return `None`.
- Invoke `assert-count draws --expect 1` **without** `--json`.

Assertions:
- `result.exit_code == 2`
- Output contains `"error:"` as plain text (existing behaviour preserved).
- Output does not start with `{`.

#### 8. `test_json_mode_false_without_context`

Setup:
- Call `_json_mode()` directly outside any Click invocation (no active context).

Assertions:
- Return value is `False`.
- No exception is raised.

## B3: Merged Shader Cache + Preload

### Files

- `tests/unit/test_shader_cache.py` (new)
- Source under test: `src/rdc/handlers/_helpers.py` (`_build_shader_cache`),
  `src/rdc/daemon_server.py` (new `"shaders_preload"` handler),
  `src/rdc/commands/session.py` (`open_cmd` with `--preload` flag).

### Approach

Reuse the `controller` / `state` fixture pattern from `tests/unit/test_search.py`: build a
`MockReplayController` with a tracked `SetFrameEvent` call counter, then construct a
`DaemonState` with `RenderDocAdapter`. The counter is the key assertion for the single-pass
guarantee.

For the CLI test (`test_open_preload_flag_calls_rpc`), monkeypatch
`rdc.commands._helpers.load_session` and `rdc.commands._helpers.send_request` to capture RPC
calls; also monkeypatch `rdc.services.session_service.open_session` to return `(True, "opened")`.

### Fixtures

```python
@pytest.fixture()
def tracked_controller():
    """MockReplayController with a SetFrameEvent call counter."""
    ctrl = mock_rd.MockReplayController()
    ctrl._set_frame_event_calls: list[int] = []
    original_sfe = ctrl.SetFrameEvent  # if mock has one

    ns = SimpleNamespace(
        GetRootActions=lambda: [ActionDescription(eventId=10, flags=ActionFlags.Drawcall, ...)],
        GetResources=lambda: [],
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        SetFrameEvent=lambda eid, force: ctrl._set_frame_event_calls.append(eid),
        GetStructuredFile=lambda: SimpleNamespace(chunks=[]),
        GetPipelineState=lambda: _build_pipe(vs_id=100, ps_id=200),
        GetTextures=lambda: [],
        GetBuffers=lambda: [],
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
        DisassembleShader=ctrl.DisassembleShader,
        GetDisassemblyTargets=lambda _with_pipeline: ["SPIR-V"],
    )
    return ns, ctrl._set_frame_event_calls


@pytest.fixture()
def tracked_state(tracked_controller, tmp_path):
    ns, call_log = tracked_controller
    s = DaemonState(capture="test.rdc", current_eid=0, token="tok" * 4)
    s.adapter = RenderDocAdapter(controller=ns, version=(1, 41))
    s.max_eid = 10
    s.rd = mock_rd
    s.temp_dir = tmp_path
    actions = ns.GetRootActions()
    s.vfs_tree = build_vfs_skeleton(actions, [])
    return s, call_log
```

### Test Cases

#### 9. `test_build_shader_cache_single_pass`

Setup:
- `tracked_state` with N draw events (at least 2) sharing distinct shader IDs per draw.
- Call `_build_shader_cache(state)`.

Assertions:
- `len(call_log)` equals the number of unique draw event IDs that have shaders (not the number
  of unique shaders times 2).
- Each EID appears at most once in `call_log` — verify with `len(call_log) == len(set(call_log))`.
- `state.disasm_cache` is non-empty.

This confirms the merged single-pass: `set_frame_event` is called once per draw, not once
during pipe-state collection and again during disassembly.

#### 10. `test_build_shader_cache_idempotent`

Setup:
- `tracked_state`.
- Call `_build_shader_cache(state)` → record `len(call_log)` as `count_first`.
- Mutate `state.disasm_cache[sid] = "sentinel"` for any known sid.
- Call `_build_shader_cache(state)` again.

Assertions:
- `len(call_log)` did not increase after second call (equals `count_first`).
- `state.disasm_cache[sid] == "sentinel"` (sentinel not overwritten).

#### 11. `test_build_shader_cache_populates_caches`

Setup:
- `state` fixture (standard, from `test_search.py` pattern, no call tracking needed).
- Call `_build_shader_cache(state)`.

Assertions:
- `state.disasm_cache` contains entries for both shader IDs (100, 200).
- `state.shader_meta` contains entries for both IDs with correct `"stages"` lists.
- `state.shader_meta[100]["stages"]` contains `"vs"`.
- `state.shader_meta[200]["stages"]` contains `"ps"`.
- VFS subtree populated: `state.vfs_tree.static.get("/shaders/100")` is not `None`.

#### 12. `test_handle_preload_builds_cache`

Setup:
- `state` fixture.
- Send `_handle_request(_req("shaders_preload"), state)` (or `_handle_request` equivalent).

Assertions:
- Response has no `"error"` key.
- `response["result"]["done"] is True`.
- `response["result"]["shaders"]` is an integer > 0.
- `state._shader_cache_built is True`.
- `state.disasm_cache` is non-empty.

#### 13. `test_handle_preload_idempotent`

Setup:
- `state` fixture.
- Call preload handler twice.

Assertions:
- Both responses return `{"done": True, "shaders": N}` with the same N.
- `SetFrameEvent` was not called during the second invocation (verify via sentinel mutation
  approach: mutate `state.disasm_cache` between calls and confirm sentinel survives).

#### 14. `test_open_preload_flag_calls_rpc`

Setup:
- Monkeypatch `rdc.services.session_service.open_session` to return `(True, "opened test.rdc")`.
- Monkeypatch `rdc.commands._helpers.load_session` to return a fake session object.
- Capture RPC calls: monkeypatch `rdc.commands._helpers.send_request` to record payloads and
  return `{"result": {"done": True, "shaders": 2}}`.
- Invoke `CliRunner().invoke(main, ["open", "--preload", "test.rdc"])`.

Assertions:
- `result.exit_code == 0`.
- At least one captured payload has `"method"` == `"shaders_preload"`.
- Output contains expected open message.

#### 15. `test_handle_shaders_uses_cache`

Setup:
- `state` fixture (with mock adapter).
- Monkeypatch `rdc.handlers.query._build_shader_cache` to track calls.
- Monkeypatch `rdc.handlers._helpers._collect_pipe_states` to raise `AssertionError` if called.
- Invoke `_handle_shaders(request_id, {}, state)`.

Assertions:
- `_build_shader_cache` was called exactly once.
- No `AssertionError` from `_collect_pipe_states` (it is not called).
- Response has no `"error"` key.

#### 16. `test_count_shaders_uses_cache`

Setup:
- `state` fixture.
- Monkeypatch `rdc.handlers._helpers._collect_pipe_states` to raise `AssertionError` if called.
- Invoke the `count` handler with `{"what": "shaders"}`.

Assertions:
- No `AssertionError` (confirming `_collect_pipe_states` not called).
- Response `count` equals `len(state.shader_meta)`.

## Assertions Summary

### B2 global assertions

- Plain-text error path: output is a human-readable string starting with `"error:"`.
- JSON error path: output is parseable JSON; top-level key is `"error"`; nested key is
  `"message"` with a non-empty string value.
- Exit codes are unchanged: `SystemExit(1)` for `call()`/`require_session()`, `sys.exit(2)` for
  `_assert_call()`.
- Stdout is not polluted when error goes to stderr.

### B3 global assertions

- `SetFrameEvent` call count after single-pass build equals the number of unique draw EIDs that
  have at least one active shader, not a multiple of it.
- Cache idempotency: second `_build_shader_cache()` call is a no-op (sentinel pattern).
- `"shaders_preload"` RPC is well-formed JSON-RPC 2.0 response.
- CLI `--preload` flag integration does not break the default `rdc open` (flag is optional).

## Risks

- **B2 `_json_mode()` detection strategy**: The helper must inspect the active Click context
  parameter list. If the detection approach differs from the proposal (e.g., thread-local vs.
  `click.get_current_context()`), test #8 may need adjustment.
- **B3 `SetFrameEvent` caching**: `_set_frame_event` in `_helpers.py` already has an EID cache
  (`state._eid_cache`). The single-pass verification must account for this — if two draws share
  the same EID, only one `SetFrameEvent` call is expected regardless.
- **`"shaders_preload"` routing**: The new handler must be registered in the dispatch table in
  `daemon_server.py`. If registration is missing, test #12 will fail with a `"method not found"`
  error response rather than a test infrastructure failure.

## Rollback

- B2: Remove `_json_mode()` helper and revert error branches in `_helpers.py` and `assert_ci.py`.
- B3: Remove `--preload` option from `open_cmd`; remove `"shaders_preload"` handler registration;
  the `_build_shader_cache` single-pass refactor is backward-compatible and can remain.
