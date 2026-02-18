from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


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
    return Path.home() / ".rdc" / "sessions"


def session_path() -> Path:
    return _session_dir() / "default.json"


def load_session() -> SessionState | None:
    path = session_path()
    if not path.exists():
        return None
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


def save_session(state: SessionState) -> None:
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2))


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
