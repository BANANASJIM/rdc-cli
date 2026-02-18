from __future__ import annotations

import importlib
import shutil
import sys
from dataclasses import dataclass

import click


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_python() -> CheckResult:
    return CheckResult("python", True, sys.version.split()[0])


def _check_renderdoc_module() -> CheckResult:
    try:
        module = importlib.import_module("renderdoc")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("renderdoc-module", False, f"import failed: {exc}")

    version = getattr(module, "GetVersionString", lambda: "unknown")()
    return CheckResult("renderdoc-module", True, f"version={version}")


def _check_renderdoccmd() -> CheckResult:
    path = shutil.which("renderdoccmd")
    if path:
        return CheckResult("renderdoccmd", True, path)
    return CheckResult("renderdoccmd", False, "not found in PATH")


def run_doctor() -> list[CheckResult]:
    return [
        _check_python(),
        _check_renderdoc_module(),
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

    if has_error:
        raise SystemExit(1)
