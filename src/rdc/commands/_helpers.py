"""Shared CLI command helpers for daemon communication."""

from __future__ import annotations

from typing import Any, cast

import click

from rdc.daemon_client import send_request
from rdc.protocol import _request
from rdc.session_state import load_session

__all__ = ["require_session", "call"]


def require_session() -> tuple[str, int, str]:
    """Load active session or exit with error.

    Returns:
        Tuple of (host, port, token).
    """
    session = load_session()
    if session is None:
        click.echo("error: no active session (run 'rdc open' first)", err=True)
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
    except OSError as exc:
        click.echo(f"error: daemon unreachable: {exc}", err=True)
        raise SystemExit(1) from exc
    if "error" in response:
        click.echo(f"error: {response['error']['message']}", err=True)
        raise SystemExit(1)
    return cast(dict[str, Any], response["result"])
