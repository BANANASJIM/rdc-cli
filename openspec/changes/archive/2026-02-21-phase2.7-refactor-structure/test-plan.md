# Test Plan: Code Structure Refactor

## Scope

### In scope
- Regression: all 838 existing tests pass unchanged after refactor
- Import correctness: all new modules and re-exported symbols importable
- No circular imports introduced in `src/rdc/`
- mypy strict passes with zero new errors
- ruff check + format pass (zero lint errors)
- Coverage does not drop below current baseline (80%)

### Out of scope
- New functional test cases (pure refactor — behavior is unchanged)
- GPU integration tests (no handler logic changes)
- Performance or latency validation

---

## Test Matrix

| Layer | Tool | What is verified |
|-------|------|-----------------|
| Static: import check | `python -c "import ..."` | No `ImportError`, no circular imports |
| Static: type check | `mypy --strict src/rdc/` | Zero new type errors after refactor |
| Static: lint | `ruff check src/rdc/ tests/` | Zero new lint violations |
| Static: format | `ruff format --check src/rdc/` | No formatting drift |
| Unit: daemon handlers | all daemon unit tests | `_handle_request` still routes all methods correctly |
| Unit: command helpers | `test_resources_commands.py`, `test_pipeline_commands.py`, `test_unix_helpers_commands.py` | `_require_session` / `_call` behavior unchanged |
| Unit: stage map | `test_daemon_shader_extended.py`, `test_pipeline_state.py`, `test_daemon_pipeline_extended.py` | Stage routing unchanged for all 6 stages |
| Unit: transport | existing daemon transport tests | `_recv_line` behavior unchanged after move to `_transport.py` |
| Full suite | `pixi run check` (= lint + typecheck + test) | All 838 tests pass, coverage >= 80% |

---

## Cases

### C1 — All existing daemon method routes still respond correctly

For every method name currently handled by `_handle_request`, confirm the dict-dispatch version
produces an identical response to the original if/elif version.

- Assertion: the existing test suite exercises this — no new test code needed.
- Key files: `test_daemon_server_unit.py`, `test_pipeline_state.py`, `test_daemon_pipeline_extended.py`,
  `test_draws_events_daemon.py`, `test_binary_daemon.py`, `test_buffer_decode.py`,
  `test_descriptors_daemon.py`, `test_usage_daemon.py`, `test_counters_daemon.py`,
  `test_search.py`, `test_vfs_daemon.py`, `test_count_shadermap.py`,
  `test_pipeline_section_routing.py`, `test_pipeline_daemon.py`, `test_draws_daemon.py`,
  `test_resources_filter.py`.

### C2 — Unknown method returns JSON-RPC error -32601

`_handle_request({"method": "nonexistent", "id": 1, "params": {}}, state)` must return
`{"error": {"code": -32601, ...}}`.

- Covered by `test_daemon_server_unit.py`.

### C3 — `_require_session` exits with code 1 when no session

After replacing with import from `_helpers.py`, the behavior must be identical:
- `load_session()` returns `None` -> `click.echo("error: ...", err=True)` + `SystemExit(1)`
- Covered by `test_resources_commands.py`, `test_pipeline_commands.py`, `test_unix_helpers_commands.py`.

### C4 — `_call` propagates daemon errors correctly

`send_request` returning `{"error": {"message": "boom"}}` must cause `SystemExit(1)`.
Covered by existing command unit tests.

### C5 — Stage map lookup uses `STAGE_MAP` from `query_service`, result unchanged

For each of the 8 call sites replaced, the looked-up integer value for all 6 stages
must be identical. Covered by shader and pipeline tests.

### C6 — `_enum_name` always returns str

After unifying to `return v.name if hasattr(v, "name") else str(v)`, all enum conversions
produce strings. Covered by `test_daemon_output_quality.py` and pipeline tests.

### C7 — `_recv_line` from `_transport.py` works for both client and server

After consolidation, socket line reading is unchanged. Covered by
`test_daemon_transport.py` and `test_protocol.py`.

### C8 — Dead `_count_events` removal causes no test failures

Function is unused — removing it must not break any test.

### C9 — `require_pipe` helper produces identical error responses

The extracted `require_pipe` helper must produce the same `-32002` error responses
for "no replay loaded" and "set_frame_event failed" cases. Covered by existing handler tests.

### C10 — No circular imports

```python
python -c "
from rdc import daemon_server
from rdc import handlers
from rdc.commands import _helpers
from rdc import _transport
"
```
Must exit 0 with no output.

### C11 — mypy strict clean

All new modules must carry full type annotations. `mypy --strict src/rdc/` zero errors.

### C12 — Symbol backward compatibility for tests

Tests import these symbols from `rdc.daemon_server` directly:
- `DaemonState`, `_handle_request`, `_load_replay`, `_set_frame_event`
- `_max_eid`, `_build_shader_cache`, `_enum_name`, `_sanitize_size`
- `_result_response`, `_error_response`

All must remain importable from `rdc.daemon_server` after the refactor via re-exports.

---

## Assertions

### Exit codes
- `pixi run check` exits 0.
- All import smoke tests exit 0.

### Output contract
- No change to any stdout/stderr output of any CLI command.
- No change to any JSON-RPC response schema or field values.

### Coverage
- `pytest --cov=src/rdc --cov-report=term` shows >= 80% overall.

### Type safety
- `mypy --strict src/rdc/` exits 0, zero errors.

### Lint
- `ruff check src/rdc/` exits 0.
- `ruff format --check src/rdc/` exits 0.

---

## Risks & Rollback

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Circular import between `handlers/*.py` and `daemon_server.py` | Medium | Handler modules import only from `handlers._helpers`; `daemon_server.py` imports handler `HANDLERS` dicts at module level |
| Test imports of private symbols break | Low | All helpers re-exported from `daemon_server.py` |
| `require_pipe` subtly changes error response format | Low | Extract exact existing code; tests verify identical responses |
| `_recv_line` move breaks socket protocol | Low | Function body unchanged; existing transport tests verify |
| `_enum_name` str fix changes output for non-enum values | Low | Only affects edge case where non-string non-enum is passed — existing tests catch this |
| Coverage drop if handler modules not exercised | Low | Tests call `_handle_request` which dispatches through modules |

### Rollback
Revert the branch. No database, protocol, or file format changes — rollback is a simple git revert.
