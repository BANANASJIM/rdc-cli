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
    """Compatibility adapter for RenderDoc API changes across versions."""

    controller: Any
    version: tuple[int, int]

    def get_root_actions(self) -> Any:
        """Return root actions with compatibility handling."""
        if self.version >= (1, 32) and hasattr(self.controller, "GetRootActions"):
            return self.controller.GetRootActions()
        if hasattr(self.controller, "GetDrawcalls"):
            return self.controller.GetDrawcalls()
        raise AttributeError("controller has neither GetRootActions nor GetDrawcalls")

    def get_api_properties(self) -> Any:
        """Return API properties from the controller."""
        return self.controller.GetAPIProperties()

    def get_resources(self) -> Any:
        """Return all resources from the controller."""
        return self.controller.GetResources()

    def get_pipeline_state(self) -> Any:
        """Return current pipeline state."""
        return self.controller.GetPipelineState()

    def get_structured_file(self) -> Any:
        """Return structured file from the controller."""
        return self.controller.GetStructuredFile()

    def set_frame_event(self, eid: int, force: bool = True) -> None:
        """Move the replay to the given event ID."""
        self.controller.SetFrameEvent(eid, force)

    def shutdown(self) -> None:
        """Shutdown the replay controller."""
        self.controller.Shutdown()
