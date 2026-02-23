"""Renderdoc module discovery.

Searches for the renderdoc Python module in standard locations
and returns the imported module if found and ABI-compatible.
"""

from __future__ import annotations

import importlib
import logging
import os
import shutil
import sys
from pathlib import Path
from types import ModuleType

log = logging.getLogger(__name__)

_SYSTEM_PATHS = [
    "/usr/lib/renderdoc",
    "/usr/local/lib/renderdoc",
]


def find_renderdoc() -> ModuleType | None:
    """Discover and import the renderdoc module.

    Search order:
        1. ``RENDERDOC_PYTHON_PATH`` environment variable
        2. System paths (``/usr/lib/renderdoc``, ``/usr/local/lib/renderdoc``)
        3. Sibling directory of ``renderdoccmd`` on PATH
    """
    candidates: list[str] = []

    env_path = os.environ.get("RENDERDOC_PYTHON_PATH")
    if env_path:
        candidates.append(env_path)

    candidates.extend(_SYSTEM_PATHS)

    cmd = shutil.which("renderdoccmd")
    if cmd:
        candidates.append(str(Path(cmd).resolve().parent))

    # Try already-importable module first (e.g. site-packages)
    mod = _try_import()
    if mod is not None:
        return mod

    for path in candidates:
        if not Path(path).is_dir():
            continue
        mod = _try_import_from(path)
        if mod is not None:
            return mod

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
