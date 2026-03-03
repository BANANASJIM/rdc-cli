"""Shared helpers and constants for e2e black-box tests.

Extracted from conftest.py so that test modules can import them
without colliding with tests/conftest.py on sys.path.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
VKCUBE = FIXTURES_DIR / "vkcube.rdc"
HELLO_TRIANGLE = FIXTURES_DIR / "hello_triangle.rdc"
DYNAMIC_RENDERING = FIXTURES_DIR / "dynamic_rendering.rdc"
OIT_DEPTH_PEELING = FIXTURES_DIR / "oit_depth_peeling.rdc"
VKCUBE_VALIDATION = FIXTURES_DIR / "vkcube_validation.rdc"

VKCUBE_BIN: str | None = os.environ.get("VKCUBE_BIN") or shutil.which("vkcube")


def self_capture(vkcube_path: str, output: Path, timeout: int = 60) -> Path:
    """Run ``rdc capture`` against *vkcube_path* and return the .rdc path."""
    r = subprocess.run(
        ["uv", "run", "rdc", "capture", "-o", str(output), "--", vkcube_path],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"self_capture failed (exit {r.returncode}):\n{r.stderr}")
    # Output path is on stdout; RenderDoc may add a _frame0 suffix
    stdout_path = r.stdout.strip()
    if stdout_path and Path(stdout_path).exists():
        return Path(stdout_path)
    # Fallback: glob for any .rdc file in the output directory
    candidates = list(output.parent.glob("*.rdc"))
    if candidates:
        return candidates[0]
    raise RuntimeError(f"No .rdc file produced by capture:\n{r.stdout}\n{r.stderr}")


def rdc(
    *args: str,
    session: str = "e2e_default",
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run ``uv run rdc`` as a subprocess and return the result."""
    cmd = ["uv", "run", "rdc", "--session", session, *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def rdc_ok(*args: str, session: str = "e2e_default", timeout: int = 30) -> str:
    """Run rdc, assert exit 0, return stdout."""
    r = rdc(*args, session=session, timeout=timeout)
    assert r.returncode == 0, f"rdc {' '.join(args)} failed:\n{r.stderr}"
    return r.stdout


def rdc_json(*args: str, session: str = "e2e_default", timeout: int = 30) -> Any:
    """Run rdc with --json, assert exit 0, return parsed JSON."""
    out = rdc_ok(*args, "--json", session=session, timeout=timeout)
    return json.loads(out)


def rdc_fail(
    *args: str, session: str = "e2e_default", exit_code: int = 1, timeout: int = 30
) -> str:
    """Run rdc, assert expected non-zero exit, return combined output."""
    r = rdc(*args, session=session, timeout=timeout)
    assert r.returncode == exit_code, (
        f"Expected exit {exit_code}, got {r.returncode}\nstdout: {r.stdout}\nstderr: {r.stderr}"
    )
    return r.stdout + r.stderr
