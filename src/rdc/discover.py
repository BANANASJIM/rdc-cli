"""Renderdoc module discovery.

Searches for the renderdoc Python module in standard locations
and returns the imported module if found and ABI-compatible.
"""

from __future__ import annotations

import importlib
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType

from rdc import _platform

log = logging.getLogger(__name__)


class ProbeResult(Enum):
    SUCCESS = "success"
    IMPORT_FAILED = "import-failed"
    CRASH_PRONE = "crash-prone"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class ProbeOutcome:
    result: ProbeResult
    candidate_path: str
    version: str | None = None


_diagnostic: ProbeOutcome | None = None


def _get_diagnostic() -> ProbeOutcome | None:
    """Return diagnostic data from last find_renderdoc() call."""
    return _diagnostic


def _probe_candidate(directory: str, timeout: float = 5.0) -> ProbeOutcome:
    """Probe a candidate directory using a subprocess to safely test import.

    Returns:
        ProbeOutcome with classification and version if available.
    """
    probe_code = f"""
import sys
sys.path.insert(0, {directory!r})
try:
    import renderdoc
    ver = getattr(renderdoc, 'GetVersionString', lambda: None)()
    print(ver if ver else '')
    sys.exit(0)
except SystemExit:
    raise
except Exception as e:
    sys.exit(1)
"""

    try:
        result = subprocess.run(
            [sys.executable, "-c", probe_code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ProbeOutcome(ProbeResult.TIMEOUT, directory)
    except OSError:
        return ProbeOutcome(ProbeResult.IMPORT_FAILED, directory)

    rc = result.returncode
    if rc == 0:
        version = result.stdout.strip() or None
        return ProbeOutcome(ProbeResult.SUCCESS, directory, version)
    if rc < 0:
        return ProbeOutcome(ProbeResult.CRASH_PRONE, directory)
    return ProbeOutcome(ProbeResult.IMPORT_FAILED, directory)


def find_renderdoc() -> ModuleType | None:
    """Discover and import the renderdoc module.

    Search order:
        1. ``RENDERDOC_PYTHON_PATH`` environment variable
        2. System paths (``/usr/lib/renderdoc``, ``/usr/local/lib/renderdoc``)
        3. Sibling directory of ``renderdoccmd`` on PATH
    """
    global _diagnostic  # noqa: PLW0603
    _diagnostic = None
    candidates: list[str] = []

    env_path = os.environ.get("RENDERDOC_PYTHON_PATH")
    if env_path:
        candidates.append(env_path)

    try:
        candidates.extend(_platform.renderdoc_search_paths())
    except NotImplementedError:
        pass

    cmd = shutil.which("renderdoccmd")
    if cmd:
        candidates.append(str(Path(cmd).resolve().parent))

    # Try already-importable module first (e.g. site-packages)
    mod = _try_import()
    if mod is not None:
        _diagnostic = None
        return mod

    crash_prone_candidates: list[str] = []

    for path in candidates:
        if not Path(path).is_dir():
            continue

        outcome = _probe_candidate(path)

        if outcome.result == ProbeResult.SUCCESS:
            mod = _try_import_from(path)
            if mod is not None:
                _diagnostic = outcome
                return mod

        if outcome.result == ProbeResult.CRASH_PRONE:
            crash_prone_candidates.append(path)
            _diagnostic = outcome
        elif outcome.result == ProbeResult.TIMEOUT:
            _diagnostic = outcome

    if crash_prone_candidates:
        _diagnostic = ProbeOutcome(
            ProbeResult.CRASH_PRONE,
            crash_prone_candidates[0],
        )

    return None


def find_renderdoccmd() -> Path | None:
    """Discover the renderdoccmd binary.

    Search order:
        1. ``shutil.which("renderdoccmd")`` -- PATH
        2. ``_platform.renderdoccmd_search_paths()`` -- platform candidates
        3. Sibling of ``RENDERDOC_PYTHON_PATH`` (same dir, adjusted name)

    Returns:
        Absolute Path if found, else None.
    """
    which_result = shutil.which("renderdoccmd")
    if which_result:
        return Path(which_result)

    for p in _platform.renderdoccmd_search_paths():
        if p.exists():
            return p

    env_path = os.environ.get("RENDERDOC_PYTHON_PATH")
    if env_path:
        name = "renderdoccmd.exe" if sys.platform == "win32" else "renderdoccmd"
        candidate = Path(env_path) / name
        if candidate.exists():
            return candidate

    return None


def _try_import() -> ModuleType | None:
    """Try bare import without path manipulation."""
    try:
        return importlib.import_module("renderdoc")
    except Exception:  # noqa: BLE001
        return None


def _try_import_from(directory: str) -> ModuleType | None:
    """Add *directory* to sys.path, attempt import, clean up on failure.

    On success the directory stays in sys.path so that subsequent
    ``import renderdoc`` calls succeed.  On failure it is removed.
    """
    if directory in sys.path:
        return _try_import()

    sys.path.append(directory)
    try:
        mod = importlib.import_module("renderdoc")
    except Exception:  # noqa: BLE001
        sys.path.remove(directory)
        return None
    log.debug("renderdoc found at %s", directory)
    return mod
