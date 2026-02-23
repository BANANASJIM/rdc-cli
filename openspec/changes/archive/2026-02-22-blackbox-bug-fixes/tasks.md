# Tasks: Blackbox Bug Fixes

**Feature branch:** `fix/blackbox-bug-fixes`
**Spec date:** 2026-02-22

> **GPU golden test philosophy:** Every bug fix MUST have a GPU integration test in
> `tests/test_daemon_handlers_real.py`. The GPU test is the true validation that the fix
> works on real RenderDoc data — unit tests with mocks only validate error handling logic,
> not correctness. Mocks can create false positives when their behavior diverges from real
> API behavior.

---

## Task List

### T0 — Add `hello_triangle_replay` fixture to `conftest.py`

**Files to modify:**
- `tests/conftest.py`

**Work:**
Add a `hello_triangle_replay` session fixture mirroring `vkcube_replay` but opening
`hello_triangle.rdc`. GPU golden tests for T1–T4 and T6 depend on this fixture.

```python
@pytest.fixture(scope="session")
def hello_triangle_replay(rd_init: Any) -> Generator[tuple[Any, Any, Any], None, None]:
    """Open hello_triangle.rdc and yield (cap, controller, structured_file)."""
    rd = rd_init
    cap = rd.OpenCaptureFile()
    rdc_path = str(FIXTURES_DIR / "hello_triangle.rdc")
    result = cap.OpenFile(rdc_path, "", None)
    assert result == rd.ResultCode.Succeeded
    assert cap.LocalReplaySupport() == rd.ReplaySupport.Supported
    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    assert result == rd.ResultCode.Succeeded
    sf = cap.GetStructuredData()
    yield cap, controller, sf
    controller.Shutdown()
    cap.Shutdown()
```

**Dependencies:** none (prerequisite for T1–T4, T6 GPU tests)

---

### T1 — `debug vertex` internal error in `_run_debug_loop`

**Files to modify:**
- `src/rdc/handlers/debug.py`
- `tests/unit/test_debug_handlers.py`
- `tests/test_daemon_handlers_real.py`

**Work:**
1. In `_run_debug_loop`, wrap the `controller.ContinueDebug()` and `_format_step()` calls
   in a `try/except Exception` block that returns `_error_response()` with a meaningful
   message instead of propagating an unhandled exception to the client.
2. Add unit tests in `test_debug_handlers.py`:
   - Mock `ContinueDebug` raising an exception → structured error response, not exception.
   - Mock `_format_step` raising an exception → structured error response, not exception.
3. Add GPU golden test in `test_daemon_handlers_real.py`: call `debug_vertex` on
   hello_triangle EID=11, vertex=0 → must return success with `inputs`, `outputs`, and
   `total_steps` fields present. (This test was failing before the fix and serves as the
   true regression guard.)

**Note:** Do NOT touch `_extract_inputs_outputs` — that function handles empty steps
gracefully and is not the failure point.

**Acceptance criteria:**
- `debug vertex` with default mode never returns an unhandled internal error to the client.
- Unit tests cover both `ContinueDebug` raise path and `_format_step` raise path.
- GPU golden test passes: `debug_vertex` EID=11 vertex=0 returns success with
  `inputs`/`outputs`/`total_steps`.

**Dependencies:** none

---

### T2 — `debug pixel` exit code always 0 on error

**Files to modify:**
- `src/rdc/commands/debug.py`
- `tests/unit/test_debug_commands.py`
- `tests/test_daemon_handlers_real.py`

**Work:**
1. Root cause is unconfirmed; fix defensively. Audit `pixel_cmd` in `commands/debug.py`:
   add an explicit error check on the result of `_daemon_call` before entering the output
   mode branch (`--json`, `--trace`, `--dump-at`, plain). Ensure all branches propagate
   `rc=1` when the daemon indicates an error.
2. Add unit tests in `test_debug_commands.py` asserting `result.exit_code == 1` for each
   of the three output modes (plain, `--json`, `--trace`/`--dump-at`) when the daemon
   returns an error response.
3. Add GPU golden test in `test_daemon_handlers_real.py`: call `debug_pixel` on
   hello_triangle EID=11, x=640, y=360, plain mode → `rc=0`. (Before the fix this path
   was returning rc=0 even on error; the GPU test confirms the correct happy-path behavior
   is preserved.)

**Acceptance criteria:**
- `debug pixel` exits with `rc=1` on daemon error for all output modes.
- Unit tests cover plain, `--json`, and `--trace`/`--dump-at` error cases.
- GPU golden test passes: `debug_pixel` EID=11 x=640 y=360 returns rc=0.

**Dependencies:** none

---

### T3 — `tex-stats --mip/--slice` out-of-bounds not validated

**Files to modify:**
- `src/rdc/handlers/texture.py`
- `tests/unit/test_tex_stats_commands.py` (or the handler-level test file if no command
  test exists)
- `tests/test_daemon_handlers_real.py`

**Work:**
1. In `_handle_tex_stats`, add bounds validation for `mip` and `slice` parameters before
   use — copy the pattern from `_handle_tex_export` in the same file.
2. Return a structured error response (not a crash) when out-of-bounds.
3. Add unit tests: valid mip/slice → success, out-of-bounds mip → error response,
   out-of-bounds slice → error response.
4. Add GPU golden test in `test_daemon_handlers_real.py`: call `tex_stats` on
   hello_triangle with valid mip/slice → success; call with out-of-bounds mip → structured
   error response with `rc=1`.

**Acceptance criteria:**
- Out-of-bounds `--mip`/`--slice` returns a clear error response with `rc=1`, no exception.
- Unit tests cover boundary values (0, max, max+1).
- GPU golden test passes for both valid and out-of-bounds cases.

**Dependencies:** none

---

### T4 — `assert-state` KEY_PATH traversal broken

**Files to modify:**
- `src/rdc/commands/assert_ci.py`
- `src/rdc/handlers/query.py` OR `src/rdc/handlers/pipe_state.py`
- `tests/unit/test_assert_ci_commands.py`
- `tests/test_daemon_handlers_real.py`

**Work:**
1. Fix #1 in `assert_ci.py`: handle `field_path == []` (single-segment path such as
   `topology`) by extracting `result[section]` as the leaf value directly.
2. Fix #2 in `assert_ci.py`: fix shader stage routing so paths like `vs.shader`,
   `ps.entry` etc. work by exposing `section_detail` contents rather than the section
   container.
3. Fix shader stage section routing in `handlers/query.py` or `handlers/pipe_state.py` so
   that `assert-state` can access shader stage fields via the existing JSON-RPC response
   structure.
4. Update `tests/unit/test_assert_ci_commands.py`:
   - (a) Update **all existing mocks** to include the `eid` field in the response dict —
     current mocks are missing `eid`, which creates false positives.
   - (b) Add tests for single-segment path (e.g. `topology`).
   - (c) Add tests for shader stage paths (e.g. `vs.shader`, `ps.entry`).
5. Add GPU golden tests in `test_daemon_handlers_real.py`:
   - `assert_state` with `topology` (single-segment) on hello_triangle → expected value
     matches.
   - `assert_state` with `vs.shader` path on hello_triangle → expected value matches.

**Acceptance criteria:**
- Existing 13 `assert-state` tests still pass (two-segment syntax unchanged).
- Single-segment `topology` now works correctly.
- `vs.shader`, `ps.entry` etc. now work correctly.
- All test mocks include `eid` field in the response format.
- GPU golden tests pass for both `topology` and `vs.shader` paths.

**Dependencies:** none

---

### T5 — `script` help text missing variable list

**Files to modify:**
- `src/rdc/commands/script.py`
- `tests/unit/test_script_command.py`

**Work:**
1. Update the Click command's `help` string (or docstring feeding it) to list all 5
   available script variables: `controller`, `rd`, `adapter`, `state`, `args`.
2. Add a unit test that invokes `rdc script --help` via `CliRunner` and asserts all five
   variable names appear in the output.

**Acceptance criteria:**
- `rdc script --help` output lists `controller`, `rd`, `adapter`, `state`, `args`.
- Unit test validates this.

**Dependencies:** none

---

### T6 — `count shaders` not implemented

**Files to modify:**
- `src/rdc/commands/unix_helpers.py`
- `src/rdc/handlers/core.py`
- `src/rdc/services/query_service.py`
- `tests/unit/test_unix_helpers_commands.py`
- `tests/test_daemon_handlers_real.py`

**Work:**
1. Add `"shaders"` to `_COUNT_TARGETS` in `unix_helpers.py`.
2. In `_handle_count` in `handlers/core.py`, add a `shaders` branch as a special case
   before `count_from_actions` (similar to the existing `resources` special case), using
   `shader_inventory()` from `query_service`.
3. In `services/query_service.py`, add `"shaders"` to `_VALID_COUNT_TARGETS` AND
   implement shader counting in `count_from_actions`, OR confirm the handler special-case
   in step 2 is sufficient and no service-level change is needed.
4. Add tests in `tests/unit/test_unix_helpers_commands.py` (note: correct filename, NOT
   `test_unix_helpers.py`): `count shaders` with a mock adapter returns the expected
   integer count.
5. Add GPU golden test in `test_daemon_handlers_real.py`: `count shaders` on
   hello_triangle → result equals the count from `rdc shaders -q | wc -l`.

**Acceptance criteria:**
- `rdc count shaders` returns a non-error integer response.
- Unit test passes with a mock adapter.
- GPU golden test passes and count matches the shader list output.

**Dependencies:** none

---

### T7 — CI gate: lint, typecheck, test

**Files to modify:** none (verification only)

**Work:**
1. Run `pixi run check` (= ruff lint + mypy + pytest).
2. Fix any lint or type errors introduced by T1–T6.
3. Confirm zero test failures and coverage stays at or above the pre-fix baseline.
4. Run `pixi run test-gpu` to validate all new GPU golden tests pass against real
   RenderDoc data.

**Acceptance criteria:**
- `pixi run check` exits 0.
- `pixi run test-gpu` exits 0 with all new GPU golden tests passing.
- No new mypy errors.
- Test count is >= pre-fix baseline.

**Dependencies:** T1, T2, T3, T4, T5, T6 all merged.

---

## Parallelization Notes

All bug fixes (T1–T6) touch non-overlapping files and have no inter-task dependencies —
they can be implemented in parallel across separate worktrees.

| Parallel group | Tasks | Shared files? |
|----------------|-------|---------------|
| Group A | T1, T2 | `tests/test_daemon_handlers_real.py` (GPU tests) — merge carefully |
| Group B | T3 | `handlers/texture.py` + GPU test file |
| Group C | T4 | `commands/assert_ci.py` + GPU test file |
| Group D | T5, T6 | No overlap in src; T6 also touches GPU test file |

T0 must be done first (adds the `hello_triangle_replay` fixture that all GPU tests depend on).
T7 must run after all of T1–T6 are merged to the feature branch.

**Note:** `tests/test_daemon_handlers_real.py` is shared by T1, T2, T3, T4, T6. Each group
adds to a different test class/section; resolve any merge conflicts by appending, not replacing.

Recommended worktree split: two worktrees (T1+T2+T5 in one, T3+T4+T6 in another), then
merge and run T7.

---

## Completion Checklist

After all code tasks are done and merged to `fix/blackbox-bug-fixes`:

- [ ] `pixi run check` passes with zero errors (T7)
- [ ] `pixi run test-gpu` passes with all new GPU golden tests (T7)
- [ ] All new tests cover both happy path and error path for each bug
- [ ] PR created via `gh pr create`; bot reviews (CodeRabbit, Greptile) checked and addressed
- [ ] Squash merge via `gh pr merge --squash --delete-branch`
- [ ] Archive OpenSpec: `mv openspec/changes/2026-02-22-blackbox-bug-fixes openspec/changes/archive/`
- [ ] Update Obsidian `进度跟踪.md` (test count delta, coverage)
- [ ] Record any design deviations in `归档/决策记录.md` (next D-NNN)
- [ ] Update `待解决.md` — remove resolved bugs
