"""Remote server state persistence."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from rdc import _platform

log = logging.getLogger(__name__)


@dataclass
class RemoteServerState:
    host: str
    port: int
    connected_at: float


def _sanitize_host(host: str) -> str:
    """Make host string safe for use in filenames (strips brackets, replaces colons)."""
    return host.replace(":", "-").replace("[", "").replace("]", "")


def _state_path(host: str, port: int) -> Path:
    return _platform.data_dir() / "remote" / f"{_sanitize_host(host)}_{port}.json"


def save_remote_state(state: RemoteServerState) -> None:
    """Write remote server state to disk with restricted permissions."""
    path = _state_path(state.host, state.port)
    _platform.secure_dir_permissions(path.parent)
    _platform.secure_write_text(path, json.dumps(asdict(state), indent=2))


def load_remote_state(host: str, port: int) -> RemoteServerState | None:
    """Load remote server state. Returns None on missing or corrupt."""
    path = _state_path(host, port)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return RemoteServerState(
            host=data["host"],
            port=int(data["port"]),
            connected_at=float(data["connected_at"]),
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        log.warning("corrupt remote state file deleted: %s", path)
        path.unlink(missing_ok=True)
        return None


def delete_remote_state(host: str, port: int) -> None:
    """Remove remote state file if it exists."""
    _state_path(host, port).unlink(missing_ok=True)


def load_latest_remote_state() -> RemoteServerState | None:
    """Load the most recently saved remote state (by connected_at)."""
    remote_dir = _platform.data_dir() / "remote"
    if not remote_dir.is_dir():
        return None
    best: RemoteServerState | None = None
    for f in remote_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            state = RemoteServerState(
                host=data["host"],
                port=int(data["port"]),
                connected_at=float(data["connected_at"]),
            )
            if best is None or state.connected_at > best.connected_at:
                best = state
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            continue
    return best
