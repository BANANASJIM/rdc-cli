# Fix: Daemon Startup Timeout for Large Captures

## Problem

Stress testing found 5/92 captures (375–596 MB) fail with "daemon failed to start".
Root cause: `wait_for_ping()` has a 2.0s hardcoded timeout, but `_load_replay()`
alone takes 2.0–2.5s for these files.

Secondary: daemon stderr goes to DEVNULL — real errors are invisible.

## Changes

### `session_service.py`

1. **`start_daemon()`**: `stderr=subprocess.DEVNULL` → `stderr=subprocess.PIPE`
2. **`wait_for_ping()`**:
   - Default timeout 2.0 → 15.0
   - Accept optional `proc: subprocess.Popen[str] | None = None`; poll for early exit
   - Return `tuple[bool, str]` — `(True, "")` on success, `(False, reason)` on failure
   - Only call `proc.poll()` in the loop — never read stderr here (avoids pipe deadlock)
3. **`open_session()`**:
   - Pass proc to `wait_for_ping()`
   - On failure: `proc.kill()` then `proc.communicate(timeout=5)` to safely drain stderr
   - Include stderr in error message; fall back to exit code if stderr is empty

### PIPE deadlock note

Linux pipe buffer is 64KB. During the ping loop we never read stderr, so the daemon
could block if it writes >64KB (e.g., Vulkan validation layers). In practice the daemon
only writes a short error string before exiting — this is safe. Stderr is drained only
after `proc.kill()` via `proc.communicate()`.

### Tests

See `test-plan.md`.
