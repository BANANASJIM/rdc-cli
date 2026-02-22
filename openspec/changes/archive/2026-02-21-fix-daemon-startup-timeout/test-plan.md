# Test Plan: Daemon Startup Timeout Fix

## Unit Tests

| # | Test | Validates |
|---|------|-----------|
| 1 | `test_wait_for_ping_default_timeout_is_15` | New default timeout value |
| 2 | `test_wait_for_ping_returns_early_on_process_exit` | Early exit when proc.poll() != None |
| 3 | `test_wait_for_ping_succeeds_returns_tuple` | Success returns `(True, "")` |
| 4 | `test_wait_for_ping_works_without_proc` | `proc=None` backward compat |
| 5 | `test_open_session_reports_stderr_on_failure` | stderr included in error message |
| 6 | `test_open_session_failure_with_empty_stderr` | Clean error when daemon crashes silently |

## Existing tests

`test_open_session_cross_name_no_conflict` and `test_open_session_same_name_alive_fails`
are unaffected — `open_session()` return type stays `tuple[bool, str]`.

## Manual Verification

```bash
# 5 previously failing captures (375-596 MB)
for cap in async_compute command_buffer_usage constant_data \
           descriptor_management multithreading_render_passes; do
  pixi run rdc --session "v_$cap" open ~/Dev/Vulkan-Samples/rdc_captures/$cap.rdc
  pixi run rdc --session "v_$cap" close
done
```

## Regression

```bash
pixi run lint && pixi run test
```
