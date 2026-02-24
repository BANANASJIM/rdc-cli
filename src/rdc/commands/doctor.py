from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from rdc.discover import find_renderdoc, find_renderdoccmd


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_python() -> CheckResult:
    return CheckResult("python", True, sys.version.split()[0])


def _check_platform() -> CheckResult:
    if sys.platform == "linux":
        return CheckResult("platform", True, "linux")
    if sys.platform == "darwin":
        return CheckResult("platform", True, "darwin (dev-host only for replay)")
    if sys.platform == "win32":
        return CheckResult("platform", True, "windows (experimental)")
    return CheckResult("platform", False, f"unsupported platform: {sys.platform}")


def _make_build_hint(platform: str) -> str:
    """Return platform-specific build instructions for renderdoc."""
    if platform == "win32":
        return (
            "  renderdoc is not available on PyPI and must be built from source.\n"
            "  Build script: python scripts/build_renderdoc.py\n"
            "  Full instructions: https://bananasjim.github.io/rdc-cli/\n"
            "  Then re-run: rdc doctor"
        )
    if platform == "darwin":
        return (
            "  renderdoc is not available on PyPI and must be built from source.\n"
            "  Build prerequisites: brew install cmake ninja\n"
            "  Build script: python scripts/build_renderdoc.py\n"
            "  Full instructions: https://bananasjim.github.io/rdc-cli/\n"
            "  Then re-run: rdc doctor"
        )
    return (
        "  renderdoc is not available on PyPI and must be built from source.\n"
        "  Quick build script (no pixi required):\n"
        "    bash <(curl -fsSL"
        " https://raw.githubusercontent.com/BANANASJIM/rdc-cli/master/scripts/build-renderdoc.sh)\n"
        "  Full instructions: https://bananasjim.github.io/rdc-cli/\n"
        "  Then re-run: rdc doctor"
    )


_RENDERDOC_BUILD_HINT = _make_build_hint(sys.platform)


def _import_renderdoc() -> tuple[Any | None, CheckResult]:
    module = find_renderdoc()
    if module is None:
        return None, CheckResult("renderdoc-module", False, "not found in search paths")

    version = getattr(module, "GetVersionString", lambda: "unknown")()
    return module, CheckResult("renderdoc-module", True, f"version={version}")


def _check_replay_support(module: Any | None) -> CheckResult:
    if module is None:
        return CheckResult("replay-support", False, "renderdoc module unavailable")

    has_init = hasattr(module, "InitialiseReplay")
    has_shutdown = hasattr(module, "ShutdownReplay")
    has_global_env = hasattr(module, "GlobalEnvironment")

    if has_init and has_shutdown and has_global_env:
        return CheckResult("replay-support", True, "renderdoc replay API surface found")
    return CheckResult("replay-support", False, "missing replay API surface")


def _check_renderdoccmd() -> CheckResult:
    cmd_path = find_renderdoccmd()
    if cmd_path is None:
        return CheckResult("renderdoccmd", False, "not found in PATH or known paths")
    try:
        out = subprocess.run(
            [str(cmd_path), "--version"], capture_output=True, text=True, timeout=3
        )
        version = out.stdout.strip() or out.stderr.strip() or "unknown"
    except Exception:  # noqa: BLE001
        version = str(cmd_path)
    return CheckResult("renderdoccmd", True, f"{cmd_path} ({version})")


# ── Windows-specific checks ──────────────────────────────────────────


def _check_win_python_version() -> CheckResult:
    """Verify the running Python matches the renderdoc .pyd build."""
    if sys.platform != "win32":
        return CheckResult("win-python-version", True, "n/a")

    from rdc import _platform

    search_paths = _platform.renderdoc_search_paths()

    pyds = [f for p in search_paths for f in glob.glob(str(Path(p) / "renderdoc.cpython-3*.pyd"))]
    if not pyds:
        return CheckResult(
            "win-python-version",
            False,
            "renderdoc.pyd not found \u2014 cannot verify Python version match",
        )

    name = Path(pyds[0]).stem
    m = re.search(r"cpython-(\d)(\d+)", name)
    if not m:
        return CheckResult("win-python-version", False, f"cannot parse version from {name}")

    pyd_ver = (int(m.group(1)), int(m.group(2)))
    running = sys.version_info[:2]
    if running == pyd_ver:
        return CheckResult(
            "win-python-version", True, f"Python {running[0]}.{running[1]} matches renderdoc.pyd"
        )
    return CheckResult(
        "win-python-version",
        False,
        f"Python {running[0]}.{running[1]} running but pyd built for {pyd_ver[0]}.{pyd_ver[1]}",
    )


def _check_win_vs_build_tools() -> CheckResult:
    """Detect Visual Studio Build Tools via vswhere.exe."""
    if sys.platform != "win32":
        return CheckResult("win-vs-build-tools", True, "n/a")

    vswhere = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")
    if not vswhere.exists():
        found = shutil.which("vswhere")
        if not found:
            return CheckResult(
                "win-vs-build-tools",
                False,
                "vswhere.exe not found \u2014 install Visual Studio 2022 Build Tools",
            )
        vswhere = Path(found)

    try:
        proc = subprocess.run(
            [
                str(vswhere),
                "-latest",
                "-products",
                "*",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        installs: list[dict[str, Any]] = json.loads(proc.stdout or "[]")
    except subprocess.TimeoutExpired:
        return CheckResult("win-vs-build-tools", False, "vswhere.exe probe timed out")
    except Exception as exc:
        return CheckResult("win-vs-build-tools", False, f"vswhere.exe probe failed: {exc}")

    if not installs:
        return CheckResult(
            "win-vs-build-tools",
            False,
            "VC++ build tools not found \u2014 required to build renderdoc Python bindings",
        )
    version = installs[0].get("installationVersion", "unknown")
    return CheckResult(
        "win-vs-build-tools", True, f"Visual Studio Build Tools found (version {version})"
    )


def _check_win_renderdoc_install() -> CheckResult:
    """Check for renderdoc.dll at known Windows install paths."""
    if sys.platform != "win32":
        return CheckResult("win-renderdoc-install", True, "n/a")

    candidates: list[Path] = [
        Path(r"C:\Program Files\RenderDoc\renderdoc.dll"),
    ]
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        candidates.append(Path(localappdata) / "renderdoc" / "renderdoc.dll")
        candidates.append(Path(localappdata) / "RenderDoc" / "renderdoc.dll")

    env_path = os.environ.get("RENDERDOC_PYTHON_PATH")
    if env_path:
        candidates.insert(0, Path(env_path) / "renderdoc.dll")

    for p in candidates:
        if p.exists():
            return CheckResult("win-renderdoc-install", True, f"RenderDoc found at {p}")
    return CheckResult(
        "win-renderdoc-install",
        False,
        "RenderDoc not found \u2014 install RenderDoc or set RENDERDOC_PYTHON_PATH",
    )


# ── macOS-specific checks ─────────────────────────────────────────────


def _check_mac_xcode_cli() -> CheckResult:
    """Verify Xcode Command Line Tools are installed."""
    if sys.platform != "darwin":
        return CheckResult("mac-xcode-cli", True, "n/a")
    try:
        proc = subprocess.run(["xcode-select", "-p"], capture_output=True, text=True, timeout=3)
        if proc.returncode == 0:
            return CheckResult("mac-xcode-cli", True, proc.stdout.strip())
        return CheckResult("mac-xcode-cli", False, "not installed — run: xcode-select --install")
    except Exception:  # noqa: BLE001
        return CheckResult("mac-xcode-cli", False, "not installed — run: xcode-select --install")


def _check_mac_homebrew() -> CheckResult:
    """Check if Homebrew is available."""
    if sys.platform != "darwin":
        return CheckResult("mac-homebrew", True, "n/a")
    if not shutil.which("brew"):
        return CheckResult(
            "mac-homebrew",
            False,
            "brew not found — install from https://brew.sh",
        )
    try:
        proc = subprocess.run(["brew", "--version"], capture_output=True, text=True, timeout=5)
        if proc.returncode != 0:
            detail = proc.stderr.strip() or "brew --version failed"
            return CheckResult("mac-homebrew", False, detail)
        version = proc.stdout.strip().split("\n")[0] if proc.stdout else "unknown"
        return CheckResult("mac-homebrew", True, version)
    except Exception:  # noqa: BLE001
        return CheckResult("mac-homebrew", False, "brew found but version check failed")


def _check_mac_renderdoc_dylib() -> CheckResult:
    """Look for renderdoc shared library in platform search paths."""
    if sys.platform != "darwin":
        return CheckResult("mac-renderdoc-dylib", True, "n/a")

    from rdc import _platform

    for search_dir in _platform.renderdoc_search_paths():
        for name in ("renderdoc.so", "librenderdoc.dylib"):
            p = Path(search_dir) / name
            if p.exists():
                return CheckResult("mac-renderdoc-dylib", True, str(p))
    return CheckResult("mac-renderdoc-dylib", False, "renderdoc library not found in search paths")


def run_doctor() -> list[CheckResult]:
    """Run all environment checks and return results."""
    module, renderdoc_check = _import_renderdoc()
    results = [
        _check_python(),
        _check_platform(),
        renderdoc_check,
        _check_replay_support(module),
        _check_renderdoccmd(),
    ]
    if sys.platform == "win32":
        results += [
            _check_win_python_version(),
            _check_win_vs_build_tools(),
            _check_win_renderdoc_install(),
        ]
    if sys.platform == "darwin":
        results += [
            _check_mac_xcode_cli(),
            _check_mac_homebrew(),
            _check_mac_renderdoc_dylib(),
        ]
    return results


@click.command("doctor")
def doctor_cmd() -> None:
    """Run environment checks for rdc-cli."""
    results = run_doctor()
    has_error = False

    for result in results:
        icon = "\u2705" if result.ok else "\u274c"
        click.echo(f"{icon} {result.name}: {result.detail}")
        if not result.ok:
            has_error = True
            if result.name == "renderdoc-module":
                click.echo(_RENDERDOC_BUILD_HINT, err=True)

    if has_error:
        raise SystemExit(1)
