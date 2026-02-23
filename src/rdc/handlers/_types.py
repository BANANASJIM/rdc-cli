"""Shared type aliases for handler modules."""

from __future__ import annotations

from collections.abc import Callable

# DaemonState lives in daemon_server which imports handler modules,
# so we use a string literal to break the cycle.  With
# ``from __future__ import annotations`` every annotation is a string
# at runtime anyway, so mypy resolves it via TYPE_CHECKING.
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState

Handler: TypeAlias = Callable[[int, dict[str, Any], "DaemonState"], tuple[dict[str, Any], bool]]
