"""Shared helpers for unit tests."""

from __future__ import annotations

from typing import Any


def rpc_request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    token: str = "tok",
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 request dict for daemon handler tests."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {"_token": token, **(params or {})},
    }
