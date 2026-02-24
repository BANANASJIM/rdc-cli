# Fix Daemon Lifecycle Bugs B21 + B22 + B23 + B25

## Summary

Four bugs in the daemon session lifecycle: B21 causes the daemon to block forever when a misbehaving client connects but never sends data; B22 has a TOCTOU race when selecting a port that allows another process to steal it; B23 silently starts a limited no-replay session without informing the user; B25 silently ignores a failed graceful shutdown and leaves a zombie daemon process running.

## Motivation

B21 makes the daemon permanently unresponsive to any subsequent client after a single misbehaving connection — effectively a denial-of-service on the user's own daemon. B22 is an intermittent startup failure that is hard to reproduce and diagnose. B23 is a silent degradation that confuses users who expect full replay functionality. B25 is a resource leak that accumulates zombie processes across failed `rdc close` calls.

---

## Bug Analysis

### B21: Blocking accept with no connection timeout (P2)

#### Current behavior

After `server.accept()` returns a new connection `conn`, the daemon immediately calls `recv_line(conn)` to read the first JSON-RPC request. If the client connects but never sends any data (e.g., a port scanner, a crashed client, or a stale TCP connection), `recv_line` blocks indefinitely. The daemon's accept loop is single-threaded, so no other client can connect while the block is active.

#### Root cause

`src/rdc/daemon_server.py` does not call `conn.settimeout()` after `server.accept()`. The connection socket inherits the server socket's blocking mode with no timeout, so `recv_line`'s internal `sock.recv()` call blocks forever waiting for the first byte.

#### Proposed fix

After `server.accept()`, set a 10-second read timeout on the returned connection socket before attempting to read:

```python
conn, addr = server.accept()
conn.settimeout(10.0)
```

`recv_line` in `src/rdc/_transport.py` calls `sock.recv()` in a loop. When the socket times out, Python raises `TimeoutError` (a subclass of `OSError`). The existing `except (OSError, ValueError)` clause in the daemon's request-handling loop already catches `OSError`, but the catch block must explicitly handle `TimeoutError` to log a specific warning and continue accepting new connections rather than propagating the exception.

Change the except clause in the connection handler to:

```python
except TimeoutError:
    log.warning("client connected but sent no data within 10s, closing")
    conn.close()
    continue
except (OSError, ValueError) as exc:
    log.warning("connection error: %s", exc)
    conn.close()
    continue
```

---

### B22: TOCTOU race in `pick_port()` (P2)

#### Current behavior

`src/rdc/services/session_service.py` contains `pick_port()` which binds a socket to port 0 (kernel assigns a free port), reads the assigned port number, closes the socket, and returns the port. `open_session()` then starts the daemon process that tries to bind to that same port. Between the `close()` and the daemon's `bind()`, another process can acquire the port, causing the daemon to fail with `Address already in use`.

#### Root cause

This is a classic TOCTOU (time-of-check-time-of-use) race. The port is "free" when checked but may be occupied by the time the daemon uses it. The gap is small but nonzero and occurs on every session open.

#### Proposed fix

Add a retry loop with up to 3 attempts in `open_session()`. On each attempt, call `pick_port()` to get a candidate port and attempt to start the daemon. If the daemon fails to bind (detected by checking the startup health-check timeout or a bind-failure sentinel in the daemon's startup output), retry with a fresh port. After 3 failed attempts, raise the error.

```python
MAX_PORT_RETRIES = 3

for attempt in range(MAX_PORT_RETRIES):
    port = pick_port()
    try:
        _start_daemon(port, ...)
        break
    except PortConflictError:
        if attempt == MAX_PORT_RETRIES - 1:
            raise
        log.warning("port %d taken, retrying (%d/%d)", port, attempt + 1, MAX_PORT_RETRIES)
```

The existing daemon startup already detects bind failures via its health-check loop; a failed bind causes the daemon process to exit quickly with a non-zero code. `open_session()` already checks for daemon liveness — this retry wraps that check.

---

### B23: Silent no-replay mode on missing renderdoc (P3)

#### Current behavior

When renderdoc is unavailable (e.g., library not installed), `open_session()` starts the daemon in no-replay mode and returns a generic success message such as `"session opened on port 12345"`. The user has no indication that replay commands (`info`, `events`, `draws`, etc.) will all fail with "renderdoc unavailable".

#### Root cause

`src/rdc/services/session_service.py` calls `_renderdoc_available()` to decide whether to pass `--no-replay` to the daemon process, but the return value of `open_session()` does not distinguish between full-replay and no-replay sessions. `src/rdc/commands/session.py` prints whatever message `open_session()` returns without any additional warnings.

#### Proposed fix

In `open_session()`, when `_renderdoc_available()` returns `False`, append a flag to the returned message:

```python
if not _renderdoc_available():
    mode_suffix = " (no-replay mode: renderdoc unavailable)"
    # append to message before returning
```

In `src/rdc/commands/session.py`, in `open_cmd`, check the returned message for the no-replay suffix (or accept a structured return) and emit a `stderr` warning:

```python
if "no-replay mode" in result:
    click.echo("warning: session started in no-replay mode — renderdoc is unavailable", err=True)
```

This ensures the user sees the warning both in the success message and as an explicit `warning:` line on stderr, which is visible even when the output is piped.

---

### B25: Silent pass on shutdown RPC failure leaves zombie daemon (P3)

#### Current behavior

`close_session()` in `src/rdc/services/session_service.py` calls `send_request` to send a `shutdown` JSON-RPC to the daemon. If `send_request` raises (e.g., the daemon is already dead, connection refused, or the socket was broken), the `except` block executes `pass` and the function returns as if the session was closed. If the daemon is still alive (e.g., in a half-open state), it continues running as a zombie process.

#### Root cause

The `except` block in `close_session()` does not attempt to kill the daemon process when the graceful RPC path fails. The session's PID is available in the session file, so a fallback SIGTERM is straightforward.

#### Proposed fix

In `close_session()`, replace the bare `pass` with a fallback `os.kill`:

```python
try:
    send_request(host, port, shutdown_payload)
except Exception:
    try:
        os.kill(pid, signal.SIGTERM)
        log.warning("shutdown RPC failed; sent SIGTERM to daemon pid %d", pid)
    except ProcessLookupError:
        pass  # already gone
```

Import `signal` at the top of `session_service.py` (it is already available in the standard library). The `ProcessLookupError` guard handles the case where the daemon has already exited between the failed RPC and the `os.kill` call.

---

## Risk Assessment

**B21 fix (connection timeout):** Low risk. `settimeout(10.0)` only affects idle connections. All legitimate clients send their first request well within 10 seconds. The `TimeoutError` branch is new but isolated to the per-connection error handler.

**B22 fix (port retry):** Low risk. The retry loop wraps existing behavior. If the first attempt succeeds (the common case), behavior is identical to before. Three attempts is sufficient to handle even pathological port churn.

**B23 fix (no-replay warning):** Very low risk. Purely additive: appends to a message string and adds a `click.echo(..., err=True)` call. No logic changes to the session startup path.

**B25 fix (SIGTERM fallback):** Low risk. The `os.kill` call is only reached when `send_request` raises, which means the graceful path already failed. `ProcessLookupError` is caught to handle the already-dead case. No risk of double-kill because `send_request` failure implies the daemon did not receive the shutdown RPC.

## Alternatives Considered

**B21 — per-connection thread:** Spawn a thread per connection so a slow client does not block accept. Rejected: the daemon is intentionally single-connection-at-a-time; threading adds complexity and is unnecessary if the timeout is set.

**B22 — SO_REUSEADDR on daemon socket:** Set `SO_REUSEADDR` on the daemon's listen socket to allow re-bind. Rejected: does not solve the race — the port is still unbound between `pick_port` close and daemon bind; `SO_REUSEADDR` only helps for `TIME_WAIT` states, not active listeners.

**B23 — structured return value from `open_session()`:** Return a dataclass with a `no_replay: bool` field instead of embedding the suffix in a string. Deferred: the current string-based API is simpler and sufficient for the warning use case. A structured return can be introduced as a follow-up refactor.

**B25 — SIGKILL instead of SIGTERM:** Use `SIGKILL` for guaranteed termination. Rejected: `SIGTERM` is the conventional graceful signal; it allows the daemon to flush any in-progress state. If SIGTERM is not honored, the user can always kill manually. Escalating to SIGKILL automatically is too aggressive for a P3 fix.
