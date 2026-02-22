"""Handler modules for JSON-RPC daemon methods."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState

    HandlerFunc = Callable[[int, dict[str, Any], DaemonState], tuple[dict[str, Any], bool]]
else:
    HandlerFunc = Any

__all__ = ["HandlerFunc"]
