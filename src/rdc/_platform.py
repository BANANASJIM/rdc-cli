"""Platform abstraction layer for rdc-cli.

Centralises all OS-specific behaviour behind a single module so that
callers never need ``sys.platform`` checks themselves.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_WIN: bool = sys.platform in ("win32", "windows")
_MAC: bool = sys.platform == "darwin"


def data_dir() -> Path:
    """Return the per-user data directory for rdc."""
    if _WIN:
        base = os.environ.get("LOCALAPPDATA", str(Path.home()))
        return Path(base) / "rdc"
    return Path.home() / ".rdc"


def terminate_process(pid: int) -> bool:
    """Send SIGTERM (Unix) or TerminateProcess (Windows) to *pid*."""
    if pid <= 0:
        return False
    if _WIN:  # pragma: no cover
        # Windows: TerminateProcess is a hard kill (no graceful shutdown).
        # GenerateConsoleCtrlEvent requires same console group. Acceptable for now.
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined,unused-ignore]
        handle = kernel32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
        if not handle:
            return False
        try:
            return bool(kernel32.TerminateProcess(handle, 1))
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def terminate_process_tree(pid: int) -> bool:
    """Kill a process and all its children (Windows: taskkill /T, Unix: SIGTERM).

    On Windows, .venv trampoline scripts spawn a child python process.
    DETACHED_PROCESS prevents kill cascading, so we use taskkill /F /T
    to terminate the entire process tree.
    """
    if pid <= 0:
        return False
    if _WIN:  # pragma: no cover
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return terminate_process(pid)
    return terminate_process(pid)


def is_pid_alive(pid: int, *, tag: str = "rdc") -> bool:
    """Check whether *pid* is alive and its cmdline contains *tag*."""
    if pid <= 0:
        return False
    if _WIN:  # pragma: no cover
        # TODO(W-next): check process name against tag on Windows
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined,unused-ignore]
        handle = kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if _MAC:
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0 and tag not in result.stdout:
                return False
        except subprocess.SubprocessError:
            pass
    else:
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
            if tag.encode() not in cmdline:
                return False
        except OSError:
            pass
    return True


def install_shutdown_signal(handler: Callable[[], None] | None = None) -> None:
    """Register a signal handler for graceful daemon shutdown."""

    def _handler(*_: object) -> None:
        if handler is not None:
            handler()
        else:
            sys.exit(0)

    if _WIN:  # pragma: no cover
        signal.signal(signal.SIGBREAK, _handler)  # type: ignore[attr-defined,unused-ignore]
    else:
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
        # DETACHED_PROCESS (0x8): detach from parent console
        # CREATE_NEW_PROCESS_GROUP (0x200): isolate signal handling
        # CREATE_BREAKAWAY_FROM_JOB (0x01000000): escape sshd job object
        return {"creationflags": 0x00000008 | 0x00000200 | 0x01000000}
    return {}


def find_pid_by_port(port: int) -> int:
    """Return the PID listening on *port*, or 0 if not found."""
    if not _WIN:
        return 0
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            # Match: TCP  127.0.0.1:PORT  0.0.0.0:0  LISTENING  PID
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                return int(parts[-1])
    except Exception:  # noqa: BLE001
        pass
    return 0


def renderdoc_search_paths() -> list[str]:
    """Return system directories to search for the renderdoc Python module."""
    if _WIN:  # pragma: no cover
        paths = [r"C:\Program Files\RenderDoc"]
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if localappdata:
            paths.append(str(Path(localappdata) / "renderdoc"))
            paths.append(str(Path(localappdata) / "rdc" / "renderdoc"))
        return paths
    if _MAC:
        return [
            "/opt/homebrew/opt/renderdoc/lib",
            "/usr/local/opt/renderdoc/lib",
            str(Path.home() / ".local" / "renderdoc"),
            "/usr/lib/renderdoc",
            "/usr/local/lib/renderdoc",
        ]
    return ["/usr/lib/renderdoc", "/usr/local/lib/renderdoc"]


def renderdoccmd_search_paths() -> list[Path]:
    """Return candidate paths for the renderdoccmd binary."""
    if _WIN:  # pragma: no cover
        paths = [Path(r"C:\Program Files\RenderDoc\renderdoccmd.exe")]
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if localappdata:
            paths.append(Path(localappdata) / "rdc" / "renderdoc" / "renderdoccmd.exe")
        userprofile = os.environ.get("USERPROFILE", "")
        if userprofile:
            paths.append(
                Path(userprofile) / "scoop" / "apps" / "renderdoc" / "current" / "renderdoccmd.exe"
            )
        return paths
    if _MAC:
        return [
            Path("/opt/homebrew/bin/renderdoccmd"),
            Path("/opt/renderdoc/bin/renderdoccmd"),
            Path("/usr/local/bin/renderdoccmd"),
            Path.home() / ".local" / "renderdoc" / "renderdoccmd",
        ]
    return [
        Path("/opt/renderdoc/bin/renderdoccmd"),
        Path("/usr/local/bin/renderdoccmd"),
        Path.home() / ".local" / "renderdoc" / "renderdoccmd",
    ]
