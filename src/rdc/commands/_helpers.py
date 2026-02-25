"""Shared CLI command helpers for daemon communication."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import click

from rdc.daemon_client import send_request, send_request_binary
from rdc.discover import find_renderdoc
from rdc.protocol import _request
from rdc.session_state import SessionState, load_session

__all__ = [
    "require_session",
    "require_renderdoc",
    "call",
    "call_binary",
    "try_call",
    "fetch_remote_file",
    "_json_mode",
    "split_session_active",
]


def _json_mode() -> bool:
    """Return True if the current Click context has a JSON output flag set."""
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return False
    params = ctx.params
    return bool(params.get("use_json"))


def require_renderdoc() -> Any:
    """Find and return the renderdoc module, or exit with error."""
    rd = find_renderdoc()
    if rd is None:
        click.echo("error: renderdoc module not found", err=True)
        raise SystemExit(1)
    return rd


def require_session() -> tuple[str, int, str]:
    """Load active session or exit with error.

    Returns:
        Tuple of (host, port, token).
    """
    from rdc.protocol import ping_request
    from rdc.session_state import delete_session, is_pid_alive

    session = load_session()
    if session is None:
        msg = "no active session (run 'rdc open' first)"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1)
    pid = getattr(session, "pid", None)
    if isinstance(pid, int) and pid <= 0:
        try:
            ping = ping_request(session.token)
            resp = send_request(session.host, session.port, ping, timeout=2.0)
            if resp.get("result", {}).get("ok") is True:
                return session.host, session.port, session.token
        except Exception:  # noqa: BLE001
            pass
        delete_session()
        msg = "stale session cleaned (daemon died); run 'rdc open' to restart"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1)
    if isinstance(pid, int) and not is_pid_alive(pid):
        delete_session()
        msg = "stale session cleaned (daemon died); run 'rdc open' to restart"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1)
    return session.host, session.port, session.token


def call(method: str, params: dict[str, Any]) -> dict[str, Any]:
    """Send a JSON-RPC request to the daemon and return the result.

    Args:
        method: The JSON-RPC method name.
        params: Request parameters.

    Returns:
        The result dict from the daemon response.

    Raises:
        SystemExit: If the daemon returns an error.
    """
    host, port, token = require_session()
    payload = _request(method, 1, {"_token": token, **params}).to_dict()
    try:
        response = send_request(host, port, payload)
    except (OSError, ValueError) as exc:
        msg = f"daemon unreachable: {exc}"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1) from exc
    if "error" in response:
        msg = response["error"]["message"]
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1)
    return cast(dict[str, Any], response["result"])


def try_call(method: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Send a JSON-RPC request, returning None on failure.

    Unlike call(), this never exits -- failures are silent.
    Use for optional features where partial success is acceptable.
    """
    try:
        host, port, token = require_session()
    except SystemExit:
        return None
    payload = _request(method, 1, {"_token": token, **params}).to_dict()
    try:
        response = send_request(host, port, payload)
    except (OSError, ValueError):
        return None
    if "error" in response:
        return None
    return cast(dict[str, Any], response.get("result", {}))


def call_binary(method: str, params: dict[str, Any]) -> tuple[dict[str, Any], bytes | None]:
    """Send a JSON-RPC request expecting an optional binary payload.

    Returns:
        Tuple of (result_dict, binary_data_or_None).

    Raises:
        SystemExit: If the daemon returns an error or is unreachable.
    """
    host, port, token = require_session()
    payload = _request(method, 1, {"_token": token, **params}).to_dict()
    try:
        response, binary = send_request_binary(host, port, payload)
    except (OSError, ValueError) as exc:
        msg = f"daemon unreachable: {exc}"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1) from exc
    if "error" in response:
        msg = response["error"]["message"]
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        raise SystemExit(1)
    return cast(dict[str, Any], response["result"]), binary


def fetch_remote_file(path: str) -> bytes:
    """Fetch a file from the daemon machine, transparently handling local/remote.

    Returns:
        Raw file bytes.

    Raises:
        SystemExit: On any error.
    """
    session = load_session()
    pid = getattr(session, "pid", 1) if session else 1
    if pid > 0:
        try:
            return Path(path).read_bytes()
        except OSError as exc:
            click.echo(f"error: {path}: {exc}", err=True)
            raise SystemExit(1) from exc
    result, binary = call_binary("file_read", {"path": path})
    if binary is None:
        click.echo("error: daemon returned no binary data", err=True)
        raise SystemExit(1)
    return binary


def _split_session() -> SessionState | None:
    session = load_session()
    if session is None:
        return None
    pid = getattr(session, "pid", 1)
    if isinstance(pid, int) and pid == 0:
        return session
    return None


def split_session_active() -> bool:
    """Return True if an active split-mode session is detected (pid == 0)."""
    return _split_session() is not None
