# Test Plan: Blackbox Bug Fix Batch (2026-02-22)

## 1. Overview

**Scope:** Unit tests + GPU integration tests covering all six bugs identified in the 2026-02-22
blackbox session.

**Strategy — unit-first, GPU golden:**

Unit tests run in CI without GPU and cover error-handling logic and fast regression checks. GPU
integration tests in `tests/test_daemon_handlers_real.py` are the golden standard: they validate
each fix against a real RenderDoc capture and catch cases where mock behavior diverges from the
real API. Every bug fix that involves handler logic MUST have a corresponding GPU golden test.

Why GPU tests are required: all six bugs were discovered via real GPU usage, not mock testing.
Mocks can pass even when the real RenderDoc API returns different data shapes, raises unexpectedly,
or has undocumented constraints. Unit tests validate error-handling paths; GPU tests validate
correctness on real data. A fix is not considered complete until its GPU golden test passes.

**GPU test setup:**
- File: `tests/test_daemon_handlers_real.py`
- Run with: `RENDERDOC_PYTHON_PATH=/home/jim_z/Dev/renderdoc-src/build-py314/lib pixi run test-gpu`
- Primary fixture: `hello_triangle.rdc` via new `hello_triangle_replay` session fixture (to be added to `tests/conftest.py` — mirrors `vkcube_replay` pattern, see T0 in tasks.md)

**Unit test layers:**
- CLI bugs (BUG-2, BUG-5, BUG-6): `CliRunner` + monkeypatch `rdc.commands._helpers.{load_session,send_request}`
- Handler bugs (BUG-1, BUG-3): call `_handle_request()` directly with `DaemonState` + `MockReplayController`
- BUG-4 spans both layers: CLI path via `CliRunner`; handler section dict structure via handler unit test

**Target files:**

| Bug | Unit test file | Handler test file | GPU golden file |
|-----|---------------|-------------------|-----------------|
| BUG-1 | `tests/unit/test_debug_commands.py` | `tests/unit/test_debug_handlers.py` | `tests/test_daemon_handlers_real.py` |
| BUG-2 | `tests/unit/test_debug_commands.py` | — | `tests/test_daemon_handlers_real.py` |
| BUG-3 | `tests/unit/test_tex_stats_commands.py` | `tests/unit/test_tex_stats_handler.py` | `tests/test_daemon_handlers_real.py` |
| BUG-4 | `tests/unit/test_assert_ci_commands.py` | `tests/unit/test_pipeline_daemon.py` | `tests/test_daemon_handlers_real.py` |
| BUG-5 | `tests/unit/test_script_command.py` | — | — |
| BUG-6 | `tests/unit/test_unix_helpers_commands.py` | — | `tests/test_daemon_handlers_real.py` |

CI gate: `pixi run lint && pixi run test` must pass with zero failures before PR. GPU tests are
run separately and must also pass before the PR is merged.

---

## 2. Test Cases per Bug

### BUG-1: `debug vertex` — internal error in `_run_debug_loop`

**Verified root cause:** `_run_debug_loop()` raises when `controller.ContinueDebug()` or
`_format_step()` encounter unexpected data from real RenderDoc traces.
`_extract_inputs_outputs` does NOT raise on empty steps; the guard belongs inside
`_run_debug_loop`.

**Unit tests** — mock the failure point in `_run_debug_loop`:

| Test ID | Description | Type | Inputs | Expected Outcome |
|---------|-------------|------|--------|-----------------|
| BUG1-H-01 | `ContinueDebug` raises `RuntimeError` → structured error response | Handler | Monkeypatch `controller.ContinueDebug` to raise `RuntimeError("unexpected state")` | `response["error"]["code"] == -32603`; message contains "unexpected state"; no unhandled exception propagates |
| BUG1-H-02 | `_format_step` raises on malformed state → structured error | Handler | Monkeypatch `controller.ContinueDebug` to return a state that causes `_format_step` to raise | `response["error"]` present; message is informative, not "internal error" |
| BUG1-H-03 | Happy path with valid mock trace → inputs/outputs present | Handler | Valid trace with ≥1 step and variable changes | `response["result"]["inputs"]` and `["outputs"]` are lists; `response["result"]["total_steps"]` is an integer |
| BUG1-C-01 | CLI exits rc=1 with clear message on handler error | CLI | Monkeypatch `send_request` returns `{"error": {"message": "unexpected state", "code": -32603}}`; invoke `debug vertex 100 0` | `result.exit_code == 1`; "unexpected state" in output |
| BUG1-C-02 | CLI `--trace` succeeds when valid trace returned | CLI | Monkeypatch `send_request` returns valid trace result; invoke `debug vertex 100 0 --trace` | `result.exit_code == 0`; trace steps present in output |

**GPU golden tests** (in `test_daemon_handlers_real.py`):
- `debug_vertex` on hello_triangle EID=11, vertex=0 → must return rc=0 with `inputs`, `outputs`, `total_steps` fields present in result. This test was FAILING before the fix; after the fix it must pass. This is the definitive validation that the fix works on real RenderDoc data.

### BUG-2: `debug pixel` — rc=0 on error (defensive fix)

**Situation:** Root cause unconfirmed from static analysis. Fix defensively: all three output
modes must propagate rc=1 when the daemon returns an error object.

**Unit tests** — verify rc propagation for all output modes:

| Test ID | Description | Type | Inputs | Expected Outcome |
|---------|-------------|------|--------|-----------------|
| BUG2-C-01 | Plain mode exits rc=1 on daemon error | CLI | `send_request` returns `{"error": {"message": "no shader bound", "code": -32603}}`; invoke `debug pixel 100 512 384` | `result.exit_code == 1` |
| BUG2-C-02 | `--json` mode exits rc=1 on daemon error | CLI | Same error response; invoke `debug pixel 100 512 384 --json` | `result.exit_code == 1` |
| BUG2-C-03 | `--trace` mode exits rc=1 on daemon error | CLI | Same error response; invoke `debug pixel 100 512 384 --trace` | `result.exit_code == 1` |
| BUG2-C-04 | Plain mode exits rc=0 on success (regression) | CLI | `send_request` returns valid pixel debug result | `result.exit_code == 0` |

**Setup note:** Use `CliRunner(mix_stderr=False)` and monkeypatch `rdc.commands._helpers.send_request`
to return the error dict (not raise).

**GPU golden tests** (in `test_daemon_handlers_real.py`):
- `debug_pixel` on hello_triangle EID=11, x=640, y=360 (pixel on triangle) → must return rc=0 with a valid result.
- `debug_pixel` on hello_triangle EID=11, x=640, y=360 plain text mode → rc=0. This validates the bug is fixed: before the fix this path returned rc=0 even on error; the golden test confirms correct behavior post-fix on real data.

### BUG-3: `tex-stats --mip/--slice` bounds checking

The handler must validate `mip` against `tex.mips` and `slice` against `tex.arraysize` before
calling `GetMinMax`.

**Unit tests:**

| Test ID | Description | Type | Inputs | Expected Outcome |
|---------|-------------|------|--------|-----------------|
| BUG3-H-01 | `mip` out of range → error response | Handler | Texture with `mips=3`; params `{"id": 42, "mip": 3}` | `response["error"]["message"]` matches `"mip 3 out of range (max: 2)"` |
| BUG3-H-02 | `mip` at upper boundary → success | Handler | Texture with `mips=3`; params `{"id": 42, "mip": 2}` | `response["result"]["mip"] == 2`; no error |
| BUG3-H-03 | `slice` out of range → error response | Handler | Texture with `arraysize=1`; params `{"id": 42, "slice": 1}` | `response["error"]["message"]` matches `"slice 1 out of range (max: 0)"` |
| BUG3-H-04 | `slice` at boundary → success | Handler | Texture with `arraysize=1`; params `{"id": 42, "slice": 0}` | no error |
| BUG3-H-05 | Negative `mip` → error response | Handler | Texture with `mips=4`; params `{"id": 42, "mip": -1}` | `response["error"]` present |
| BUG3-H-06 | Valid `mip=0`, `slice=0` still succeeds (regression) | Handler | Texture with `mips=4`, `arraysize=2`; params `{"id": 42, "mip": 0, "slice": 0}` | `response["result"]["mip"] == 0`; no error |
| BUG3-C-01 | CLI `tex-stats ID --mip 999` exits rc=1 | CLI | Mock `send_request` returns error response; invoke `tex-stats 42 --mip 999` | `result.exit_code == 1`; "out of range" in output |

**Mock note:** `TextureDescription` in `mock_renderdoc.py` must support `mips` and `arraysize`
fields. The `_make_state` helper in `test_tex_stats_handler.py` gains `mips=` and `arraysize=`
kwargs for these tests.

**GPU golden tests** (in `test_daemon_handlers_real.py`):
- `tex_stats` on hello_triangle resource (first valid texture resource ID from fixture) with `mip=0` → success.
- `tex_stats` on hello_triangle with `mip=999` → error response, rc=1. Before the fix this returned rc=0; the golden test confirms the bounds check works on real texture metadata.

### BUG-4: `assert-state` — two issues, two GPU goldens

**Issue 1** (single-segment path): First segment is the pipeline section name; no further
traversal needed when the value is a scalar leaf.

**Issue 2** (shader stage routing): `vs.shader`, `vs.entry`, etc. must be routed correctly and
return a flat dict, not a nested `section_detail` wrapper.

**Important:** All assert-state unit test mocks MUST include `eid` field in the response dict.
Current mocks omit it and create false positives. Real handler responses always include `eid`.

**Unit tests:**

| Test ID | Description | Type | Inputs | Expected Outcome |
|---------|-------------|------|--------|-----------------|
| BUG4-C-01 | Single-segment leaf — pass | CLI | Mock pipeline result `{"eid": 120, "topology": "TriangleList"}`; invoke `assert-state 100 topology --expect TriangleList` | `result.exit_code == 0` |
| BUG4-C-02 | Single-segment leaf — fail | CLI | Same mock; invoke `assert-state 100 topology --expect PointList` | `result.exit_code == 1`; "expected PointList, got TriangleList" in output |
| BUG4-C-03 | `vs.shader` path → extracts shader ID | CLI | Mock result `{"eid": 120, "stage": "vs", "shader": 42, "entry": "main", "ro": 0, "rw": 0, "cbuffers": 1}`; invoke `assert-state 100 vs.shader --expect 42` | `result.exit_code == 0` |
| BUG4-C-04 | `vs.entry` path → extracts entry point | CLI | Same mock; invoke `assert-state 100 vs.entry --expect main` | `result.exit_code == 0` |
| BUG4-C-05 | Index segment — pass | CLI | Mock result `{"eid": 120, "blends": [{"enabled": true}]}`; invoke `assert-state 100 blend.0.enabled --expect true` | `result.exit_code == 0` |
| BUG4-C-06 | Index segment — fail | CLI | Same mock; invoke with `--expect false` | `result.exit_code == 1` |
| BUG4-C-07 | Key not found → rc=1 | CLI | Mock result `{"eid": 120}`; invoke `assert-state 100 nonexistent.field --expect x` | `result.exit_code == 1`; "not found" in output |
| BUG4-C-08 | `--json` output with pass=true | CLI | Mock `{"eid": 120, "topology": "TriangleList"}`; invoke `assert-state 100 topology --expect TriangleList --json` | `result.exit_code == 0`; JSON with `"pass": true` |
| BUG4-C-09 | `--json` output with pass=false | CLI | Mismatch; invoke with `--json` | `result.exit_code == 1`; JSON with `"pass": false`, `"expected"`, `"actual"` |
| BUG4-C-10 | `topology.topology` two-segment path still works (regression) | CLI | Mock `{"eid": 120, "topology": "TriangleList"}`; invoke `assert-state 100 topology.topology --expect TriangleList` | `result.exit_code == 0` |
| BUG4-H-01 | Pipeline handler returns flat dict with `eid` for `topology` | Handler | `_handle_request` with `method="pipeline"`, `params={"section": "topology"}`; mock pipeline state | `response["result"]` has `"eid"` key and `"topology"` key with scalar string value |
| BUG4-H-02 | Pipeline handler returns flat dict with `eid` for shader stage | Handler | `_handle_request` with `method="pipeline"`, `params={"section": "vs"}`; mock pipeline state | `response["result"]` has keys: `eid`, `stage`, `shader`, `entry`, `ro`, `rw`, `cbuffers` |

**Mock format requirement:** All `send_request` mocks for assert-state tests MUST return dicts
that include `"eid"`. Shader stage section result must use the flat dict format above, not a
`section_detail` wrapper, to match the real handler output after the routing fix.

**GPU golden tests** (in `test_daemon_handlers_real.py`):
- `assert_state` on hello_triangle EID=11, `topology` → pass with `"TriangleList"`.
- `assert_state` on hello_triangle EID=11, `vs.shader` → pass with the actual shader ID (obtain via `rdc shaders` against the same capture first).
- `assert_state` on hello_triangle EID=11, `topology.topology` → pass (regression: two-segment path still works).

### BUG-5: `script` help text

No behavioral fix — docstring/help text only.

| Test ID | Description | Type | Inputs | Expected Outcome |
|---------|-------------|------|--------|-----------------|
| BUG5-C-01 | `--help` lists all five variable names | CLI | `CliRunner().invoke(main, ["script", "--help"])` | All of `controller`, `rd`, `adapter`, `state`, `args` appear in output |
| BUG5-C-02 | `--help` does not mention removed `-c` option | CLI | Same invocation | `-c` / `--code` not in output |

No GPU test needed for documentation-only changes.

### BUG-6: `count shaders`

`"shaders"` must be a valid choice in `_COUNT_TARGETS`; the handler must return a count.

**Unit tests:**

| Test ID | Description | Type | Inputs | Expected Outcome |
|---------|-------------|------|--------|-----------------|
| BUG6-C-01 | `count shaders` accepted and returns count | CLI | Monkeypatch `send_request` returns `{"result": {"value": 7}}`; invoke `count shaders` | `result.exit_code == 0`; "7" in output |
| BUG6-C-02 | `assert-count shaders --expect 7` passes | CLI | Same mock with `value=7`; invoke `assert-count shaders --expect 7` | `result.exit_code == 0` |
| BUG6-C-03 | `assert-count shaders --expect 99` fails | CLI | Same mock with `value=7`; invoke `assert-count shaders --expect 99` | `result.exit_code == 1` |
| BUG6-C-04 | Invalid target still fails rc=2 (regression) | CLI | Invoke `count bogus` | `result.exit_code == 2`; "Invalid value" in output |
| BUG6-H-01 | Handler `count` with `what=shaders` returns integer | Handler | `_handle_request` with `method="count"`, `params={"what": "shaders"}`; mock adapter with shader list | `response["result"]["value"]` is an integer ≥ 0 |

**GPU golden test** (in `test_daemon_handlers_real.py`):
- `count shaders` on hello_triangle → returns the same count as `len(rdc shaders -q)` output on the same capture. Validates that the handler correctly enumerates real shaders, not just accepting the keyword without producing a meaningful result.

---

## 3. Mock Accuracy Requirements

The following mock response formats MUST match the real handler output format to prevent false
positives. Deviations will cause unit tests to pass while GPU tests fail.

| Handler | Required mock format | Key constraint |
|---------|---------------------|----------------|
| `pipeline` (topology) | `{"eid": int, "topology": str}` | `eid` always present |
| `pipeline` (vs/ps/cs stage) | `{"eid": int, "stage": str, "shader": int, "entry": str, "ro": int, "rw": int, "cbuffers": int}` | Flat dict, not nested `section_detail` wrapper |
| `debug_vertex` (result) | `{"inputs": list, "outputs": list, "total_steps": int}` | All three fields required |
| `count` (shaders) | `{"value": int}` | Integer, not list |
| `tex_stats` (error) | `{"error": {"code": int, "message": str}}` | `message` must contain bound info |

Any existing assert-state unit test mock that omits `eid` must be updated. This is a correctness
fix for the tests themselves, not just the new cases.

---

## 4. Regression Coverage

Existing passing tests that must remain green after each fix:

| Bug fixed | Existing tests that must still pass |
|-----------|-------------------------------------|
| BUG-1 | `test_debug_handlers.py`: all existing `debug_vertex` and `debug_pixel` handler tests; `test_debug_commands.py`: happy-path `debug vertex` and `debug pixel` CLI tests |
| BUG-2 | `test_debug_commands.py`: all existing `debug pixel` happy-path tests (rc=0 on success) |
| BUG-3 | `test_tex_stats_handler.py`: `test_tex_stats_happy_minmax`, `test_tex_stats_happy_histogram`; `test_tex_stats_commands.py`: `test_tex_stats_table_output`, `test_tex_stats_float_format` |
| BUG-4 | `test_assert_ci_commands.py`: `test_assert_call_success`, `test_assert_call_rpc_error`, `test_assert_call_no_session`; all existing `assert-count` tests |
| BUG-5 | `test_script_command.py`: all existing `TestScriptDefaultOutput` tests |
| BUG-6 | `test_unix_helpers_commands.py`: `test_count_draws`, `test_count_events`, `test_count_triangles`, `test_count_with_pass`, `test_count_no_session`, `test_count_error_response` |

---

## 5. Out of Scope

- `debug thread` handler audits beyond the consistency note in the proposal.
- New JSON-RPC methods or CLI commands.
- Coverage for the `assert-count shaders` handler path if `test_count_shadermap.py` already covers it — confirm overlap before adding duplicate coverage.
- E2e tests beyond the GPU golden tests listed above.
