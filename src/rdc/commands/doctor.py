from __future__ import annotations

import platform
import shutil
import sys
from dataclasses import dataclass
from typing import Any

import click

from rdc.discover import find_renderdoc


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_python() -> CheckResult:
    return CheckResult("python", True, sys.version.split()[0])


def _check_platform() -> CheckResult:
    system = platform.system().lower()
    if system == "linux":
        return CheckResult("platform", True, "linux")
    if system == "darwin":
        return CheckResult("platform", True, "darwin (dev-host only for replay)")
    return CheckResult("platform", False, f"unsupported system: {system}")


_RENDERDOC_BUILD_HINT = """\
  To build the renderdoc Python module:
    git clone --depth 1 https://github.com/baldurk/renderdoc.git
    cd renderdoc
    cmake -B build -DENABLE_PYRENDERDOC=ON -DENABLE_QRENDERDOC=OFF
    cmake --build build -j$(nproc)
    export RENDERDOC_PYTHON_PATH=$PWD/build/lib"""


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
    path = shutil.which("renderdoccmd")
    if path:
        return CheckResult("renderdoccmd", True, path)
    return CheckResult("renderdoccmd", False, "not found in PATH")


def run_doctor() -> list[CheckResult]:
    module, renderdoc_check = _import_renderdoc()
    return [
        _check_python(),
        _check_platform(),
        renderdoc_check,
        _check_replay_support(module),
        _check_renderdoccmd(),
    ]


@click.command("doctor")
def doctor_cmd() -> None:
    """Run environment checks for rdc-cli."""
    results = run_doctor()
    has_error = False

    for result in results:
        icon = "✅" if result.ok else "❌"
        click.echo(f"{icon} {result.name}: {result.detail}")
        if not result.ok:
            has_error = True
            if result.name == "renderdoc-module":
                click.echo(_RENDERDOC_BUILD_HINT, err=True)

    if has_error:
        raise SystemExit(1)
