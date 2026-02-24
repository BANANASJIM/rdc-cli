#!/usr/bin/env python3
"""Cross-platform RenderDoc Python bindings build script.

Replaces build-renderdoc.sh and setup-renderdoc.sh.
Standalone -- requires only Python 3.10+ stdlib.

Usage:
    python scripts/build_renderdoc.py [INSTALL_DIR] [--build-dir DIR] [--jobs N]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

RDOC_TAG = "v1.41"
RDOC_REPO = "https://github.com/baldurk/renderdoc.git"
SWIG_URL = "https://github.com/baldurk/swig/archive/renderdoc-modified-7.zip"
SWIG_SHA256 = "9d7e5013ada6c42ec95ab167a34db52c1cc8c09b89c8e9373631b1f10596c648"
SWIG_SUBDIR = "swig-renderdoc-modified-7"

CMAKE_COMMON_FLAGS = [
    "-DCMAKE_BUILD_TYPE=Release",
    "-DENABLE_PYRENDERDOC=ON",
    "-DENABLE_QRENDERDOC=OFF",
    "-DENABLE_RENDERDOCCMD=OFF",
    "-DENABLE_GL=OFF",
    "-DENABLE_GLES=OFF",
    "-DENABLE_VULKAN=ON",
]


def _log(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _platform() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def default_install_dir() -> Path:
    """Default renderdoc artifact directory (~/.local/renderdoc or %LOCALAPPDATA%\\rdc\\renderdoc)."""
    if _platform() == "windows":
        base = os.environ.get("LOCALAPPDATA", str(Path.home()))
        return Path(base) / "rdc" / "renderdoc"
    return Path.home() / ".local" / "renderdoc"


def _artifact_names(plat: str) -> list[str]:
    if plat == "windows":
        return ["renderdoc.pyd", "renderdoc.dll"]
    return ["renderdoc.so", "librenderdoc.so"]


def _artifact_src_dir(build_dir: Path, plat: str) -> Path:
    if plat == "windows":
        return build_dir / "renderdoc" / "build" / "Release"
    return build_dir / "renderdoc" / "build" / "lib"


def check_prerequisites(plat: str) -> None:
    """Verify required build tools are available."""
    common = ["cmake", "git"]
    if plat == "windows":
        required = [*common]
    else:
        required = [*common, "ninja"]

    missing = [cmd for cmd in required if shutil.which(cmd) is None]

    # Check python3 or python
    if shutil.which("python3") is None and shutil.which("python") is None:
        missing.append("python3")

    if missing:
        sys.stderr.write(f"ERROR: missing required tools: {', '.join(missing)}\n")
        raise SystemExit(1)

    if plat == "windows":
        _check_visual_studio()


def _check_visual_studio() -> None:
    vswhere = shutil.which("vswhere") or shutil.which("vswhere.exe")
    if not vswhere:
        # Try default install location
        prog = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        candidate = prog / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        if candidate.exists():
            vswhere = str(candidate)
        else:
            sys.stderr.write("ERROR: vswhere.exe not found; install Visual Studio Build Tools\n")
            raise SystemExit(1)

    result = subprocess.run(
        [
            vswhere,
            "-products", "*",
            "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-format", "value",
            "-property", "installationPath",
        ],
        capture_output=True,
        text=True,
    )
    if not result.stdout.strip():
        sys.stderr.write("ERROR: Visual Studio C++ Build Tools not found\n")
        raise SystemExit(1)


def clone_renderdoc(build_dir: Path, version: str = RDOC_TAG) -> None:
    """Clone renderdoc source (idempotent)."""
    src_dir = build_dir / "renderdoc"
    if src_dir.exists():
        _log(f"renderdoc source already exists at {src_dir}")
        return
    _log(f"--- Cloning renderdoc {version} ---")
    build_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", version, RDOC_REPO, str(src_dir)],
        check=True,
    )


def _safe_extractall(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract zip archive while rejecting members that would escape dest (zip-slip mitigation)."""
    dest_resolved = dest.resolve()
    for member in zf.infolist():
        target = (dest / member.filename).resolve()
        if not target.is_relative_to(dest_resolved):
            sys.stderr.write(f"ERROR: zip-slip attempt detected: {member.filename}\n")
            raise SystemExit(1)
        zf.extract(member, dest)


def download_swig(build_dir: Path) -> None:
    """Download and extract the RenderDoc SWIG fork (idempotent)."""
    swig_dir = build_dir / "renderdoc-swig"
    if swig_dir.exists():
        _log(f"SWIG fork already exists at {swig_dir}")
        return

    build_dir.mkdir(parents=True, exist_ok=True)
    archive = build_dir / "swig.zip"

    _log("--- Downloading SWIG fork ---")
    urlretrieve(SWIG_URL, str(archive))

    # SHA256 verification
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    if sha != SWIG_SHA256:
        archive.unlink()
        sys.stderr.write(f"ERROR: SWIG archive SHA256 mismatch: {sha}\n")
        raise SystemExit(1)

    try:
        with zipfile.ZipFile(archive) as zf:
            _safe_extractall(zf, build_dir)
        (build_dir / SWIG_SUBDIR).rename(swig_dir)
    except Exception:
        # Clean up partial extraction so next run retries cleanly
        shutil.rmtree(build_dir / SWIG_SUBDIR, ignore_errors=True)
        shutil.rmtree(swig_dir, ignore_errors=True)
        raise
    finally:
        archive.unlink(missing_ok=True)


def strip_lto(env: dict[str, str]) -> dict[str, str]:
    """Remove -flto=auto from compiler/linker flags (unconditional on Linux)."""
    env = dict(env)
    for key in ("CFLAGS", "CXXFLAGS", "LDFLAGS"):
        if key in env:
            env[key] = env[key].replace("-flto=auto", "").strip()
    return env


def configure_build(
    build_dir: Path,
    swig_dir: Path,
    plat: str,
) -> None:
    """Run cmake configure with platform-specific generator."""
    src_dir = build_dir / "renderdoc"
    cmake_build = src_dir / "build"

    cmd = ["cmake", "-B", str(cmake_build), "-S", str(src_dir)]

    if plat == "windows":
        cmd += ["-G", "Visual Studio 17 2022", "-A", "x64"]
    else:
        cmd += ["-G", "Ninja"]

    cmd += CMAKE_COMMON_FLAGS
    cmd.append(f"-DRENDERDOC_SWIG_PACKAGE={swig_dir}")

    env = dict(os.environ)
    if plat == "linux":
        _log("stripping LTO flags")
        env = strip_lto(env)

    _log("--- cmake configure ---")
    subprocess.run(cmd, check=True, env=env)


def run_build(build_dir: Path, plat: str, jobs: int | None = None) -> None:
    """Run cmake --build with platform-specific parallelism."""
    cmake_build = build_dir / "renderdoc" / "build"
    n = jobs or os.cpu_count() or 4

    cmd = ["cmake", "--build", str(cmake_build)]

    if plat == "windows":
        cmd += ["--config", "Release", "--", f"/m:{n}"]
    else:
        cmd += ["-j", str(n)]

    _log("--- cmake build ---")
    subprocess.run(cmd, check=True)


def copy_artifacts(build_dir: Path, install_dir: Path, plat: str) -> None:
    """Copy built artifacts to install directory."""
    src = _artifact_src_dir(build_dir, plat)
    names = _artifact_names(plat)
    install_dir.mkdir(parents=True, exist_ok=True)

    for name in names:
        artifact = src / name
        if not artifact.exists():
            # macOS may produce .dylib instead of .so for librenderdoc
            if plat == "macos" and name == "librenderdoc.so":
                alt = src / "librenderdoc.dylib"
                if alt.exists():
                    artifact = alt
                else:
                    sys.stderr.write(f"ERROR: artifact not found: {artifact} (also tried .dylib)\n")
                    raise SystemExit(1)
            else:
                sys.stderr.write(f"ERROR: artifact not found: {artifact}\n")
                raise SystemExit(1)
        shutil.copy2(artifact, install_dir / name)
        # Preserve original .dylib name for @rpath resolution on macOS
        if plat == "macos" and artifact.suffix == ".dylib" and name.endswith(".so"):
            shutil.copy2(artifact, install_dir / artifact.name)
    _log(f"artifacts copied to {install_dir}")


def _artifacts_present(install_dir: Path, plat: str) -> bool:
    return all((install_dir / n).exists() for n in _artifact_names(plat))


def main(argv: list[str] | None = None) -> None:
    """Entry point: parse args and orchestrate the build."""
    parser = argparse.ArgumentParser(description="Build RenderDoc Python bindings from source.")
    parser.add_argument("install_dir", nargs="?", default=None, help="Installation directory")
    parser.add_argument("--build-dir", default=None, help="Build cache directory")
    parser.add_argument("--version", default=RDOC_TAG, help="RenderDoc tag to build")
    parser.add_argument("--jobs", type=int, default=None, help="Parallel build jobs")
    args = parser.parse_args(argv)

    plat = _platform()
    install_dir = Path(args.install_dir) if args.install_dir else default_install_dir()
    build_dir = Path(args.build_dir) if args.build_dir else install_dir.parent / "renderdoc-build"

    if _artifacts_present(install_dir, plat):
        _log(f"renderdoc already exists at {install_dir}/")
        _log(f"To rebuild: rm -rf {install_dir} {build_dir} && re-run this script")
        return

    _log(f"=== Building renderdoc {args.version} Python module ===")
    check_prerequisites(plat)
    clone_renderdoc(build_dir, args.version)
    download_swig(build_dir)
    configure_build(build_dir, build_dir / "renderdoc-swig", plat)
    run_build(build_dir, plat, args.jobs)
    copy_artifacts(build_dir, install_dir, plat)
    _log("=== Done ===")
    _log(f'  export RENDERDOC_PYTHON_PATH="{install_dir}"')
    _log("  rdc doctor   # verify installation")


if __name__ == "__main__":
    main()
