#!/usr/bin/env python3
"""Cross-platform Vulkan-Samples clone+build script.

Replaces setup-vulkan-samples.sh. Clones KhronosGroup/Vulkan-Samples into
.local/vulkan-samples/src, builds the vulkan_samples binary, and creates a
symlink/junction at .local/vulkan-samples/vulkan_samples.

Idempotent: exits early if the binary already exists.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/KhronosGroup/Vulkan-Samples.git"
TARGET = Path(".local/vulkan-samples")

_IS_WINDOWS = sys.platform == "win32"
_BIN_NAME = "vulkan_samples.exe" if _IS_WINDOWS else "vulkan_samples"


def _log(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _binary_exists(target: Path) -> bool:
    link = target / _BIN_NAME
    return link.exists() and (link.stat().st_size > 0 if not link.is_symlink() else True)


def _clone(src_dir: Path) -> None:
    if src_dir.exists():
        _log(f"source already exists at {src_dir}, skipping clone")
        return
    _log("Cloning Vulkan-Samples...")
    src_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(src_dir)],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"ERROR: git clone failed (exit {exc.returncode})\n")
        raise SystemExit(1) from exc


def _build(src_dir: Path) -> None:
    _log("Building Vulkan-Samples...")
    jobs = str(os.cpu_count() or 4)
    try:
        subprocess.run(
            ["cmake", "-B", "build", "-DCMAKE_BUILD_TYPE=Release"],
            cwd=src_dir,
            check=True,
        )
        build_cmd = ["cmake", "--build", "build", "--parallel", jobs, "--target", "vulkan_samples"]
        if _IS_WINDOWS:
            build_cmd += ["--config", "Release"]
        subprocess.run(build_cmd, cwd=src_dir, check=True)
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"ERROR: cmake build failed (exit {exc.returncode})\n")
        raise SystemExit(1) from exc


def _find_binary(src_dir: Path) -> Path:
    # Windows Release config places binary under app/bin/Release/
    for candidate in (
        src_dir / "build" / "app" / "bin" / "Release" / _BIN_NAME,
        src_dir / "build" / "app" / "bin" / _BIN_NAME,
    ):
        if candidate.exists():
            return candidate
    sys.stderr.write(f"ERROR: built binary not found under {src_dir / 'build'}\n")
    raise SystemExit(1)


def _link(binary: Path, target: Path) -> None:
    link = target / _BIN_NAME
    if link.exists() or link.is_symlink():
        link.unlink()

    if _IS_WINDOWS:
        shutil.copy2(binary, link)
    else:
        # Relative symlink from target dir to binary
        rel = os.path.relpath(binary, target)
        os.symlink(rel, link)


def main() -> None:
    """Clone, build, and link Vulkan-Samples; skip if binary already present.

    The binary is placed at .local/vulkan-samples/vulkan_samples (Unix) or
    .local/vulkan-samples/vulkan_samples.exe (Windows) via symlink/junction.
    All paths are resolved relative to the current working directory, which
    should be the repository root.
    """
    if _binary_exists(TARGET):
        _log(f"vulkan_samples already built at {TARGET / _BIN_NAME}")
        return

    src_dir = TARGET / "src"
    _clone(src_dir)
    _build(src_dir)
    binary = _find_binary(src_dir)
    _link(binary, TARGET)
    _log(f"Done: {TARGET / _BIN_NAME}")


if __name__ == "__main__":
    main()
