# Test Plan: diff-infrastructure

## Unit Tests: `test_diff_service.py`

### DiffContext

| # | Test | Validates |
|---|------|-----------|
| 1 | Construct with all fields, access each | Field presence and types |

### start_diff_session — happy path

| # | Test | Validates |
|---|------|-----------|
| 2 | Mock start_daemon + wait_for_ping → success | Returns (DiffContext, "") |
| 3 | session_id is 12 hex chars | Format |
| 4 | token_a != token_b | Independent tokens |
| 5 | port_a != port_b | Distinct ports |
| 6 | atexit.register called | Orphan protection |
| 7 | start_daemon called with idle_timeout=120 | Short orphan timer |

### start_diff_session — failure paths

| # | Test | Validates |
|---|------|-----------|
| 8 | A fails ping → kill both, return error | A fails |
| 9 | B fails ping → kill both, return error | B fails |
| 10 | Second Popen raises → kill A | Spawn failure |
| 11 | Both fail ping | Both fail |

### stop_diff_session

| # | Test | Validates |
|---|------|-----------|
| 12 | RPC succeeds, pid dead → no SIGTERM | Clean shutdown |
| 13 | RPC fails, pid alive → SIGTERM sent | Fallback |
| 14 | Call twice → no exception | Idempotent |
| 15 | os.kill raises ProcessLookupError | Never raises |

### query_both

| # | Test | Validates |
|---|------|-----------|
| 16 | Both succeed | Returns (result_a, result_b, "") |
| 17 | Token injection per side | A gets token_a, B gets token_b |
| 18 | Original params not mutated | No side effects |
| 19 | A returns error → result_a is None | Partial failure |
| 20 | B raises ConnectionRefused → result_b is None | Partial failure |
| 21 | Both fail | Both None |

### query_both_sync

| # | Test | Validates |
|---|------|-----------|
| 22 | Ordering preserved | results[i] matches calls[i] |
| 23 | Partial batch failure | One None, rest present |

### start_daemon idle_timeout

| # | Test | Validates |
|---|------|-----------|
| 24 | idle_timeout=120 → "120" in cmd | Propagated |
| 25 | Default → "1800" in cmd | Backward compat |

## Unit Tests: `test_diff_command.py`

| # | Test | Validates |
|---|------|-----------|
| 26 | Happy path → exit 0 | Summary stub works |
| 27 | --timeout 90 forwarded | Param passing |
| 28 | Missing file → exit 2 | Validation |
| 29 | Startup error → exit 2 with message | Error reporting |
| 30 | Mode stub raises → cleanup still runs | finally block |
| 31 | --draws → dispatched to draws handler | Mode routing |
| 32 | --pipeline MARKER → mode=pipeline | Pipeline flag |
| 33 | No flag → mode=summary | Default |
| 34 | --json forwarded | Flag passing |
| 35 | --no-header forwarded | Flag passing |

## Regression

```bash
pixi run lint && pixi run test
```
