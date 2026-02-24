from __future__ import annotations

import atexit
import secrets
import threading
from dataclasses import dataclass
from typing import Any

from rdc import _platform
from rdc.daemon_client import send_request
from rdc.protocol import shutdown_request
from rdc.services.session_service import pick_port, start_daemon, wait_for_ping
from rdc.session_state import is_pid_alive


@dataclass
class DiffContext:
    session_id: str
    host: str
    port_a: int
    port_b: int
    token_a: str
    token_b: str
    pid_a: int
    pid_b: int
    capture_a: str
    capture_b: str


def start_diff_session(
    capture_a: str,
    capture_b: str,
    *,
    timeout_s: float = 60.0,
) -> tuple[DiffContext | None, str]:
    """Start two daemons for diff comparison.

    Returns:
        (DiffContext, "") on success, (None, error_message) on failure.
    """
    session_id = secrets.token_hex(6)
    host = "127.0.0.1"
    port_a = pick_port()
    port_b = pick_port()
    while port_b == port_a:
        port_b = pick_port()
    token_a = secrets.token_hex(16)
    token_b = secrets.token_hex(16)

    # Fork daemon A
    try:
        proc_a = start_daemon(capture_a, port_a, token_a, idle_timeout=120)
    except Exception as exc:  # noqa: BLE001
        return None, f"failed to start daemon A: {exc}"

    # Fork daemon B; kill A on failure
    try:
        proc_b = start_daemon(capture_b, port_b, token_b, idle_timeout=120)
    except Exception as exc:  # noqa: BLE001
        proc_a.kill()
        return None, f"failed to start daemon B: {exc}"

    # Concurrent ping
    results: list[tuple[bool, str]] = [
        (False, "not started"),
        (False, "not started"),
    ]

    def _ping(idx: int, port: int, token: str) -> None:
        results[idx] = wait_for_ping(host, port, token, timeout_s=timeout_s)

    t_a = threading.Thread(target=_ping, args=(0, port_a, token_a), daemon=True)
    t_b = threading.Thread(target=_ping, args=(1, port_b, token_b), daemon=True)
    t_a.start()
    t_b.start()
    t_a.join()
    t_b.join()

    ok_a, err_a = results[0]
    ok_b, err_b = results[1]

    if not ok_a or not ok_b:
        proc_a.kill()
        proc_b.kill()
        errors = []
        if not ok_a:
            errors.append(f"daemon A: {err_a}")
        if not ok_b:
            errors.append(f"daemon B: {err_b}")
        return None, "; ".join(errors)

    ctx = DiffContext(
        session_id=session_id,
        host=host,
        port_a=port_a,
        port_b=port_b,
        token_a=token_a,
        token_b=token_b,
        pid_a=proc_a.pid,
        pid_b=proc_b.pid,
        capture_a=capture_a,
        capture_b=capture_b,
    )
    atexit.register(stop_diff_session, ctx)
    return ctx, ""


def stop_diff_session(ctx: DiffContext) -> None:
    """Shut down both daemons. Best-effort, never raises, idempotent."""
    atexit.unregister(stop_diff_session)
    for port, token in [(ctx.port_a, ctx.token_a), (ctx.port_b, ctx.token_b)]:
        try:
            send_request(ctx.host, port, shutdown_request(token), timeout=2.0)
        except Exception:  # noqa: BLE001
            pass

    for pid in (ctx.pid_a, ctx.pid_b):
        if is_pid_alive(pid):
            _platform.terminate_process(pid)


def _do_query(
    host: str,
    port: int,
    token: str,
    method: str,
    params: dict[str, Any],
    timeout_s: float,
    out: list[dict[str, Any] | None],
    idx: int,
) -> None:
    """Worker for a single RPC call. Stores result at out[idx]."""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1,
        "params": {**params, "_token": token},
    }
    try:
        resp = send_request(host, port, payload, timeout=timeout_s)
        if "error" in resp:
            out[idx] = None
        else:
            out[idx] = resp
    except Exception:  # noqa: BLE001
        out[idx] = None


def query_both(
    ctx: DiffContext,
    method: str,
    params: dict[str, Any],
    *,
    timeout_s: float = 30.0,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    """Send same RPC to both daemons concurrently.

    Returns:
        (result_a, result_b, error_string). Partial results on single-side failure.
    """
    out: list[dict[str, Any] | None] = [None, None]
    t_a = threading.Thread(
        target=_do_query,
        args=(ctx.host, ctx.port_a, ctx.token_a, method, params, timeout_s, out, 0),
        daemon=True,
    )
    t_b = threading.Thread(
        target=_do_query,
        args=(ctx.host, ctx.port_b, ctx.token_b, method, params, timeout_s, out, 1),
        daemon=True,
    )
    t_a.start()
    t_b.start()
    t_a.join()
    t_b.join()

    err = ""
    if out[0] is None and out[1] is None:
        err = "both daemons failed"
    return out[0], out[1], err


def query_both_sync(
    ctx: DiffContext,
    calls: list[tuple[str, dict[str, Any]]],
    *,
    timeout_s: float = 30.0,
) -> tuple[list[dict[str, Any] | None], list[dict[str, Any] | None], str]:
    """Batch variant: send N calls to both daemons (2N threads).

    Returns:
        (results_a, results_b, error_string). Order matches input calls.
    """
    n = len(calls)
    out_a: list[dict[str, Any] | None] = [None] * n
    out_b: list[dict[str, Any] | None] = [None] * n
    threads: list[threading.Thread] = []

    for i, (method, params) in enumerate(calls):
        t_a = threading.Thread(
            target=_do_query,
            args=(ctx.host, ctx.port_a, ctx.token_a, method, params, timeout_s, out_a, i),
            daemon=True,
        )
        t_b = threading.Thread(
            target=_do_query,
            args=(ctx.host, ctx.port_b, ctx.token_b, method, params, timeout_s, out_b, i),
            daemon=True,
        )
        threads.extend([t_a, t_b])

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    all_none = n > 0 and all(r is None for r in out_a) and all(r is None for r in out_b)
    err = "all queries failed" if all_none else ""
    return out_a, out_b, err


def query_each_sync(
    ctx: DiffContext,
    calls_a: list[tuple[str, dict[str, Any]]],
    calls_b: list[tuple[str, dict[str, Any]]],
    *,
    timeout_s: float = 30.0,
) -> tuple[list[dict[str, Any] | None], list[dict[str, Any] | None], str]:
    """Send N calls to daemon A and M calls to daemon B concurrently.

    Unlike ``query_both_sync`` which sends identical calls to both daemons,
    this variant accepts separate call lists (e.g. different EIDs per side).

    Returns:
        (results_a, results_b, error_string). Order matches input call lists.
    """
    na, nb = len(calls_a), len(calls_b)
    out_a: list[dict[str, Any] | None] = [None] * na
    out_b: list[dict[str, Any] | None] = [None] * nb
    threads: list[threading.Thread] = []

    for i, (method, params) in enumerate(calls_a):
        t = threading.Thread(
            target=_do_query,
            args=(ctx.host, ctx.port_a, ctx.token_a, method, params, timeout_s, out_a, i),
            daemon=True,
        )
        threads.append(t)

    for i, (method, params) in enumerate(calls_b):
        t = threading.Thread(
            target=_do_query,
            args=(ctx.host, ctx.port_b, ctx.token_b, method, params, timeout_s, out_b, i),
            daemon=True,
        )
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    all_none = (na + nb > 0) and all(r is None for r in out_a) and all(r is None for r in out_b)
    err = "all queries failed" if all_none else ""
    return out_a, out_b, err
