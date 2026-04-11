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
from types import ModuleType
from typing import Any

import click

from rdc.discover import ProbeResult, _get_diagnostic, find_renderdoc, find_renderdoccmd


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
        return CheckResult("platform", True, "windows")
    return CheckResult("platform", False, f"unsupported platform: {sys.platform}")


def _make_build_hint(platform: str) -> str:  # noqa: ARG001
    """Return build instructions for renderdoc."""
    return (
        "  renderdoc is not available on PyPI and must be built from source.\n"
        "  Run: rdc setup-renderdoc\n"
        "  Full instructions: https://bananasjim.github.io/rdc-cli/docs/install/\n"
        "  Then re-run: rdc doctor"
    )


_RENDERDOC_BUILD_HINT = _make_build_hint(sys.platform)


def _import_renderdoc() -> tuple[Any | None, CheckResult]:
    module = find_renderdoc()
    if module is None:
        diag = _get_diagnostic()
        if diag is not None and diag.result == ProbeResult.CRASH_PRONE:
            return None, CheckResult(
                "renderdoc-module",
                False,
                f"incompatible at {diag.candidate_path} -- rebuild renderdoc for current Python",
            )
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


# -- Windows-specific checks -----------------------------------------------


def _check_win_python_version() -> CheckResult:
    """Verify the running Python matches the renderdoc .pyd build."""
    if sys.platform != "win32":
        return CheckResult("win-python-version", True, "n/a")

    from rdc import _platform

    search_paths = list(_platform.renderdoc_search_paths())
    env_path = os.environ.get("RENDERDOC_PYTHON_PATH")
    if env_path and env_path not in search_paths:
        search_paths.insert(0, env_path)

    # Try cpython-tagged .pyd first (setuptools output)
    pyds = [f for p in search_paths for f in glob.glob(str(Path(p) / "renderdoc.cpython-3*.pyd"))]
    if pyds:
        # Prefer the .pyd matching the running Python version
        running_tag = f"cpython-{sys.version_info[0]}{sys.version_info[1]}"
        matched = [p for p in pyds if running_tag in Path(p).stem]
        if matched:
            pyds = matched
        else:
            # Tagged .pyds exist but none match running Python -- fall through to plain .pyd
            pyds = []
    if not pyds:
        # Fall back to plain renderdoc.pyd (MSBuild output, no cpython tag)
        pyds = [
            str(Path(p) / "renderdoc.pyd")
            for p in search_paths
            if (Path(p) / "renderdoc.pyd").is_file()
        ]
        if pyds:
            return CheckResult(
                "win-python-version",
                True,
                f"MSBuild renderdoc.pyd found at {pyds[0]} (version check skipped)",
            )
        return CheckResult(
            "win-python-version",
            False,
            "renderdoc.pyd not found -- cannot verify Python version match",
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
                "vswhere.exe not found -- install Visual Studio 2022 Build Tools",
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
            "VC++ build tools not found -- required to build renderdoc Python bindings",
        )
    version = installs[0].get("installationVersion", "unknown")
    return CheckResult(
        "win-vs-build-tools", True, f"Visual Studio Build Tools found (version {version})"
    )


def _check_win_renderdoc_install() -> CheckResult:
    """Check for renderdoc.dll at known Windows install paths."""
    if sys.platform != "win32":
        return CheckResult("win-renderdoc-install", True, "n/a")

    from rdc import _platform

    candidates: list[Path] = []

    env_path = os.environ.get("RENDERDOC_PYTHON_PATH")
    if env_path:
        candidates.append(Path(env_path) / "renderdoc.dll")

    for search_dir in _platform.renderdoc_search_paths():
        candidates.append(Path(search_dir) / "renderdoc.dll")

    for p in candidates:
        if p.exists():
            return CheckResult("win-renderdoc-install", True, f"RenderDoc found at {p}")
    return CheckResult(
        "win-renderdoc-install",
        False,
        "RenderDoc not found -- install RenderDoc or set RENDERDOC_PYTHON_PATH",
    )


def _check_win_vulkan_layer() -> CheckResult:
    """Check Vulkan implicit layer JSON and registry for capture support."""
    if sys.platform != "win32":
        return CheckResult("win-vulkan-layer", True, "n/a")

    import winreg  # noqa: PLC0415

    # 1. Collect all renderdoc layer entries from registry
    reg_path = r"SOFTWARE\Khronos\Vulkan\ImplicitLayers"
    candidates: list[Path] = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, reg_path) as key:
                i = 0
                while True:
                    try:
                        name, _val, _typ = winreg.EnumValue(key, i)
                        if "renderdoc" in name.lower():
                            candidates.append(Path(name))
                    except OSError:
                        break
                    i += 1
        except OSError:
            continue

    if not candidates:
        return CheckResult(
            "win-vulkan-layer",
            False,
            "renderdoc not registered as Vulkan implicit layer"
            " -- register renderdoc.json in HKCU\\SOFTWARE\\Khronos\\Vulkan\\ImplicitLayers",
        )

    # 2. Find first candidate whose JSON file exists
    layer_json_path = next((p for p in candidates if p.is_file()), None)
    if layer_json_path is None:
        return CheckResult(
            "win-vulkan-layer",
            False,
            f"registry points to {candidates[0]} but file not found",
        )

    # 3. Validate layer JSON references renderdoc.dll that exists
    try:
        data = json.loads(layer_json_path.read_text(encoding="utf-8"))
        lib_path = data.get("layer", {}).get("library_path", "")
        if lib_path:
            dll = (layer_json_path.parent / lib_path).resolve()
            if not dll.is_file():
                return CheckResult(
                    "win-vulkan-layer",
                    False,
                    f"layer JSON references {lib_path} but {dll} not found",
                )
    except Exception:  # noqa: BLE001
        pass

    return CheckResult("win-vulkan-layer", True, f"registered at {layer_json_path}")


# -- Android checks --------------------------------------------------------


def _check_adb() -> CheckResult:
    path = shutil.which("adb")
    if path:
        return CheckResult("adb", True, f"found: {path}")
    return CheckResult("adb", True, "not found (run: pixi run setup-android)")


def _check_android_apk(rd_module: ModuleType | None) -> CheckResult:
    if rd_module is None or rd_module.__file__ is None:
        return CheckResult("android-apk", True, "skipped (renderdoc not installed)")
    lib_dir = Path(rd_module.__file__).resolve().parent
    apk_dir = (lib_dir / ".." / "share" / "renderdoc" / "plugins" / "android").resolve()
    apks = list(apk_dir.glob("*.apk"))
    if apks:
        return CheckResult("android-apk", True, f"{len(apks)} APK(s) at {apk_dir}")
    return CheckResult("android-apk", True, "not found (run: rdc setup-renderdoc --android)")


def _check_renderdoc_variant(rd_module: ModuleType | None) -> CheckResult:
    if rd_module is None:
        return CheckResult("renderdoc-variant", True, "skipped")
    version = getattr(rd_module, "GetVersionString", lambda: "unknown")()
    if re.match(r"^\d{4}\.", version):
        detail = f"arm-performance-studio ({version})"
    else:
        detail = f"upstream ({version})"
    return CheckResult("renderdoc-variant", True, detail)


# -- macOS-specific checks -------------------------------------------------


def _check_mac_xcode_cli() -> CheckResult:
    """Verify Xcode Command Line Tools are installed."""
    if sys.platform != "darwin":
        return CheckResult("mac-xcode-cli", True, "n/a")
    try:
        proc = subprocess.run(["xcode-select", "-p"], capture_output=True, text=True, timeout=3)
        if proc.returncode == 0:
            return CheckResult("mac-xcode-cli", True, proc.stdout.strip())
        return CheckResult("mac-xcode-cli", False, "not installed -- run: xcode-select --install")
    except Exception:  # noqa: BLE001
        return CheckResult("mac-xcode-cli", False, "not installed -- run: xcode-select --install")


def _check_mac_homebrew() -> CheckResult:
    """Check if Homebrew is available."""
    if sys.platform != "darwin":
        return CheckResult("mac-homebrew", True, "n/a")
    brew_path = shutil.which("brew")
    if not brew_path:
        for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
            if Path(candidate).is_file():
                brew_path = candidate
                break
    if not brew_path:
        return CheckResult(
            "mac-homebrew",
            False,
            "brew not found -- install from https://brew.sh",
        )
    try:
        proc = subprocess.run([brew_path, "--version"], capture_output=True, text=True, timeout=5)
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
            _check_win_vulkan_layer(),
        ]
    if sys.platform == "darwin":
        results += [
            _check_mac_xcode_cli(),
            _check_mac_homebrew(),
            _check_mac_renderdoc_dylib(),
        ]
    results += [
        _check_adb(),
        _check_android_apk(module),
        _check_renderdoc_variant(module),
    ]
    return results


HINT_MAP: dict[str, str] = {
    "replay-support": (
        "renderdoc replay API unavailable"
        " -- ensure renderdoc is installed with replay support enabled"
        " (see renderdoc-module check above for module load status)"
    ),
    "renderdoccmd": (
        "install renderdoccmd or add it to PATH;"
        " see https://bananasjim.github.io/rdc-cli/docs/install/"
    ),
    "platform": "rdc-cli capture requires Linux, macOS, or Windows",
    "win-python-version": (
        "rebuild renderdoc Python bindings against the running Python version,"
        " or switch Python to match the .pyd tag"
    ),
    "win-vs-build-tools": (
        "install Visual Studio 2022 Build Tools from https://visualstudio.microsoft.com/downloads/"
    ),
    "win-renderdoc-install": (
        "install RenderDoc from https://renderdoc.org/builds or set RENDERDOC_PYTHON_PATH"
    ),
    "win-vulkan-layer": (
        "re-install RenderDoc to restore the Vulkan implicit layer registry entry"
    ),
    "mac-xcode-cli": "run: xcode-select --install",
    "mac-homebrew": "install Homebrew from https://brew.sh",
    "mac-renderdoc-dylib": (
        "build renderdoc for macOS; see https://bananasjim.github.io/rdc-cli/docs/install/"
    ),
}


@click.command("doctor")
def doctor_cmd() -> None:
    """Run environment checks for rdc-cli."""
    results = run_doctor()
    has_error = False

    for result in results:
        icon = "[ok]" if result.ok else "[FAIL]"
        click.echo(f"{icon} {result.name}: {result.detail}")
        if not result.ok:
            has_error = True
            if result.name == "renderdoc-module":
                click.echo(f"  hint: {_RENDERDOC_BUILD_HINT}", err=True)
            else:
                hint = HINT_MAP.get(result.name)
                if hint:
                    click.echo(f"  hint: {hint}", err=True)

    if has_error:
        raise SystemExit(1)
