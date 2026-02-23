# Tasks: Remaining Blackbox Bug Fixes + JSON Error Coverage

**Feature branch:** `fix/remaining-blackbox-bugs`
**Spec date:** 2026-02-22

> **GPU golden test philosophy:** Handler-level bugs (B1, B6, B7) MUST have GPU integration tests
> in `tests/test_daemon_handlers_real.py`. The GPU test is the true regression guard — unit tests
> with mocks only validate error handling logic, not correctness against real RenderDoc data.

---

## Agent Assignment

| Agent | Files Owned | Bugs Covered | Parallel? |
|-------|-------------|--------------|-----------|
| Agent A | `src/rdc/daemon_server.py`, `src/rdc/handlers/query.py`, `src/rdc/handlers/debug.py` | B6, B1, B7 | Fully parallel with Agent B |
| Agent B | `src/rdc/commands/info.py`, `src/rdc/commands/assert_ci.py` | B8, B9, PR#84 | Fully parallel with Agent A |
| Agent C | various test files | all | Parallel with A+B; final integration after A+B |

---

## Agent A — Daemon Fixes (B6, B1, B7)

### A1 — B6: Add `_debug_messages_cache` to `DaemonState`

**File:** `src/rdc/daemon_server.py`

Add one field to the `DaemonState` dataclass:

```python
_debug_messages_cache: list[Any] | None = None
```

Place it alongside the other `_`-prefixed cache fields (e.g. near `_shader_cache_built`).

**Acceptance criteria:**
- Field exists in `DaemonState` with type `list[Any] | None` and default `None`.
- No other changes to `daemon_server.py`.

**Dependencies:** none

---

### A2 — B6: Cache `GetDebugMessages()` in `_handle_log`

**File:** `src/rdc/handlers/query.py`

In `_handle_log`, replace the unconditional `controller.GetDebugMessages()` call with a
cache-check-then-populate pattern:

```python
if state._debug_messages_cache is None:
    state._debug_messages_cache = list(controller.GetDebugMessages())
messages = state._debug_messages_cache
```

Then apply any existing level/source filtering to `messages` as before.

The cache is never explicitly invalidated within a session (it is reset by the `DaemonState`
re-instantiation on `session_open`). This is correct: the daemon is single-threaded and the
debug message queue is exhausted after the first call.

**Acceptance criteria:**
- `GetDebugMessages()` is called at most once per session regardless of how many times
  `rdc log` is invoked with any output flag.
- The returned data is identical on all invocations within the same session.

**Dependencies:** A1

---

### A3 — B1: Extract `stage_name` before `_run_debug_loop()` in all three debug handlers

**File:** `src/rdc/handlers/debug.py`

In `_handle_debug_vertex`, `_handle_debug_pixel`, and `_handle_debug_thread`, move the line:

```python
stage_name = _STAGE_NAMES.get(int(trace.stage), str(trace.stage))
```

to immediately after the `controller.DebugVertex()` / `controller.DebugPixel()` /
`controller.DebugThread()` call and **before** the `_run_debug_loop(controller, trace)` call.

`_run_debug_loop` calls `controller.FreeTrace(trace)` in its `finally` block, which invalidates
the trace object. Any attribute access on `trace` after `_run_debug_loop` raises a native
exception on real GPU traces.

**Do NOT** restructure `_run_debug_loop` itself.

**Acceptance criteria:**
- `stage_name` is extracted before `_run_debug_loop` in all three handlers.
- No functional change to the debug loop logic.

**Dependencies:** none

---

### A4 — B1: Wrap debug API calls in try/except

**File:** `src/rdc/handlers/debug.py`

In each of the three debug handlers, wrap the `controller.DebugVertex()`,
`controller.DebugPixel()`, and `controller.DebugThread()` calls in a `try/except Exception`
block that returns a structured error response instead of propagating the exception:

```python
try:
    trace = controller.DebugVertex(eid, vertex_idx, rd.DebugVertexInput())
except Exception as exc:
    return _error_response(request_id, f"DebugVertex failed: {exc}"), True
```

Use the same pattern for `DebugPixel` and `DebugThread`. Do not catch exceptions inside
`_run_debug_loop` — let any loop errors surface as-is since they already have their own
error path.

**Acceptance criteria:**
- A failed `DebugVertex`/`DebugPixel`/`DebugThread` API call returns a structured
  `{"error": {...}}` response, not an unhandled exception.
- `_run_debug_loop` is unchanged.

**Dependencies:** A3 (ordering matters for correctness)

---

### A5 — B7: Enrich per-pass rows with RT_W/RT_H/ATTACHMENTS in `_handle_stats`

**File:** `src/rdc/handlers/query.py`

In `_handle_stats`, after calling `aggregate_stats()` which returns `per_pass` rows
with `rt_w=0`, `rt_h=0`, `attachments=0`, add an enrichment pass:

For each pass row in `per_pass`, pick a representative event ID (the first draw EID in that
pass), call `controller.SetFrameEvent(eid, False)` and `pipe = controller.GetPipelineState()`,
then extract:
- `rt_w`, `rt_h` from `pipe.GetOutputTargets()` viewport or framebuffer dimensions (follow
  the pattern used in `_build_pass_list` / `_set_frame_event` elsewhere in the file).
- `attachments` = number of non-null color attachments + depth attachment (if present).

Update the pass row dict in-place.

If any pipeline query raises an exception for a pass, leave that pass's RT fields as `0`/`-`
and continue (do not abort the entire stats response).

**Acceptance criteria:**
- `rt_w`, `rt_h` are non-zero for passes that include draw calls on real GPU traces.
- `attachments` reflects the actual attachment count.
- Passes with no events gracefully retain `0`/`-` without crashing.

**Dependencies:** none (independent of A1–A4)

---

## Agent B — CLI Fixes (B8, B9, PR#84)

### B1 — B8: Gate section titles on `not no_header` in `stats_cmd`

**File:** `src/rdc/commands/info.py`

Locate the two unconditional `sys.stderr.write(...)` calls that print section titles in
`stats_cmd`:

```python
sys.stderr.write("Per-Pass Breakdown:\n")
...
sys.stderr.write("Top Draws by Triangle Count:\n")
```

Wrap each in `if not no_header:`:

```python
if not no_header:
    sys.stderr.write("Per-Pass Breakdown:\n")
...
if not no_header:
    sys.stderr.write("Top Draws by Triangle Count:\n")
```

**Acceptance criteria:**
- `rdc stats --no-header` produces zero lines of section-title stderr output.
- `rdc stats` (no flag) still prints section titles.

**Dependencies:** none

---

### B2 — B9: Add `@list_output_options` to `stats_cmd`

**File:** `src/rdc/commands/info.py`

`stats_cmd` currently has custom `--json` / `--no-header` options inline. Replace them with
the `@list_output_options` decorator (which provides `--json` as `use_json`, `--jsonl` as
`use_jsonl`, `--no-header` as `no_header`, and `-q`/`--quiet` as `quiet`).

Steps:

1. Add `from rdc.formatters.options import list_output_options` import.
2. Replace the individual `@click.option("--json", ...)` and `@click.option("--no-header", ...)`
   decorators with a single `@list_output_options`.
3. Update the function signature to accept `use_jsonl: bool` and `quiet: bool` (in addition to
   the already-present `use_json` and `no_header`).
4. Add output routing for the new modes. The handler response already contains
   `{"per_pass": [...], "top_draws": [...]}`. Use:
   - `use_jsonl`: write each pass row as a separate JSON line via `write_jsonl(result["per_pass"])`,
     then `write_jsonl(result["top_draws"])`.
   - `quiet`: print `pass["pass"]` per row, one per line, to stdout.
5. Retain the existing `use_json` (full JSON dump) and plain-TSV paths unchanged.

Import additions for `info.py`:

```python
from rdc.formatters.options import list_output_options
from rdc.formatters.json_fmt import write_jsonl
```

**Acceptance criteria:**
- `rdc stats --jsonl` produces valid JSONL (one object per line) with no section titles.
- `rdc stats -q` prints one pass identifier per line.
- `rdc stats --json` behavior is unchanged.
- `rdc stats` (plain) behavior is unchanged.

**Dependencies:** B1 (no_header gating must be present before decorator swap)

---

### B3 — PR#84: Fix JSON error formatting in `_traverse_path()`

**File:** `src/rdc/commands/assert_ci.py`

Three error `click.echo` calls inside `_traverse_path()` (around lines 102, 107, 111) currently
always emit plain text. Replace each with the `_json_mode()` / `_json_error()` pattern already
established in PR #84:

```python
# before
click.echo(f"error: key '{key}' not found in ...", err=True)

# after
msg = f"key '{key}' not found in ..."
if _json_mode():
    click.echo(json.dumps({"error": {"message": msg}}), err=True)
else:
    click.echo(f"error: {msg}", err=True)
```

Apply the same pattern to the index-out-of-range error path.

**Acceptance criteria:**
- `assert-state --json SECTION.bad_key VALUE` emits valid JSON to stderr.
- `assert-state SECTION.bad_key VALUE` (no `--json`) emits unchanged plain text.

**Dependencies:** none

---

### B4 — PR#84: Fix JSON error formatting in `assert_pixel_cmd` validation

**File:** `src/rdc/commands/assert_ci.py`

The validation block in `assert_pixel_cmd` (lines 141–153) has two error paths:
1. Invalid `--expect` format.
2. No passing modification found.

Both call `click.echo(f"error: ...")` unconditionally. Apply `_json_mode()` gating:

```python
msg = "invalid --expect format: ..."
if _json_mode():
    click.echo(json.dumps({"error": {"message": msg}}), err=True)
else:
    click.echo(f"error: {msg}", err=True)
```

**Acceptance criteria:**
- `assert-pixel --json --expect bad_format` emits valid JSON error to stderr.
- `assert-pixel --json` with no passing modification emits valid JSON error to stderr.
- Both paths without `--json` are unchanged.

**Dependencies:** none

---

### B5 — PR#84: Fix JSON error formatting in `assert_state_cmd` invalid-section path

**File:** `src/rdc/commands/assert_ci.py`

The invalid-section error in `assert_state_cmd` (around line 299) calls
`click.echo(f"error: ...")` unconditionally. Apply `_json_mode()` gating identically to B3/B4.

**Acceptance criteria:**
- `assert-state --json bad_section.field value` emits valid JSON error to stderr.
- Without `--json` the behavior is unchanged.

**Dependencies:** none

---

## Agent C — Tests

### C1 — Tests for B6: debug message caching

**File:** `tests/unit/test_info_handlers.py` (or nearest log-handler test file)

1. `test_log_caches_debug_messages` — mock `GetDebugMessages` returning 3 messages; call
   `_handle_log` twice; assert `GetDebugMessages` was called exactly once.
2. `test_log_cache_populated_on_first_call` — assert `state._debug_messages_cache` is `None`
   before the first call and a list after.
3. `test_log_second_call_returns_same_data` — assert both calls return the same message list.

**File:** `tests/test_daemon_handlers_real.py` (GPU test)

4. `test_log_jsonl_not_empty` — on a real capture that has debug messages, invoke `log` twice
   via the daemon; assert neither response returns an empty list (i.e., cache is working).

**Dependencies:** A1, A2

---

### C2 — Tests for B1: stage extraction order

**File:** `tests/unit/test_debug_handlers.py`

1. `test_debug_vertex_stage_extracted_before_free` — mock `DebugVertex` returning a trace
   object whose `.stage` attribute raises `AttributeError` after `FreeTrace` is called;
   assert the handler returns success with a valid `stage` field (i.e., stage was read
   before free).
2. `test_debug_vertex_api_exception_returns_error` — mock `DebugVertex` raising an exception;
   assert response has `"error"` key with a meaningful message, exit rc = 1.
3. `test_debug_pixel_api_exception_returns_error` — same pattern for `DebugPixel`.
4. `test_debug_thread_api_exception_returns_error` — same pattern for `DebugThread`.

**File:** `tests/test_daemon_handlers_real.py` (GPU test)

5. `test_debug_vertex_default_mode_no_internal_error` — call `debug_vertex` on a real capture
   EID with a valid vertex index; assert response has `"inputs"`, `"outputs"`, `"total_steps"`
   and does NOT contain `"internal error"`.

**Dependencies:** A3, A4

---

### C3 — Tests for B7: RT info enrichment

**File:** `tests/unit/test_stats_handlers.py` (or nearest stats-handler test file)

1. `test_stats_rt_fields_populated` — mock `GetPipelineState` returning a pipe state with
   a non-zero viewport; call `_handle_stats`; assert `per_pass[0]["rt_w"]` is non-zero.
2. `test_stats_rt_enrichment_failure_is_silent` — mock `GetPipelineState` raising an exception
   for one pass; assert the other passes are still enriched and the response succeeds.

**File:** `tests/test_daemon_handlers_real.py` (GPU test)

3. `test_stats_rt_w_nonzero_on_real_capture` — call `stats` via daemon on a real capture;
   assert at least one pass row has `rt_w > 0`.

**Dependencies:** A5

---

### C4 — Tests for B8: no-header section titles

**File:** `tests/unit/test_info_commands.py` (or nearest stats-command test file)

1. `test_stats_no_header_suppresses_section_titles` — invoke `stats_cmd` with `--no-header`
   via `CliRunner(mix_stderr=False)`; assert neither `"Per-Pass Breakdown:"` nor `"Top Draws"`
   appears in `result.output` or captured stderr.
2. `test_stats_default_shows_section_titles` — invoke `stats_cmd` without `--no-header`; assert
   section titles are present in stderr.

**Dependencies:** B1

---

### C5 — Tests for B9: JSONL and quiet output for stats

**File:** `tests/unit/test_info_commands.py`

1. `test_stats_jsonl_produces_valid_jsonl` — monkeypatch `send_request` to return a mock stats
   response; invoke `stats_cmd --jsonl`; assert each non-empty stdout line is valid JSON.
2. `test_stats_jsonl_no_section_titles` — same; assert stderr is empty (no section titles in
   JSONL mode because `--jsonl` implies `no_header` behavior OR section titles are still
   conditional on `--no-header`; confirm from proposal).
3. `test_stats_quiet_one_pass_per_line` — invoke `stats_cmd -q`; assert stdout line count
   equals the number of passes in the mock response.
4. `test_stats_json_unchanged` — invoke `stats_cmd --json`; assert stdout is valid JSON object
   with `per_pass` key.

**Dependencies:** B2

---

### C6 — Tests for PR#84: JSON error formatting in assert commands

**File:** `tests/unit/test_assert_ci_commands.py`

1. `test_traverse_path_key_not_found_plain` — monkeypatch handler to return a valid response;
   invoke `assert_state_cmd SECTION.nonexistent_key VALUE` without `--json`; assert stderr
   contains `"error:"` as plain text.
2. `test_traverse_path_key_not_found_json` — same with `--json`; assert stderr is valid JSON
   with `"error"` key.
3. `test_assert_pixel_bad_expect_plain` — invoke `assert_pixel_cmd --expect bad` without
   `--json`; assert plain-text stderr error.
4. `test_assert_pixel_bad_expect_json` — same with `--json`; assert JSON stderr error.
5. `test_assert_state_invalid_section_plain` — invoke `assert_state_cmd bad_section.field val`
   without `--json`; assert plain-text stderr.
6. `test_assert_state_invalid_section_json` — same with `--json`; assert JSON stderr.

Use `CliRunner(mix_stderr=False)` throughout. Monkeypatch on `rdc.commands._helpers` (not on
individual command modules).

**Dependencies:** B3, B4, B5

---

### C7 — CI gate: lint, typecheck, test

**Files:** none (verification only)

1. Run `pixi run check` (ruff lint + mypy + pytest).
2. Fix any lint or type errors introduced by A1–A5, B1–B5.
3. Confirm zero test failures and coverage stays at or above the pre-fix baseline.
4. Run `pixi run test-gpu` to validate GPU golden tests pass on real RenderDoc data.

**Acceptance criteria:**
- `pixi run check` exits 0.
- `pixi run test-gpu` exits 0 with all new GPU golden tests passing.
- Test count is >= pre-fix baseline.

**Dependencies:** all of A1–A5, B1–B5, C1–C6 merged to the feature branch.

---

## File Ownership and Conflict Analysis

| Agent | Files Exclusively Owned |
|-------|------------------------|
| Agent A | `src/rdc/daemon_server.py`, `src/rdc/handlers/query.py`, `src/rdc/handlers/debug.py` |
| Agent B | `src/rdc/commands/info.py`, `src/rdc/commands/assert_ci.py` |
| Agent C | `tests/unit/test_info_handlers.py`, `tests/unit/test_debug_handlers.py`, `tests/unit/test_stats_handlers.py`, `tests/unit/test_info_commands.py`, `tests/unit/test_assert_ci_commands.py`, `tests/test_daemon_handlers_real.py` |

No source file is touched by more than one agent. `tests/test_daemon_handlers_real.py` is owned
exclusively by Agent C; Agent A and Agent B do not modify it.

---

## Parallelization Notes

- **Agent A and Agent B are fully parallel.** No shared source files.
- **Agent C can begin** on tasks C4–C6 (CLI-level tests) in parallel with A+B; tasks C1–C3
  (handler-level and GPU tests) require A1–A5 to be merged first.
- **C7 must run last**, after all other tasks are merged to the feature branch.

Recommended worktree split:
- Worktree 1: Agent A (A1 → A2 → A3+A4 → A5, in order within the worktree)
- Worktree 2: Agent B (B1 → B2, then B3/B4/B5 in any order)
- Worktree 3: Agent C (C4–C6 first, then C1–C3 after Worktree 1 merges, then C7 last)

---

## Completion Checklist

- [ ] `pixi run check` passes with zero errors (C7)
- [ ] `pixi run test-gpu` passes with all new GPU golden tests (C7)
- [ ] B6: `rdc log --jsonl` on a capture with debug messages returns a non-empty array
- [ ] B1: `rdc debug vertex` in default mode never returns `"internal error"` on real GPU traces
- [ ] B7: `rdc stats` per-pass rows show non-zero `RT_W`/`RT_H`/`ATTACHMENTS` on real captures
- [ ] B8: `rdc stats --no-header` produces zero section-title lines in stderr
- [ ] B9: `rdc stats --jsonl` produces valid JSONL; `rdc stats -q` prints one pass per line
- [ ] PR#84: `rdc assert-state --json` emits valid JSON on all error paths
- [ ] PR#84: `rdc assert-pixel --json` emits valid JSON on validation errors
- [ ] PR created via `gh pr create`; CodeRabbit and Greptile reviews checked and addressed
- [ ] Squash merge via `gh pr merge --squash --delete-branch`
- [ ] Archive OpenSpec: `mv openspec/changes/2026-02-22-bugfix-remaining-blackbox openspec/changes/archive/`
- [ ] Update Obsidian `进度跟踪.md` (test count delta, coverage)
- [ ] Update Obsidian `待解决.md` — mark B1, B6, B7, B8, B9 resolved
- [ ] Record any design deviations in `归档/决策记录.md` (next D-NNN)
- [ ] Update MEMORY.md (open bugs list)
