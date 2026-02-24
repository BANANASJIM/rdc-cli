from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from rdc import _platform
from rdc._platform import is_pid_alive as is_pid_alive

SESSION_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@dataclass
class SessionState:
    capture: str
    current_eid: int
    opened_at: str
    host: str
    port: int
    token: str
    pid: int


def _session_dir() -> Path:
    return _platform.data_dir() / "sessions"


def session_path() -> Path:
    """Return the session file path, derived from RDC_SESSION env var."""
    name = os.environ.get("RDC_SESSION") or "default"
    if not SESSION_NAME_RE.match(name):
        name = "default"
    return _session_dir() / f"{name}.json"


def load_session() -> SessionState | None:
    path = session_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return SessionState(
            capture=data["capture"],
            current_eid=int(data["current_eid"]),
            opened_at=data["opened_at"],
            host=data["host"],
            port=int(data["port"]),
            token=data["token"],
            pid=int(data["pid"]),
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        import logging

        logging.getLogger("rdc").warning("corrupt session file deleted: %s", path)
        path.unlink(missing_ok=True)
        return None


def save_session(state: SessionState) -> None:
    """Write session state to disk with restricted permissions."""
    path = session_path()
    _platform.secure_dir_permissions(path.parent)
    _platform.secure_write_text(path, json.dumps(asdict(state), indent=2))


def create_session(
    capture: str,
    host: str,
    port: int,
    token: str,
    pid: int,
) -> SessionState:
    state = SessionState(
        capture=capture,
        current_eid=0,
        opened_at=datetime.now(timezone.utc).isoformat(),
        host=host,
        port=port,
        token=token,
        pid=pid,
    )
    save_session(state)
    return state


def delete_session() -> bool:
    path = session_path()
    if not path.exists():
        return False
    path.unlink()
    return True
