# Test Plan: Remaining Blackbox Bug Fixes (B1, B6-B9 + PR #84) (2026-02-22)

## 1. Overview

**Scope:** Unit tests covering all five open blackbox bugs (B1, B6-B9) and the incomplete JSON
error coverage left by PR #84 in `assert_ci.py`.

**Strategy:** CLI-layer tests use `CliRunner` + monkeypatch on `rdc.commands._helpers`
(`load_session`, `send_request`). Handler-layer tests call `_handle_request()` directly with a
`DaemonState` + `MockReplayController`. B6 daemon-unit tests call `_handle_log()` directly to
verify the caching contract without going through the CLI layer.

**Regression policy:** Every test group includes at least one regression case to confirm that
the happy paths that existed before the fix still pass.

**Target files:**

| Bug | Unit test file |
|-----|---------------|
| B6 (log caching) | `tests/unit/test_daemon_server_unit.py` |
| B1 (debug stage extraction) | `tests/unit/test_debug_handlers.py` |
| B7 (stats RT enrichment) | `tests/unit/test_info_commands.py` |
| B8 (stats --no-header section titles) | `tests/unit/test_info_commands.py` |
| B9 (stats --jsonl/-q) | `tests/unit/test_info_commands.py` |
| PR #84 (assert_ci JSON errors) | `tests/unit/test_assert_ci_commands.py` |

CI gate: `pixi run lint && pixi run test` must pass with zero failures before PR.

---

## 2. Test Matrix

| ID | Test name | File | Layer | Bug |
|----|-----------|------|-------|-----|
| B6-H-01 | `test_log_cache_populated_on_first_call` | `test_daemon_server_unit.py` | Handler | B6 |
| B6-H-02 | `test_log_cache_returned_on_second_call` | `test_daemon_server_unit.py` | Handler | B6 |
| B6-H-03 | `test_log_cache_respects_level_filter` | `test_daemon_server_unit.py` | Handler | B6 |
| B6-H-04 | `test_log_cache_respects_eid_filter` | `test_daemon_server_unit.py` | Handler | B6 |
| B6-C-01 | `test_log_json_nonempty_after_prior_call` | `test_info_commands.py` | CLI | B6 |
| B1-H-01 | `test_debug_vertex_stage_extracted_before_free` | `test_debug_handlers.py` | Handler | B1 |
| B1-H-02 | `test_debug_pixel_stage_extracted_before_free` | `test_debug_handlers.py` | Handler | B1 |
| B1-H-03 | `test_debug_thread_stage_extracted_before_free` | `test_debug_handlers.py` | Handler | B1 |
| B1-H-04 | `test_debug_vertex_api_exception_structured_error` | `test_debug_handlers.py` | Handler | B1 |
| B1-H-05 | `test_debug_pixel_api_exception_structured_error` | `test_debug_handlers.py` | Handler | B1 |
| B1-H-06 | `test_debug_thread_api_exception_structured_error` | `test_debug_handlers.py` | Handler | B1 |
| B1-R-01 | `test_debug_pixel_happy_path` (existing — must pass) | `test_debug_handlers.py` | Handler | B1 |
| B7-H-01 | `test_stats_rt_dimensions_from_pipeline` | `test_info_commands.py` | CLI | B7 |
| B7-H-02 | `test_stats_rt_fallback_on_pipeline_failure` | `test_info_commands.py` | CLI | B7 |
| B7-H-03 | `test_stats_per_pass_rt_fields_populated` | `test_info_commands.py` | CLI | B7 |
| B8-C-01 | `test_stats_no_header_suppresses_section_titles` | `test_info_commands.py` | CLI | B8 |
| B8-C-02 | `test_stats_default_shows_section_titles` | `test_info_commands.py` | CLI | B8 |
| B8-R-01 | `test_stats_no_header` (existing — must pass) | `test_info_commands.py` | CLI | B8 |
| B9-C-01 | `test_stats_jsonl_valid_lines` | `test_info_commands.py` | CLI | B9 |
| B9-C-02 | `test_stats_jsonl_per_pass_structure` | `test_info_commands.py` | CLI | B9 |
| B9-C-03 | `test_stats_quiet_pass_names_only` | `test_info_commands.py` | CLI | B9 |
| B9-R-01 | `test_stats_json` (existing — must pass) | `test_info_commands.py` | CLI | B9 |
| P84-C-01 | `test_traverse_path_key_not_found_json_error` | `test_assert_ci_commands.py` | CLI | PR#84 |
| P84-C-02 | `test_traverse_path_invalid_index_json_error` | `test_assert_ci_commands.py` | CLI | PR#84 |
| P84-C-03 | `test_assert_pixel_bad_expect_json_error` | `test_assert_ci_commands.py` | CLI | PR#84 |
| P84-C-04 | `test_assert_pixel_no_passing_mod_json_error` | `test_assert_ci_commands.py` | CLI | PR#84 |
| P84-C-05 | `test_assert_state_invalid_section_json_error` | `test_assert_ci_commands.py` | CLI | PR#84 |
| P84-R-01 | `test_assert_pixel_exact_match` (existing — must pass) | `test_assert_ci_commands.py` | CLI | PR#84 |

Total new tests: **23** across 2 test files.

---

## 3. Bug-by-Bug Test Cases

### B6: Log message caching

**Root cause:** `controller.GetDebugMessages()` consumes the internal queue on first call.
Subsequent calls within the same session return an empty list. Structured output modes
(`--json`, `--jsonl`, `--no-header`, `-q`) that reach `_handle_log()` a second time receive
nothing.

**Fix:** Add `_debug_messages_cache: list[Any] | None = None` to `DaemonState`. On the
first `_handle_log()` call, populate the cache from `GetDebugMessages()` and store it.
On subsequent calls, read from the cache. Clear the cache on `session_open`/`session_close`.

**Source under test:** `src/rdc/handlers/query.py` (`_handle_log`), `src/rdc/daemon_server.py`
(`DaemonState`).

**Test approach:** Build a `DaemonState` with a `MockReplayController` whose
`GetDebugMessages()` returns a non-empty list exactly once (a call counter enforces this).
Call `_handle_log()` twice and verify that both responses contain the same messages.

#### B6-H-01: `test_log_cache_populated_on_first_call`

Setup:
- `MockReplayController` with `GetDebugMessages` returning two messages on the first call and
  an empty list on every subsequent call. Track call count via a closure counter.
- Build `DaemonState` with no prior cache (`_debug_messages_cache is None`).

Assertions:
- After calling `_handle_log(req, {}, state)` once, `state._debug_messages_cache` is not
  `None`.
- `len(state._debug_messages_cache) == 2`.
- `GetDebugMessages` was called exactly once (counter == 1).

#### B6-H-02: `test_log_cache_returned_on_second_call`

Setup:
- Same `MockReplayController` as B6-H-01.
- Call `_handle_log()` once to prime the cache.

Assertions:
- Call `_handle_log()` a second time with identical params.
- Second response `result["messages"]` has length 2 (not 0).
- `GetDebugMessages` was NOT called a second time (counter still == 1).

#### B6-H-03: `test_log_cache_respects_level_filter`

Setup:
- Two cached messages: one with severity HIGH, one with INFO.
- Cache pre-populated via first call.

Assertions:
- Second call with `params={"level": "HIGH"}` returns only the HIGH message.
- Third call with `params={"level": "INFO"}` returns only the INFO message.
- `GetDebugMessages` still called exactly once total.

#### B6-H-04: `test_log_cache_respects_eid_filter`

Setup:
- Two cached messages: `{"eid": 0, ...}` and `{"eid": 42, ...}`.
- Cache pre-populated via first call.

Assertions:
- Second call with `params={"eid": 42}` returns only the eid=42 message.
- `GetDebugMessages` called exactly once total.

#### B6-C-01: `test_log_json_nonempty_after_prior_call`

**Note:** This is a CLI integration test that simulates the scenario where the daemon has
already served `log` once and a second `log --json` call returns the correct data. Since unit
tests monkeypatch `send_request` rather than running a real daemon, this test verifies the
CLI-layer routing rather than the caching itself (caching is verified by B6-H-01/02).

Setup:
- Monkeypatch `rdc.commands._helpers.send_request` to return
  `{"result": {"messages": [{"level": "HIGH", "eid": 0, "message": "err"}]}}`.
- Invoke `CliRunner().invoke(main, ["log", "--json"])`.

Assertions:
- `result.exit_code == 0`.
- Output is valid JSON.
- Parsed `messages` array has length 1.
- `messages[0]["level"] == "HIGH"`.

---

### B1: Debug stage extraction before FreeTrace

**Root cause:** In `_handle_debug_vertex/pixel/thread`, `stage_name = _STAGE_NAMES.get(int(trace.stage), ...)` is evaluated after `_run_debug_loop()`. `_run_debug_loop()` calls `controller.FreeTrace(trace)` in its `finally` block, invalidating the trace object. On real GPU traces, accessing `trace.stage` after `FreeTrace` raises a native exception caught by the daemon's generic handler as `"internal error"`.

**Fix:** Extract `stage_name` immediately after the `DebugVertex`/`DebugPixel`/`DebugThread`
API call and before `_run_debug_loop()`. Also wrap the API call itself in try/except and return
a structured error (not an unhandled exception) if the API call fails.

**Source under test:** `src/rdc/handlers/debug.py`.

**Test approach:** For stage-extraction tests, produce a `MockReplayController` where
`trace.stage` is set correctly and `FreeTrace` invalidates the trace object (sets
`trace.stage = None` or raises on attribute access). Verify that `stage_name` in the response
matches the stage set before `FreeTrace`. For API-exception tests, make `DebugVertex` etc.
raise a `RuntimeError` and verify a structured error response is returned.

**Fixture note:** Reuse `_make_state`, `_make_trace`, and `_req` helpers already defined in
`test_debug_handlers.py`.

#### B1-H-01: `test_debug_vertex_stage_extracted_before_free`

Setup:
- `MockReplayController` where `DebugVertex` returns a trace with `stage = rd.ShaderStage.Vertex`
  and `debugger` is a valid object.
- Extend `FreeTrace` to set a sentinel on the trace that would cause `int(trace.stage)` to
  raise after the call (e.g., `trace.stage = None`).
- `state = _make_state(ctrl)`.

Assertions:
- Call `_handle_request(_req("debug_vertex", {"eid": 100, "vtx_id": 0}), state)`.
- Response has no `"error"` key.
- `response["result"]["stage"] == "vs"`.

#### B1-H-02: `test_debug_pixel_stage_extracted_before_free`

Setup and assertions mirror B1-H-01 but for `DebugPixel`:
- Trace has `stage = rd.ShaderStage.Pixel`.
- Call `_handle_request(_req("debug_pixel", {"eid": 100, "x": 320, "y": 240}), state)`.
- `response["result"]["stage"] == "ps"`.

#### B1-H-03: `test_debug_thread_stage_extracted_before_free`

Setup and assertions mirror B1-H-01 but for `DebugThread`:
- Trace has `stage = rd.ShaderStage.Compute`.
- Call `_handle_request(_req("debug_thread", {"eid": 100, "group_x": 0, "group_y": 0,
  "group_z": 0, "thread_x": 0, "thread_y": 0, "thread_z": 0}), state)`.
- `response["result"]["stage"] == "cs"`.

#### B1-H-04: `test_debug_vertex_api_exception_structured_error`

Setup:
- `MockReplayController` where `DebugVertex` raises `RuntimeError("shader not bound")`.
- `state = _make_state(ctrl)`.

Assertions:
- Call `_handle_request(_req("debug_vertex", {"eid": 100, "vtx_id": 0}), state)`.
- Response has `"error"` key.
- `response["error"]["code"]` is an integer (e.g., -32603 or -32007).
- `response["error"]["message"]` is a non-empty string; does NOT equal `"internal error"`.
- No unhandled exception propagates.

#### B1-H-05: `test_debug_pixel_api_exception_structured_error`

Setup:
- `MockReplayController` where `DebugPixel` raises `RuntimeError("no fragment")`.
- `state = _make_state(ctrl)`.

Assertions:
- Call `_handle_request(_req("debug_pixel", {"eid": 100, "x": 0, "y": 0}), state)`.
- Response has `"error"` key with non-empty, non-`"internal error"` message.

#### B1-H-06: `test_debug_thread_api_exception_structured_error`

Setup:
- `MockReplayController` where `DebugThread` raises `RuntimeError("compute unavailable")`.
- `state = _make_state(ctrl)`.

Assertions:
- Call `_handle_request(_req("debug_thread", {...}), state)`.
- Response has `"error"` key with informative message.

#### B1-R-01: Regression guard

`test_debug_pixel_happy_path` (already exists in `test_debug_handlers.py`) must continue to
pass unchanged. No modification to that test case.

---

### B7: Stats RT info enrichment

**Root cause:** `aggregate_stats()` initializes `rt_w`, `rt_h`, and `attachments` to 0/`"-"`
and never updates them. `_handle_stats` does not query pipeline state to populate render-target
dimensions.

**Fix:** After `aggregate_stats()`, iterate per-pass rows and query `GetPipelineState()` at a
representative EID within each pass to extract framebuffer dimensions and attachment counts.

**Source under test:** `src/rdc/handlers/query.py` (`_handle_stats`).

**Test approach:** CLI tests patch `send_request` to return a response that now contains
non-zero `rt_w`/`rt_h`/`attachments`, verifying that the CLI correctly renders these fields.
The handler-level correctness (that the enrichment actually happens) is verified by a handler
unit test added to `test_daemon_server_unit.py` or a new handler test file if preferred.

For CLI-layer tests, add to `test_info_commands.py`.

#### B7-H-01: `test_stats_rt_dimensions_from_pipeline`

Setup:
- Monkeypatch `send_request` to return:
  ```json
  {
    "per_pass": [{"name": "Main", "draws": 5, "dispatches": 0, "triangles": 1000,
                  "rt_w": 1920, "rt_h": 1080, "attachments": 2}],
    "top_draws": []
  }
  ```
- Invoke `CliRunner().invoke(main, ["stats"])`.

Assertions:
- `result.exit_code == 0`.
- `"1920"` in `result.output`.
- `"1080"` in `result.output`.
- `"2"` in `result.output`.

#### B7-H-02: `test_stats_rt_fallback_on_pipeline_failure`

Setup:
- Monkeypatch `send_request` to return per-pass row with `rt_w=0`, `rt_h=0`,
  `attachments=0` (the fallback values when pipeline query fails).
- Invoke `CliRunner().invoke(main, ["stats"])`.

Assertions:
- `result.exit_code == 0`.
- Output renders without crashing (shows `0` or `"-"` for those columns, not a traceback).

#### B7-H-03: `test_stats_per_pass_rt_fields_populated`

Setup:
- Two passes in `per_pass`, each with different `rt_w`/`rt_h`/`attachments` values.
- Invoke `CliRunner().invoke(main, ["stats", "--json"])`.

Assertions:
- `result.exit_code == 0`.
- Parsed JSON `per_pass[0]["rt_w"]` and `per_pass[1]["rt_w"]` match the mocked values.
- Both passes have `attachments` field present in JSON output.

---

### B8: Stats --no-header section titles

**Root cause:** "Per-Pass Breakdown:" and "Top Draws by Triangle Count:" section titles are
written to stderr unconditionally in `stats_cmd`, bypassing the `--no-header` flag.

**Fix:** Wrap each section-title `sys.stderr.write(...)` call in `if not no_header:`.

**Source under test:** `src/rdc/commands/info.py` (`stats_cmd`).

**Test approach:** `CliRunner(mix_stderr=True)` (default) captures both stdout and stderr in
`result.output`. Use `CliRunner(mix_stderr=False)` when asserting stderr-only content.

#### B8-C-01: `test_stats_no_header_suppresses_section_titles`

Setup:
- Monkeypatch `send_request` with a response containing one pass and one top-draw entry.
- Invoke `CliRunner(mix_stderr=False).invoke(main, ["stats", "--no-header"])`.

Assertions:
- `result.exit_code == 0`.
- `result.output` (stdout) does NOT contain `"Per-Pass Breakdown:"`.
- `result.output` does NOT contain `"Top Draws"`.
- Captured stderr (`result.stderr` from `mix_stderr=False` runner) does NOT contain
  `"Per-Pass Breakdown:"`.
- Data rows ARE present (pass name appears in stdout).

#### B8-C-02: `test_stats_default_shows_section_titles`

Setup:
- Same monkeypatch as B8-C-01.
- Invoke `CliRunner(mix_stderr=True).invoke(main, ["stats"])` (default mode with header).

Assertions:
- `result.exit_code == 0`.
- `result.output` contains `"Per-Pass Breakdown:"` or `"Top Draws"` (section titles present).
- Column header `"PASS"` is present.

#### B8-R-01: Regression guard

`test_stats_no_header` (already exists in `test_info_commands.py`) must continue to pass
unchanged. That test already asserts `"PASS" not in result.output`; after the fix it must also
not contain section titles.

---

### B9: Stats --jsonl/-q support

**Root cause:** `stats_cmd` uses a custom `--json`/`--no-header` option set instead of
`@list_output_options`, so `--jsonl` and `-q` are absent.

**Fix:** Replace custom options with `@list_output_options` (which provides `--json`,
`--jsonl`, `-q`, `--no-header`). Update output routing accordingly.

**Source under test:** `src/rdc/commands/info.py` (`stats_cmd`).

**Monkeypatch shape for B9 tests:**

```python
_STATS_RESPONSE = {
    "per_pass": [
        {"name": "Main", "draws": 10, "dispatches": 0, "triangles": 5000,
         "rt_w": 1920, "rt_h": 1080, "attachments": 3},
        {"name": "Shadow", "draws": 4, "dispatches": 0, "triangles": 2000,
         "rt_w": 1024, "rt_h": 1024, "attachments": 1},
    ],
    "top_draws": [{"eid": 42, "marker": "Geo", "triangles": 3000}],
}
```

#### B9-C-01: `test_stats_jsonl_valid_lines`

Setup:
- Monkeypatch `send_request` with `_STATS_RESPONSE`.
- Invoke `CliRunner().invoke(main, ["stats", "--jsonl"])`.

Assertions:
- `result.exit_code == 0`.
- `result.output` is non-empty.
- Every non-empty line in `result.output` is valid JSON (parse each with `json.loads`).
- No `json.JSONDecodeError` raised during parsing.

#### B9-C-02: `test_stats_jsonl_per_pass_structure`

Setup:
- Same monkeypatch.
- Invoke `CliRunner().invoke(main, ["stats", "--jsonl"])`.

Assertions:
- `result.exit_code == 0`.
- Lines include at least one object with `"name"` == `"Main"`.
- Each per-pass line has at least `"draws"` and `"triangles"` keys.

#### B9-C-03: `test_stats_quiet_pass_names_only`

Setup:
- Monkeypatch `send_request` with `_STATS_RESPONSE`.
- Invoke `CliRunner().invoke(main, ["stats", "-q"])`.

Assertions:
- `result.exit_code == 0`.
- Output contains `"Main"` and `"Shadow"`.
- Output does NOT contain `"PASS"` (no column header).
- Output does NOT contain `"{"` (no JSON objects, only names).

#### B9-R-01: Regression guard

`test_stats_json` (already exists in `test_info_commands.py`) must continue to pass. It
invokes `stats --json` and asserts `"per_pass" in result.output`. After replacing the decorator
this must still hold.

---

### PR #84: assert_ci.py JSON error formatting (incomplete coverage)

**Root cause:** PR #84 applied `_json_mode()` / `_json_error()` to main success/failure paths,
but three error paths in `assert_ci.py` still emit plain text unconditionally:
1. `_traverse_path()` — key-not-found (line 106) and invalid-index (line 102) errors.
2. `assert_pixel_cmd` — `--expect` format validation errors (lines 141, 146).
3. `assert_pixel_cmd` — no-passing-modification error (line 153).
4. `assert_state_cmd` — invalid-section error (line 299).

**Fix:** In each error branch, check `_json_mode()` and emit JSON if true, else fall back to
`click.echo(f"error: ...")`.

**Source under test:** `src/rdc/commands/assert_ci.py`.

**Test approach:** Use `CliRunner(mix_stderr=False)` to capture stderr separately. All error
paths in `assert_ci.py` write to stderr (`err=True`). Monkeypatch `_assert_call` via
`mod._assert_call` (the `assert_ci` module-level binding) to return controlled data without
a real daemon. For path-traversal tests, use `assert-state` with a mock that returns a known
dict, then provide a key path that is guaranteed to fail traversal.

#### P84-C-01: `test_traverse_path_key_not_found_json_error`

Setup:
- Monkeypatch `mod._assert_call` (where `mod = rdc.commands.assert_ci`) to return
  `{"topology": "TriangleList"}` (no `"eid"` key, which the real handler always returns, but
  the test path must include a non-existent key).
- Invoke `CliRunner(mix_stderr=False).invoke(main,
  ["assert-state", "100", "topology.nonexistent", "--expect", "x", "--json"])`.

Assertions:
- `result.exit_code == 2`.
- `result.stderr` is valid JSON.
- Parsed JSON has `{"error": {"message": <str>}}` shape.
- `"message"` contains `"not found"` or `"nonexistent"`.
- `result.output` (stdout) is empty or does not contain a plain `"error:"` prefix.

#### P84-C-02: `test_traverse_path_invalid_index_json_error`

Setup:
- Monkeypatch `mod._assert_call` to return `{"blends": [{"enabled": True}]}`.
- Invoke `CliRunner(mix_stderr=False).invoke(main,
  ["assert-state", "100", "blend.99", "--expect", "true", "--json"])`.

Assertions:
- `result.exit_code == 2`.
- `result.stderr` is valid JSON `{"error": {"message": <str>}}`.
- `"message"` references the invalid segment or index.

#### P84-C-03: `test_assert_pixel_bad_expect_json_error`

Setup:
- Monkeypatch `mod._assert_call` to a no-op (not called due to early exit).
- Invoke `CliRunner(mix_stderr=False).invoke(main,
  ["assert-pixel", "88", "512", "384", "--expect", "1.0 2.0", "--json"])`.
  (Only 2 floats instead of 4.)

Assertions:
- `result.exit_code == 2`.
- `result.stderr` is valid JSON `{"error": {"message": <str>}}`.
- `"message"` references the 4-float requirement.

#### P84-C-04: `test_assert_pixel_no_passing_mod_json_error`

Setup:
- Monkeypatch `mod._assert_call` to return `{"modifications": [{"eid": 88, "passed": False,
  "post_mod": {"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0}}]}`.
- Invoke `CliRunner(mix_stderr=False).invoke(main,
  ["assert-pixel", "88", "512", "384", "--expect", "0.5 0.3 0.1 1.0", "--json"])`.

Assertions:
- `result.exit_code == 2`.
- `result.stderr` is valid JSON `{"error": {"message": <str>}}`.
- `"message"` contains `"no passing modification"` or equivalent.

#### P84-C-05: `test_assert_state_invalid_section_json_error`

Setup:
- Monkeypatch `mod._assert_call` to a no-op (not called due to early exit).
- Invoke `CliRunner(mix_stderr=False).invoke(main,
  ["assert-state", "100", "bogussection", "--expect", "x", "--json"])`.

Assertions:
- `result.exit_code == 2`.
- `result.stderr` is valid JSON `{"error": {"message": <str>}}`.
- `"message"` references `"bogussection"` or `"invalid section"`.

#### P84-R-01: Regression guard

`test_assert_pixel_exact_match` (already exists in `test_assert_ci_commands.py`) must
continue to pass. That test invokes `assert-pixel` without `--json` and asserts
`result.output.startswith("pass:")`. The fix must not alter the success path.

---

## 4. Assertions Summary

### Global JSON error assertions (PR #84)

All JSON error cases share these invariants:
- `result.exit_code == 2` (assert_ci errors use `sys.exit(2)`).
- `result.stderr` is parseable with `json.loads` (no `JSONDecodeError`).
- Parsed JSON top-level key is `"error"`.
- Parsed `"error"` dict has key `"message"` with a non-empty string value.
- `result.output` (stdout) does not contain `"error:"` as a plain-text prefix.

### B6 caching invariants

- `GetDebugMessages()` is called at most once per session regardless of how many times
  `_handle_log()` is invoked.
- Filter params (`level`, `eid`) are applied to the cached list, not re-fetched from the API.
- The cached list has the same length and content as what was returned on the first call.

### B8 no-header invariants

- Without `--no-header`: column header AND section titles are present.
- With `--no-header`: column header AND section titles are both absent.
- Data rows are present in both cases.

### B9 output-mode invariants

- `--jsonl`: every output line is valid JSON; no column headers.
- `-q`: one pass name per line; no JSON, no column headers.
- `--json`: full JSON object (existing behaviour unchanged).
- `--no-header` (existing): TSV rows without column header (existing behaviour unchanged).

---

## 5. Regression Coverage

Existing tests that must remain green after each fix:

| Bug fixed | Existing tests that must still pass |
|-----------|-------------------------------------|
| B6 | `test_log_tsv`, `test_log_json`, `test_log_with_level_filter`, `test_log_with_eid_filter`, `test_log_no_header_regression`, `test_log_jsonl`, `test_log_quiet` |
| B1 | `test_debug_pixel_happy_path`, `test_debug_pixel_missing_eid` in `test_debug_handlers.py` |
| B7 | `test_stats_tsv`, `test_stats_json`, `test_stats_empty` in `test_info_commands.py` |
| B8 | `test_stats_no_header` in `test_info_commands.py` |
| B9 | `test_stats_json`, `test_stats_tsv`, `test_stats_no_header` in `test_info_commands.py` |
| PR #84 | `test_assert_pixel_exact_match`, `test_assert_pixel_within_tolerance`, `test_assert_pixel_no_passing_mod`, `test_assert_call_success`, `test_assert_call_rpc_error` in `test_assert_ci_commands.py` |

---

## 6. Out of Scope

- GPU integration tests (all bugs in this batch are unit-testable without a real capture).
- `assert-clean` JSON error paths (not flagged as incomplete in the proposal).
- `_traverse_path` plain-text (non-`--json`) paths — existing behaviour is correct.
- `debug thread` beyond B1-H-03/B1-H-06 (stage extraction fix is the full scope).
- New JSON-RPC methods or CLI commands.
