# Tasks: diff-infrastructure

## Phase A — idle_timeout parameter + daemon fix

- [ ] Fix `daemon_server.py`: `if idle_timeout_s > 0 and time.time() - last_activity > idle_timeout_s`
- [ ] Add `idle_timeout: int = 1800` keyword-only param to `start_daemon()`
- [ ] Replace hardcoded `"1800"` with `str(idle_timeout)`
- [ ] Add 2 tests to `test_session_service.py` (idle_timeout=120 and default)

## Phase B — diff_service unit tests (write first)

- [ ] Create `tests/unit/test_diff_service.py`
- [ ] Tests #1–7: DiffContext + start_diff_session happy path
- [ ] Tests #8–11: start_diff_session failure paths
- [ ] Tests #12–15: stop_diff_session behavior
- [ ] Tests #16–21: query_both
- [ ] Tests #22–23: query_both_sync

## Phase C — diff_service.py implementation

- [ ] Create `src/rdc/services/diff_service.py`
- [ ] DiffContext dataclass
- [ ] start_diff_session: dual fork, concurrent ping, atexit, cleanup
- [ ] stop_diff_session: 4 independent best-effort steps
- [ ] query_both: 2 threads, token injection, partial results
- [ ] query_both_sync: 2N threads, ordered results

## Phase D — diff_cmd CLI tests (write first)

- [ ] Create `tests/unit/test_diff_command.py`
- [ ] Tests #26–35: argument validation, mode dispatch, flag forwarding, cleanup

## Phase E — diff_cmd implementation

- [ ] Create `src/rdc/commands/diff.py`
- [ ] All Click options, mode dispatch table, stub handlers
- [ ] try/finally with stop_diff_session

## Phase F — Registration + verification

- [ ] Register in `src/rdc/cli.py`
- [ ] `pixi run check` — lint + typecheck + test
- [ ] `rdc diff --help` shows all flags
