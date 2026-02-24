# Tasks: fix capture process leak (B26, B27, B28)

## Task list

- [ ] T1: fix(capture): terminate target process on error path when pid is known (B26)
  - File: `src/rdc/commands/capture.py` line 121
  - Change `result.success and result.pid` to just `result.pid` in the terminate
    condition so that a process launched by ExecuteAndInject is cleaned up even
    when the capture itself fails (e.g. timeout, inject error after process
    started). The `not trigger` and `not keep_alive` guards remain unchanged.

- [ ] T2: test(capture): add unit tests for B26 error-path terminate behavior
  - File: `tests/unit/test_capture.py`
  - Add cases: (a) success=False, pid set → process is terminated; (b)
    success=True, pid set → process is terminated; (c) success=False, pid=0 →
    no terminate call; (d) keep_alive=True → no terminate; (e) trigger=True → no
    terminate. Monkeypatch `terminate_process` and `execute_and_capture` as needed.

- [ ] T3: fix(capture_core): return pid in trigger early-return path (B27)
  - File: `src/rdc/capture_core.py` lines 113-114
  - In the `if trigger: return CaptureResult(...)` branch, briefly call
    `rd.CreateTargetControl("", result.ident, "rdc-cli", True)` to obtain the
    real OS pid via `tc.GetPID()`, then call `tc.Shutdown()`, and include `pid`
    in the returned `CaptureResult`. If the brief connection fails, fall back to
    pid=0 (non-fatal for a P2 bug).

- [ ] T4: test(capture_core): add unit tests for B27 trigger-mode pid retrieval
  - File: `tests/unit/test_capture_core.py`, `tests/mocks/mock_renderdoc.py`
  - Prerequisite: add `shutdown_count: int = 0` to `MockTargetControl.__init__`
    and increment in `Shutdown()` (needed for asserting cleanup in TC-B27-2).
  - Update existing `test_capture_trigger_mode`: change assertion from
    `assert rd._calls["tc_create"] == []` to `assert len(rd._calls["tc_create"]) == 1`.
  - Add cases: (a) trigger=True, tc connects → returned CaptureResult has pid
    set and tc.Shutdown called; (b) trigger=True, tc is None → returned
    CaptureResult has pid=0 (graceful fallback); (c) non-trigger path unaffected.
    Mock `rd.ExecuteAndInject` and `rd.CreateTargetControl`.

- [ ] T5: fix(capture_control): shutdown TargetControl on failed connection (B28)
  - File: `src/rdc/commands/capture_control.py` lines 41-47
  - In `_connect()`, when `tc is not None` but `tc.Connected()` is False, call
    `tc.Shutdown()` before raising `SystemExit(1)`. This prevents the partially-
    initialised TargetControl handle from leaking the connection.

- [ ] T6: test(capture_control): add unit tests for B28 Shutdown-on-failure path
  - File: `tests/unit/test_capture_control.py`
  - Add cases: (a) tc is None → SystemExit(1), no Shutdown; (b) tc not None,
    Connected()=False → Shutdown called, then SystemExit(1); (c) tc not None,
    Connected()=True → tc returned, Shutdown not called by _connect.

## Implementation order

1. T1 (B26 — trivial one-liner, isolated to capture.py)
2. T2 (B26 tests — validates T1 before touching other files)
3. T5 (B28 — isolated to capture_control.py, no cross-file dependency)
4. T6 (B28 tests — validates T5)
5. T3 (B27 — requires understanding of CaptureResult + tc lifecycle)
6. T4 (B27 tests — validates T3)

Run `pixi run lint && pixi run test` after each task pair (fix + test) before
moving to the next bug.

## Estimated complexity

| Task | Complexity | Notes |
|------|-----------|-------|
| T1   | XS        | single boolean operand removal |
| T2   | S         | ~5 parametrised test cases, existing mock infra |
| T3   | S         | ~8 lines: brief connect, GetPID, Shutdown, fallback |
| T4   | S         | ~3 test cases, mock tc object needed |
| T5   | XS        | one `if tc is not None: tc.Shutdown()` guard |
| T6   | S         | ~3 test cases, mock tc with Connected() side effect |
