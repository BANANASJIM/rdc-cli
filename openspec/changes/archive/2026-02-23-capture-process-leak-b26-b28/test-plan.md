# Test Plan: Capture Process Leak Fixes (B26, B27, B28)

## Scope

Three unit-test suites covering the buggy code paths:

| Bug | File | Function | Nature |
|-----|------|----------|--------|
| B26 | `src/rdc/commands/capture.py:121` | `capture_cmd` | Failed captures skip `terminate_process` |
| B27 | `src/rdc/capture_core.py:113-114` | `execute_and_capture` | `--trigger` returns `pid=0` |
| B28 | `src/rdc/commands/capture_control.py:41-47` | `_connect` | `tc.Shutdown()` missing before `SystemExit` |

No new test files are created. Tests are appended to the three existing files:

- `tests/unit/test_capture.py` — B26 and B27 (CLI layer)
- `tests/unit/test_capture_core.py` — B27 (core layer)
- `tests/unit/test_capture_control.py` — B28

---

## Test Matrix

### B26 — Failed capture must still terminate target process

**Root cause**: `capture.py:121` guards `terminate_process` with `result.success`, so any
failure leaves the injected process running.

**Fixed condition**: call `terminate_process(result.pid)` whenever
`not trigger and not keep_alive and result.pid` — regardless of `result.success`.

All tests go in `tests/unit/test_capture.py`.

Monkeypatch targets (same pattern as existing tests in that file):
- `rdc.commands.capture.find_renderdoc` → `lambda: MagicMock()`
- `rdc.commands.capture.execute_and_capture` → returns a crafted `CaptureResult`
- `rdc.commands.capture.build_capture_options` → `lambda opts: MagicMock()`
- `rdc.commands.capture.terminate_process` → side-effect appends pid to `terminated: list[int]`

Use the existing `_setup_capture_with_terminate` helper already defined in `test_capture.py`.

#### TC-B26-1 `test_failed_capture_timeout_terminates_process`

```python
def test_failed_capture_timeout_terminates_process(monkeypatch: Any) -> None:
    terminated = _setup_capture_with_terminate(
        monkeypatch, success=False, error="timeout waiting for capture", pid=5678
    )
    result = CliRunner().invoke(capture_cmd, ["--", "/usr/bin/app"])
    assert result.exit_code != 0
    assert terminated == [5678]
```

Assert: `terminate_process` IS called with `pid=5678` even though `success=False`.

#### TC-B26-2 `test_failed_capture_disconnect_terminates_process`

```python
def test_failed_capture_disconnect_terminates_process(monkeypatch: Any) -> None:
    terminated = _setup_capture_with_terminate(
        monkeypatch, success=False, error="target disconnected", pid=9101
    )
    result = CliRunner().invoke(capture_cmd, ["--", "/usr/bin/app"])
    assert result.exit_code != 0
    assert terminated == [9101]
```

Assert: `terminate_process` IS called with `pid=9101`.

#### TC-B26-3 `test_failed_capture_zero_pid_no_termination`

```python
def test_failed_capture_zero_pid_no_termination(monkeypatch: Any) -> None:
    terminated = _setup_capture_with_terminate(
        monkeypatch, success=False, error="inject failed", pid=0
    )
    result = CliRunner().invoke(capture_cmd, ["--", "/usr/bin/app"])
    assert result.exit_code != 0
    assert terminated == []
```

Assert: when `pid=0`, `terminate_process` is NOT called (pid=0 is sentinel for "unknown").

#### TC-B26-4 `test_failed_capture_keep_alive_skips_termination`

```python
def test_failed_capture_keep_alive_skips_termination(monkeypatch: Any) -> None:
    terminated = _setup_capture_with_terminate(
        monkeypatch, success=False, error="timeout waiting for capture", pid=7777
    )
    result = CliRunner().invoke(capture_cmd, ["--keep-alive", "--", "/usr/bin/app"])
    assert result.exit_code != 0
    assert terminated == []
```

Assert: `--keep-alive` suppresses termination even on failure with a valid pid.

Note: The existing `test_failed_capture_skips_termination` which tests `pid=1234`
but asserts `terminated == []` documents the *old* (buggy) behavior and must be
**deleted or updated** when the fix is applied. The `--trigger` termination skip is
already covered by the existing `test_trigger_skips_termination` test.

---

### B27 — `--trigger` mode must return a non-zero pid

**Root cause**: `capture_core.py:113-114` early-returns `CaptureResult(success=True, ident=result.ident)`
without obtaining the pid from a TargetControl connection.

**Fixed behavior**: briefly connect (`CreateTargetControl`), call `tc.GetPID()`, then
`tc.Shutdown()`, and return `CaptureResult(success=True, ident=..., pid=<pid>)`.

**Existing test impact**: The existing `test_capture_trigger_mode` in `test_capture_core.py`
asserts `assert rd._calls["tc_create"] == []` — this will fail after B27 since the trigger path
now calls `CreateTargetControl`. This test must be updated to
`assert len(rd._calls["tc_create"]) == 1`.

#### B27 core-layer tests — `tests/unit/test_capture_core.py`

Monkeypatch target: none needed — use `_make_mock_rd()` helper already defined in that file.
`mock_rd.MockTargetControl.GetPID()` must return a nonzero value (check mock; add if missing).

##### TC-B27-1 `test_capture_trigger_returns_nonzero_pid`

```python
def test_capture_trigger_returns_nonzero_pid(self) -> None:
    from rdc.capture_core import execute_and_capture

    rd = _make_mock_rd()  # inject_ident=12345 by default

    result = execute_and_capture(rd, "/usr/bin/app", trigger=True)
    assert result.success is True
    assert result.ident == 12345
    assert result.pid != 0
```

Assert: `result.pid` is nonzero after fix. Before fix this would be 0.

##### TC-B27-2 `test_capture_trigger_connects_briefly_then_shuts_down`

```python
def test_capture_trigger_connects_briefly_then_shuts_down(self) -> None:
    from rdc.capture_core import execute_and_capture

    rd = _make_mock_rd()
    result = execute_and_capture(rd, "/usr/bin/app", trigger=True)

    assert result.success is True
    # After fix: one tc_create call to get pid
    assert len(rd._calls["tc_create"]) == 1
    # tc.Shutdown must be called (no resource leak)
    assert rd._tc.shutdown_count >= 1
```

This requires `MockTargetControl` to track `Shutdown` calls. If it does not, add
`self.shutdown_count: int = 0` and increment in `Shutdown()`.

##### TC-B27-3 `test_capture_trigger_connect_failure_still_succeeds`

```python
def test_capture_trigger_connect_failure_still_succeeds(self) -> None:
    from rdc.capture_core import execute_and_capture

    rd = _make_mock_rd()
    rd.CreateTargetControl = lambda *_a, **_kw: None  # connect fails

    result = execute_and_capture(rd, "/usr/bin/app", trigger=True)
    # Inject itself succeeded; trigger mode should still report success
    # pid will be 0 (fallback) but not crash
    assert result.success is True
    assert result.ident == 12345
    assert result.pid == 0
```

Assert: a failed brief connect in trigger mode degrades gracefully (pid=0, success=True), not
exception.

#### B27 CLI-layer test — `tests/unit/test_capture.py`

##### TC-B27-4 `test_trigger_mode_output_includes_pid`

```python
def test_trigger_mode_output_includes_pid(monkeypatch: Any) -> None:
    """--trigger output must include ident and pid info."""
    monkeypatch.setattr("rdc.commands.capture.find_renderdoc", lambda: MagicMock())
    monkeypatch.setattr(
        "rdc.commands.capture.execute_and_capture",
        lambda *a, **kw: _make_capture_result(success=True, path="", ident=99999, pid=3333),
    )
    monkeypatch.setattr("rdc.commands.capture.build_capture_options", lambda opts: MagicMock())

    result = CliRunner().invoke(capture_cmd, ["--trigger", "--", "/usr/bin/app"])
    assert result.exit_code == 0
    combined = result.output + (result.stderr or "")
    assert "99999" in combined  # ident present
```

Assert: `ident` appears in output so the user can run `rdc attach`.

---

### B28 — `_connect` must call `Shutdown` before raising `SystemExit`

**Root cause**: `capture_control.py:41-47` raises `SystemExit(1)` without calling `tc.Shutdown()`
when `tc` is not `None` but `tc.Connected()` returns `False`.

**Fixed behavior** (split into two separate checks, matching proposal):
```python
def _connect(rd, host, ident):
    tc = rd.CreateTargetControl(host, ident, "rdc-cli", True)
    if tc is None:
        click.echo(...)
        raise SystemExit(1)
    if not tc.Connected():
        tc.Shutdown()
        click.echo(...)
        raise SystemExit(1)
    return tc
```

All tests go in `tests/unit/test_capture_control.py`.

Monkeypatch target: `rdc.commands.capture_control.find_renderdoc`.

Use `_make_mock_tc(connected=False)` (already defined in that file) to produce a tc that returns
`False` from `Connected()`.

#### TC-B28-1 `test_connect_not_connected_calls_shutdown`

```python
def test_connect_not_connected_calls_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    """_connect must call tc.Shutdown() when tc is not None but not connected."""
    tc = _make_mock_tc(connected=False)
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(attach_cmd, ["12345"])
    assert result.exit_code != 0
    tc.Shutdown.assert_called_once()
```

Assert: `tc.Shutdown` was called exactly once even though the connection was refused.

#### TC-B28-2 `test_connect_none_tc_does_not_call_shutdown`

```python
def test_connect_none_tc_does_not_call_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    """_connect must not attempt Shutdown when CreateTargetControl returns None."""
    rd = MagicMock()
    rd.CreateTargetControl.return_value = None
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(attach_cmd, ["12345"])
    assert result.exit_code != 0
    # No tc to call Shutdown on — must not raise AttributeError
```

Assert: no `AttributeError` / no crash when `tc is None`.

#### TC-B28-3 `test_capture_trigger_not_connected_calls_shutdown`

```python
def test_capture_trigger_not_connected_calls_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    """_connect called by capture_trigger_cmd also shuts down a non-connected tc."""
    _save_state()  # needed: capture_trigger_cmd calls _resolve_ident() which reads saved state
    tc = _make_mock_tc(connected=False)
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_trigger_cmd, [])
    assert result.exit_code != 0
    tc.Shutdown.assert_called_once()
```

Assert: `_connect` used from `capture_trigger_cmd` also shuts down the non-connected tc.

#### TC-B28-4 `test_capture_list_not_connected_calls_shutdown`

```python
def test_capture_list_not_connected_calls_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    """_connect called by capture_list_cmd also shuts down a non-connected tc."""
    _save_state()  # needed: capture_list_cmd calls _resolve_ident() which reads saved state
    tc = _make_mock_tc(connected=False)
    rd = _make_mock_rd(tc)
    monkeypatch.setattr("rdc.commands.capture_control.find_renderdoc", lambda: rd)

    result = CliRunner().invoke(capture_list_cmd, ["--timeout", "0.1"])
    assert result.exit_code != 0
    tc.Shutdown.assert_called_once()
```

---

## Coverage Targets

| File | Current relevant lines | New lines exercised |
|------|----------------------|---------------------|
| `src/rdc/commands/capture.py` | line 121 (termination guard) | B26 success + failure + keep-alive + trigger branches |
| `src/rdc/capture_core.py` | lines 113-127 (trigger branch, pid fetch) | B27 trigger happy-path + connect-fail fallback |
| `src/rdc/commands/capture_control.py` | lines 41-47 (`_connect`) | B28 `tc is not None but not Connected` branch |

All new tests use only existing monkeypatching patterns; no new fixtures or conftest changes are
required. The only mock extension possibly needed is adding `shutdown_count` tracking to
`MockTargetControl` in `tests/mocks/mock_renderdoc.py` for TC-B27-2.
