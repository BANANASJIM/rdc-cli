# Proposal: Fix Target Process Leaks in Capture Subsystem (B26, B27, B28)

## Summary

Three related bugs cause injected target processes to become orphaned, consuming RenderDoc
client slots until the "Maximum number of clients reached" error prevents new captures.
B26 is the primary source: failed captures never terminate the target. B27 leaves the pid
unknown in `--trigger` mode so callers cannot clean up. B28 is a defensive correctness gap
where a partially-constructed TargetControl object is abandoned without `Shutdown()`.

## Background

`ExecuteAndInject` launches the target process and returns an `ident` + implicit OS PID.
The current cleanup condition in `capture.py` line 121 is:

```python
if not trigger and not keep_alive and result.success and result.pid:
    terminate_process(result.pid)
```

The `result.success` guard is the root cause of B26: on timeout or disconnect, `success`
is `False`, so `terminate_process` is skipped even though a real OS process is running.
On XWayland each orphan holds a Wayland/X11 connection slot inside RenderDoc's overlay
multiplexer, exhausting the fixed-size client table.

B27 is a secondary issue: the `--trigger` path in `capture_core.py` returns a
`CaptureResult` with `pid=0` because it skips the `CreateTargetControl` connection that
is the only place `GetPID()` is called. This means even if the caller wanted to clean up,
it has no pid to act on.

B28 is a defensive gap in `_connect()` in `capture_control.py`: when
`CreateTargetControl` returns a non-None object that is not yet connected,
the function raises `SystemExit` without calling `tc.Shutdown()`, leaking
the partially-initialised object.

## Changes

### B26: Terminate target on all non-keepalive, non-trigger paths

**File:** `src/rdc/commands/capture.py`, line 121.

Remove the `result.success` guard. Terminate whenever the pid is known and neither
`keep_alive` nor `trigger` is set:

```python
# before
if not trigger and not keep_alive and result.success and result.pid:
    terminate_process(result.pid)

# after
if not trigger and not keep_alive and result.pid:
    terminate_process(result.pid)
```

Rationale: the target was launched unconditionally by `ExecuteAndInject`. Whether the
capture succeeded or timed out, the process is running and must be cleaned up unless the
user explicitly opted into keeping it alive.

### B27: Return pid in --trigger mode

**File:** `src/rdc/capture_core.py`, lines 113-114.

The `trigger` early-return path must also populate `pid`. After `ExecuteAndInject`
succeeds we already hold a valid `ident`. We briefly open a `CreateTargetControl`
connection solely to call `GetPID()`, then immediately shut it down:

```python
# before
if trigger:
    return CaptureResult(success=True, ident=result.ident)

# after
if trigger:
    pid = _get_pid_for_ident(rd, result.ident)
    return CaptureResult(success=True, ident=result.ident, pid=pid)
```

New helper (added to `capture_core.py`):

```python
def _get_pid_for_ident(rd: Any, ident: int) -> int:
    """Connect briefly to retrieve the OS PID for an injected ident."""
    tc = rd.CreateTargetControl("", ident, "rdc-cli", True)
    if tc is None:
        return 0
    try:
        return tc.GetPID() if tc.Connected() else 0
    finally:
        tc.Shutdown()
```

With `pid` populated, the B26 fix in `capture.py` also applies in trigger mode if the
user does NOT pass `--trigger`, and callers that inspect `result.pid` can take their own
action. Note: `--trigger` itself still skips `terminate_process` (the `not trigger` guard
is preserved), which is correct because the user intends to keep the process running for
subsequent `rdc attach` / `rdc capture-trigger` calls.

### B28: Call Shutdown before raising on not-connected TargetControl

**File:** `src/rdc/commands/capture_control.py`, lines 41-47.

The current `_connect()` function checks `tc is None or not tc.Connected()` in one branch
and raises immediately. When `tc` is not None but not connected, `Shutdown()` is never
called:

```python
# before
def _connect(rd: Any, host: str, ident: int) -> Any:
    tc = rd.CreateTargetControl(host, ident, "rdc-cli", True)
    if tc is None or not tc.Connected():
        click.echo(f"error: failed to connect to target ident={ident}", err=True)
        raise SystemExit(1)
    return tc

# after
def _connect(rd: Any, host: str, ident: int) -> Any:
    tc = rd.CreateTargetControl(host, ident, "rdc-cli", True)
    if tc is None:
        click.echo(f"error: failed to connect to target ident={ident}", err=True)
        raise SystemExit(1)
    if not tc.Connected():
        tc.Shutdown()
        click.echo(f"error: failed to connect to target ident={ident}", err=True)
        raise SystemExit(1)
    return tc
```

## Risks

- **B27 extra connection**: The brief `CreateTargetControl` for `GetPID()` in trigger mode
  adds one extra slot consumption. This is transient (the connection is shut down
  immediately after reading the PID) and is strictly less harmful than the existing leak.
  If the connection itself fails, `pid` falls back to 0 and the behaviour is identical to
  the current (unfixed) code.

- **B26 terminate on error path**: Calling `terminate_process` on a pid when capture
  failed is the correct policy since the user did not ask for `--keep-alive`. The only
  edge case is `wait_for_exit=True`: if the process has already exited, `terminate_process`
  returns `False` gracefully (the current implementation already handles ESRCH).

- **B28**: Low risk — the split of the `None` and `not Connected()` checks is a pure
  defensive refactor with no observable behaviour change under the normal (forceConnection
  = True) path.

## Alternatives Considered

- **Add `rdc target-kill <ident>` command**: Rejected for B27 as a primary fix. The real
  problem is that capture.py has the cleanup logic and just needs the pid. Exposing a kill
  command is a separate UX feature and does not close the leak for automated callers.

- **Track idents in a file and sweep on next run**: Rejected as overly complex and
  fragile. Direct termination at the call site is simpler and more reliable.

- **Suppress B26 only on XWayland**: Rejected. The leak is wrong on all platforms; the
  XWayland symptom just makes it more visible sooner.
