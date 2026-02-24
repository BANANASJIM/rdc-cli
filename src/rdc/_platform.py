"""Platform abstraction layer for rdc-cli.

Centralises all OS-specific behaviour behind a single module so that
callers never need ``sys.platform`` checks themselves.
"""

from __future__ import annotations

import os
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_WIN: bool = sys.platform == "win32"


def data_dir() -> Path:
    """Return the per-user data directory for rdc."""
    if _WIN:
        base = os.environ.get("LOCALAPPDATA", str(Path.home()))
        return Path(base) / "rdc"
    return Path.home() / ".rdc"


def terminate_process(pid: int) -> bool:
    """Send SIGTERM (Unix) to *pid*. Returns True if the signal was sent."""
    if _WIN:  # pragma: no cover
        raise NotImplementedError("Windows support — Phase W2")
    if pid <= 0:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def is_pid_alive(pid: int, *, tag: str = "rdc") -> bool:
    """Check whether *pid* is alive and its cmdline contains *tag*."""
    if _WIN:  # pragma: no cover
        raise NotImplementedError("Windows support — Phase W2")
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        if tag.encode() not in cmdline:
            return False
    except OSError:
        pass  # non-Linux or permission denied — accept kill-only result
    return True


def install_shutdown_signal(handler: Callable[[], None] | None = None) -> None:
    """Register a SIGTERM handler for graceful daemon shutdown."""
    if _WIN:  # pragma: no cover
        raise NotImplementedError("Windows support — Phase W2")

    def _handler(*_: object) -> None:
        if handler is not None:
            handler()
        else:
            sys.exit(0)

    signal.signal(signal.SIGTERM, _handler)


def secure_write_text(path: Path, content: str) -> None:
    """Write *content* to *path* with 0o600 permissions.

    Creates new files with restricted mode atomically; also fixes
    permissions on pre-existing files.
    """
    if _WIN:  # pragma: no cover
        path.write_text(content)
        return
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(content)
    path.chmod(0o600)


def secure_permissions(path: Path) -> None:
    """Set *path* to owner-only read/write (0o600)."""
    if _WIN:  # pragma: no cover
        return
    path.chmod(0o600)


def secure_dir_permissions(path: Path) -> None:
    """Ensure *path* exists as a directory with restricted permissions."""
    path.mkdir(parents=True, exist_ok=True)
    if not _WIN:
        path.chmod(0o700)


def popen_flags() -> dict[str, Any]:
    """Return extra kwargs for subprocess.Popen on this platform."""
    if _WIN:  # pragma: no cover
        raise NotImplementedError("Windows support — Phase W2")
    return {}


def renderdoc_search_paths() -> list[str]:
    """Return system directories to search for the renderdoc Python module."""
    if _WIN:  # pragma: no cover
        raise NotImplementedError("Windows support — Phase W2")
    return ["/usr/lib/renderdoc", "/usr/local/lib/renderdoc"]


def renderdoccmd_search_paths() -> list[Path]:
    """Return candidate paths for the renderdoccmd binary."""
    if _WIN:  # pragma: no cover
        raise NotImplementedError("Windows support — Phase W2")
    return [Path("/opt/renderdoc/bin/renderdoccmd"), Path("/usr/local/bin/renderdoccmd")]
