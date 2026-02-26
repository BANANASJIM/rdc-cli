"""Shared CLI command helpers for daemon communication."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from typing import Any, cast

import click
from click.shell_completion import CompletionItem

from rdc.capture_core import CaptureResult
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
    "completion_call",
    "fetch_remote_file",
    "write_capture_to_path",
    "_json_mode",
    "split_session_active",
    "complete_eid",
    "complete_pass_name",
    "complete_pass_identifier",
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


def completion_call(method: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Send a request for shell completion, silently returning None on failure."""
    with contextlib.redirect_stderr(io.StringIO()):
        return try_call(method, params)


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


def write_capture_to_path(result: CaptureResult, dest: Path) -> CaptureResult:
    """Fetch ``result.path`` and persist it locally.

    ``fetch_remote_file`` errors (SystemExit) propagate; local ``OSError``
    writes are caught and converted into a failed ``CaptureResult``.  On
    success, ``result.path`` points to ``dest`` and ``result.local`` is True.
    """
    if not result.success or not result.path:
        return result
    try:
        data = fetch_remote_file(result.path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    except OSError as exc:
        result.success = False
        result.error = f"failed to write capture to {dest}: {exc}"
        result.path = ""
        return result
    result.path = str(dest)
    result.local = True
    return result


def _split_session() -> SessionState | None:
    session = load_session()
    if session is None:
        return None
    pid = getattr(session, "pid", 1)
    if isinstance(pid, int) and pid == 0:
        return session
    return None


def split_session_active() -> bool:
    """Return True if the session file indicates Split mode (pid == 0).

    This is a routing hint only—the next RPC will still rely on
    ``require_session()`` to ping the daemon and clean up stale sessions.
    """
    return _split_session() is not None


def complete_eid(
    _ctx: click.Context | None,
    _param: click.Parameter | None,
    incomplete: str,
) -> list[CompletionItem]:
    """Return shell-completion items for event-id arguments.

    Completion is best-effort and must stay silent/fail-safe when session or
    daemon access is unavailable.
    """
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            result = try_call("events", {})
            if result is None:
                return []
            rows = result.get("events", [])
            if not isinstance(rows, list):
                return []

            items: list[CompletionItem] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                eid = row.get("eid")
                if not isinstance(eid, int):
                    continue
                value = str(eid)
                if incomplete and not value.startswith(incomplete):
                    continue
                label = row.get("name")
                if isinstance(label, str) and label:
                    items.append(CompletionItem(value, help=label))
                else:
                    items.append(CompletionItem(value))
            return items
        except Exception:  # noqa: BLE001
            return []


def complete_pass_name(
    _ctx: click.Context | None,
    _param: click.Parameter | None,
    incomplete: str,
) -> list[CompletionItem]:
    """Complete render pass names from daemon metadata.

    Fail-safe behavior: return an empty list if session/RPC is unavailable.
    """
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            result = try_call("passes", {})
            if not isinstance(result, dict):
                return []
            tree = result.get("tree")
            if not isinstance(tree, dict):
                return []
            passes = tree.get("passes", [])
            if not isinstance(passes, list):
                return []

            prefix = incomplete.casefold()
            names: set[str] = set()
            items: list[CompletionItem] = []
            for p in passes:
                if not isinstance(p, dict):
                    continue
                name = p.get("name")
                if not isinstance(name, str):
                    continue
                if prefix and not name.casefold().startswith(prefix):
                    continue
                if name in names:
                    continue
                names.add(name)
                items.append(CompletionItem(name))
            return items
        except Exception:  # noqa: BLE001
            return []


def complete_pass_identifier(
    _ctx: click.Context | None,
    _param: click.Parameter | None,
    incomplete: str,
) -> list[CompletionItem]:
    """Complete pass identifier as index or name."""
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            result = try_call("passes", {})
            if not isinstance(result, dict):
                return []
            tree = result.get("tree", {})
            passes = tree.get("passes", []) if isinstance(tree, dict) else []
            if not isinstance(passes, list):
                return []

            prefix = incomplete.casefold()
            items: list[CompletionItem] = []
            seen_names: set[str] = set()
            for index, p in enumerate(passes):
                if not isinstance(p, dict):
                    continue
                index_text = str(index)
                if index_text.startswith(incomplete):
                    items.append(CompletionItem(index_text))

                name = p.get("name")
                if not isinstance(name, str) or not name:
                    continue
                if prefix and not name.casefold().startswith(prefix):
                    continue
                if name in seen_names:
                    continue
                seen_names.add(name)
                items.append(CompletionItem(name))
            return items
        except Exception:  # noqa: BLE001
            return []
