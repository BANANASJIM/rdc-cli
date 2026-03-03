#!/usr/bin/env python3
"""Auto-link .local/renderdoc from main worktree into current worktree.

Cross-platform replacement for ensure-renderdoc.sh.
Called by: pixi run sync
No-op if .local/renderdoc already exists or we're in the main worktree.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    target = Path(".local/renderdoc")
    if target.exists() or target.is_symlink():
        return

    try:
        out = subprocess.check_output(
            ["git", "worktree", "list", "--porcelain"],
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return

    lines = out.strip().splitlines()
    if not lines or not lines[0].startswith("worktree "):
        return

    main_wt = Path(lines[0].removeprefix("worktree ").strip())
    if main_wt.resolve() == Path.cwd().resolve():
        return

    source = main_wt / ".local" / "renderdoc"
    if not source.exists():
        return

    target.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        # Use directory junction on Windows (no admin required)
        subprocess.check_call(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        os.symlink(source, target)

    print("linked .local/renderdoc")


if __name__ == "__main__":
    main()
