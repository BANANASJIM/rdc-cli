#!/usr/bin/env python3
"""Ensure .claude/skills/rdc-cli is a real directory link, not a git text stub.

Windows git stores symlinks as plain text files by default.
This script replaces that stub with a junction (Windows) or symlink (Unix).
Called by: pixi run sync
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    link = Path(".claude/skills/rdc-cli")
    target = Path("src/rdc/_skills")

    if link.is_dir():
        return

    if not target.is_dir():
        print(f"warning: skill target '{target}' not found, skipping", file=sys.stderr)
        return

    # Remove text-file stub left by git on Windows
    if link.exists() or link.is_symlink():
        link.unlink()

    link.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        # Absolute path required for junction
        subprocess.check_call(
            ["cmd", "/c", "mklink", "/J", str(link), str(target.resolve())],
            stdout=subprocess.DEVNULL,
        )
    else:
        os.symlink(Path("../../src/rdc/_skills"), link)

    print("linked .claude/skills/rdc-cli")


if __name__ == "__main__":
    main()
