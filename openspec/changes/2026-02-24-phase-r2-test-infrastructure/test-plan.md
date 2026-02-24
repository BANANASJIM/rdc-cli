# Phase R2 — Test Infrastructure Refactoring: Test Plan

## Scope

Pure regression validation. R2 introduces no new behavior — only consolidates existing boilerplate
into shared helpers in `tests/unit/conftest.py`. All 2135 tests must continue to pass at ≥94%
coverage. No new test cases are added; no test logic changes semantically.

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|-------------|
| All 2135 tests pass | `pixi run test` exits 0 |
| Coverage stays ≥ 94% | Coverage report shows ≥ 94% total |
| No local `_make_state()` definitions remain in daemon handler tests | `grep` count = 0 (see TC-1) |
| No inline `import rdc.commands._helpers as mod` inside test functions | `grep` count = 0 (see TC-2) |
| No repeated session stub construction (`type("S", ...)`) | `grep` count = 0 (see TC-3) |
| Output assertion boilerplate replaced with shared helpers | Spot-check selected files (see TC-4) |
| `conftest.py` exports remain backward-compatible | `rpc_request()` still callable from all importing tests |

---

## TC-1: `make_daemon_state()` consolidation

**Objective**: Verify that all local `_make_state*()` definitions in daemon handler test files
have been replaced by imports of `make_daemon_state()` from `conftest`.

**Verification command**:
```bash
grep -rn "^def _make_state" tests/unit/ --include="*.py"
```
**Expected**: zero matches (pattern without `\b` catches `_make_state_with_*` variants too).

**Files that must be migrated** (19 files, baseline from pre-R2):
- `test_daemon_pipeline_extended.py`
- `test_draws_daemon.py`
- `test_vfs_daemon.py`
- `test_capturefile_handlers.py`
- `test_daemon_output_quality.py`
- `test_tex_stats_handler.py`
- `test_draws_events_daemon.py`
- `test_pipeline_section_routing.py`
- `test_script_handler.py`
- `test_handlers_remote.py`
- `test_fix1_draws_pass_name.py`
- `test_pipeline_daemon.py`
- `test_debug_handlers.py`
- `test_pick_pixel_daemon.py`
- `test_pixel_history_daemon.py`
- `test_shader_edit_handlers.py`
- `test_binary_daemon.py` (`_make_state_with_temp`)
- `test_descriptors_daemon.py` (`_make_state_with_pipe`)
- `test_daemon_shader_api_fix.py` (`_make_state_with_ps`, `_make_state_with_cbuffer`, `_make_state_with_vfs`)

**Spot-check**: import in each migrated file:
```bash
grep "from conftest import.*make_daemon_state" tests/unit/test_draws_daemon.py
grep "from conftest import.*make_daemon_state" tests/unit/test_vfs_daemon.py
grep "from conftest import.*make_daemon_state" tests/unit/test_debug_handlers.py
```
Each must return exactly one match.

---

## TC-2: CLI monkeypatch helper consolidation

**Objective**: Verify that inline `import rdc.commands._helpers as mod` inside test functions or
local `_patch()` wrappers have been replaced by a shared `patch_cli()` fixture or helper from
`conftest`.

**Verification command** (inline import inside functions):
```bash
grep -rn "import rdc.commands._helpers as" tests/unit/ --include="*.py"
```
**Expected**: zero matches (all imports moved to `conftest.py`).

**Verification command** (session stub duplication):
```bash
grep -rn 'type("S", (), {"host"' tests/unit/ --include="*.py"
```
**Expected**: zero matches in test files (only in `conftest.py`).

**Verification command** (string-based monkeypatches):
```bash
grep -rn 'setattr("rdc.commands._helpers' tests/unit/ --include="*.py" | grep -v conftest.py
```
**Expected**: zero matches (all migrated to shared helper).

---

## TC-3: Session stub deduplication

**Objective**: The session stub `type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()`
must appear only inside `conftest.py`, not in individual test files.

**Verification command**:
```bash
grep -rn '"host": "127.0.0.1"' tests/unit/ --include="*.py" | grep -v conftest.py
```
**Expected**: zero matches.

---

## TC-4: Output assertion helpers

**Objective**: Spot-check that `assert_json_output()`, `assert_jsonl_output()` (or equivalent
helpers) are used in the five highest-boilerplate CLI test files.

**Verification command**:
```bash
grep -rn "assert_json_output\|assert_jsonl_output" tests/unit/ --include="*.py"
```
**Expected**: matches in at least:
- `test_resources_commands.py`
- `test_pipeline_commands.py`
- `test_capturefile_commands.py`
- `test_debug_commands.py`
- `test_tex_stats_commands.py`

**Anti-pattern check** — inline `json.loads(result.output)` in CLI test files should be eliminated
or reduced significantly:
```bash
grep -rn "json\.loads(result\.output)" tests/unit/ --include="*.py" | grep -v conftest.py | wc -l
```
**Expected**: count reduced from 37 (pre-R2 baseline) toward 0; must not exceed 10.

---

## TC-5: `rpc_request()` backward compatibility

**Objective**: The existing `rpc_request()` helper (present since R1) must remain callable with the
same signature and produce identical output.

**Verification**: All tests that import `rpc_request` from `conftest` must pass without
modification.

**Verification command**:
```bash
grep -rn "from conftest import rpc_request" tests/unit/ --include="*.py" | wc -l
```
**Expected**: same count as pre-R2 (no imports removed).

**Functional check**: Run `pixi run test -k "vfs_daemon or draws_daemon"` — must pass with zero
failures.

---

## TC-6: Full test suite regression

**Objective**: Zero regressions across all test files after refactoring.

**Verification command**:
```bash
pixi run test
```
**Expected output** (last lines):
```
2135 passed in ...
Required test coverage of 80% reached. Total coverage: 94.xx%
```

Exact pass count must equal pre-R2 baseline (2135). Coverage must not drop below 94.0%.

---

## TC-7: Lint and type check

**Objective**: No new lint or type errors introduced in `conftest.py` or migrated test files.

**Verification command**:
```bash
pixi run lint
```
**Expected**: exits 0, zero ruff errors.

```bash
pixi run typecheck
```
**Expected**: exits 0, zero mypy errors.

---

## Non-Goals

- This test plan does NOT validate new behaviors or new test cases.
- Tests for the helper functions themselves (e.g., unit-testing `make_daemon_state()`) are out of
  scope — helpers are validated indirectly by the full suite passing.
- GPU integration tests (`test_daemon_handlers_real.py`) are not affected by R2 and are excluded
  from scope.
