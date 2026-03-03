#!/usr/bin/env python3
"""Packaging verification script — runs locally before release.

Usage: python scripts/verify_package.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
USE_COLOR = sys.platform != "win32"

PASS_COUNT = 0
FAIL_COUNT = 0


def _prefix(ok: bool) -> str:
    if USE_COLOR:
        return f"\033[0;3{'2' if ok else '1'}m{'[ok]' if ok else '[FAIL]'}\033[0m"
    return "[ok]" if ok else "[FAIL]"


def _log(ok: bool, desc: str, detail: str = "") -> None:
    suffix = f" ({detail})" if detail else ""
    print(f"  {_prefix(ok)} {desc}{suffix}")


def _record(ok: bool) -> None:
    global PASS_COUNT, FAIL_COUNT
    if ok:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1


def check(desc: str, cmd: list[str]) -> bool:
    """Run cmd silently; record pass/fail."""
    ok = subprocess.run(cmd, capture_output=True, cwd=ROOT).returncode == 0
    _log(ok, desc)
    _record(ok)
    return ok


def check_output(desc: str, expected: str, cmd: list[str]) -> bool:
    """Run cmd; check that output contains expected string."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    ok = expected in (result.stdout + result.stderr)
    _log(ok, desc, "" if ok else f"expected '{expected}'")
    _record(ok)
    return ok


def main() -> None:
    """Run all verification layers and exit non-zero if any check fails.

    Layers:
        0 — Code quality (lint, format, type check, unit tests)
        1 — Build validation (uv build, twine check, artifact existence)
        2 — Install and smoke test (clean venv, CLI invocations)
        3 — Version consistency (installed package vs __init__ version)
    """
    print("=== Layer 0: Code quality ===")
    check("ruff check", ["uv", "run", "ruff", "check", "src", "tests"])
    check("ruff format", ["uv", "run", "ruff", "format", "--check", "src", "tests"])
    check("mypy", ["uv", "run", "mypy", "src"])
    check("pytest (unit)", ["uv", "run", "pytest", "tests/unit", "-q", "--cov=rdc", "--cov-fail-under=80"])

    print()
    print("=== Layer 1: Build validation ===")
    dist = ROOT / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    check("uv build", ["uv", "build"])
    check("twine check", ["uvx", "twine", "check"] + [str(p) for p in dist.glob("*")])
    check("wheel contents", ["uvx", "check-wheel-contents"] + [str(p) for p in dist.glob("*.whl")])

    sdist_ok = any(dist.glob("*.tar.gz"))
    _log(sdist_ok, "sdist exists")
    _record(sdist_ok)

    wheel_ok = any(dist.glob("*.whl"))
    _log(wheel_ok, "wheel exists")
    _record(wheel_ok)

    print()
    print("=== Layer 2: Install + smoke test ===")
    wheels = list(dist.glob("*.whl"))
    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp) / "venv"
        subprocess.run(["uv", "venv", str(venv)], capture_output=True, cwd=ROOT)
        if sys.platform == "win32":
            python = venv / "Scripts" / "python.exe"
            rdc = venv / "Scripts" / "rdc.exe"
        else:
            python = venv / "bin" / "python"
            rdc = venv / "bin" / "rdc"

        if wheels:
            check("clean venv install", ["uv", "pip", "install", str(wheels[0]), "--python", str(python)])
        else:
            _log(False, "clean venv install (no wheel found)")
            _record(False)

        ver_result = subprocess.run([str(rdc), "--version"], capture_output=True, text=True)
        installed_version = (
            (ver_result.stdout + ver_result.stderr).strip().split()[-1]
            if ver_result.returncode == 0
            else ""
        )

        check_output("rdc --version", installed_version, [str(rdc), "--version"])
        check("rdc --help", [str(rdc), "--help"])
        check("import rdc.cli", [str(python), "-c", "from rdc.cli import main"])
        check("import rdc.daemon_server", [str(python), "-c", "from rdc.daemon_server import _handle_request"])
        check("rdc completion bash", [str(rdc), "completion", "bash"])
        check("rdc completion zsh", [str(rdc), "completion", "zsh"])
        check("rdc completion fish", [str(rdc), "completion", "fish"])

        print()
        print("=== Layer 3: Version consistency ===")
        init_ver_result = subprocess.run(
            [str(python), "-c", "from rdc import __version__; print(__version__)"],
            capture_output=True,
            text=True,
        )
        init_version = init_ver_result.stdout.strip()
        check_output("rdc --version matches installed", installed_version, [str(rdc), "--version"])
        check_output(
            "__init__.py version matches installed",
            installed_version,
            [str(python), "-c", "from rdc import __version__; print(__version__)"],
        )
        if init_version and installed_version and init_version != installed_version:
            _log(False, f"version mismatch: rdc={installed_version}, __init__={init_version}")
            _record(False)

    if dist.exists():
        shutil.rmtree(dist)

    print()
    print("================================")
    if USE_COLOR:
        print(f"  \033[0;32m{PASS_COUNT} passed\033[0m, \033[0;31m{FAIL_COUNT} failed\033[0m")
    else:
        print(f"  {PASS_COUNT} passed, {FAIL_COUNT} failed")
    print("================================")

    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
