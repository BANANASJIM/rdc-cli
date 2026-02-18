from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


def parse_version_tuple(value: str) -> tuple[int, int]:
    """Parse RenderDoc version string into (major, minor)."""
    match = re.search(r"(\d+)\.(\d+)", value)
    if not match:
        return (0, 0)
    return int(match.group(1)), int(match.group(2))


@dataclass(frozen=True)
class RenderDocAdapter:
    """Minimal compatibility adapter for RenderDoc API changes."""

    controller: Any
    version: tuple[int, int]

    def get_root_actions(self) -> Any:
        """Return root actions with compatibility handling."""
        if self.version >= (1, 32) and hasattr(self.controller, "GetRootActions"):
            return self.controller.GetRootActions()
        if hasattr(self.controller, "GetDrawcalls"):
            return self.controller.GetDrawcalls()
        raise AttributeError("controller has neither GetRootActions nor GetDrawcalls")
