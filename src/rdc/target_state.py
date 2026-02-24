"""TargetControl state persistence — save/load per-ident state files."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from rdc import _platform

log = logging.getLogger(__name__)


@dataclass
class TargetControlState:
    ident: int
    target_name: str
    pid: int
    api: str
    connected_at: float


def _state_path(ident: int) -> Path:
    return _platform.data_dir() / "target" / f"{ident}.json"


def save_target_state(state: TargetControlState) -> None:
    """Write target control state to disk with restricted permissions."""
    path = _state_path(state.ident)
    _platform.secure_dir_permissions(path.parent)
    _platform.secure_write_text(path, json.dumps(asdict(state), indent=2))


def load_target_state(ident: int) -> TargetControlState | None:
    """Load target control state by ident. Returns None on missing or corrupt."""
    path = _state_path(ident)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return TargetControlState(
            ident=int(data["ident"]),
            target_name=data["target_name"],
            pid=int(data["pid"]),
            api=data["api"],
            connected_at=float(data["connected_at"]),
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        log.warning("corrupt target state file deleted: %s", path)
        path.unlink(missing_ok=True)
        return None


def delete_target_state(ident: int) -> None:
    """Remove target state file if it exists."""
    _state_path(ident).unlink(missing_ok=True)


def load_latest_target_state() -> TargetControlState | None:
    """Load the most recently saved target state (by connected_at). Returns None if none exist."""
    target_dir = _platform.data_dir() / "target"
    if not target_dir.is_dir():
        return None
    best: TargetControlState | None = None
    for f in target_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            state = TargetControlState(
                ident=int(data["ident"]),
                target_name=data["target_name"],
                pid=int(data["pid"]),
                api=data["api"],
                connected_at=float(data["connected_at"]),
            )
            if best is None or state.connected_at > best.connected_at:
                best = state
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            continue
    return best
