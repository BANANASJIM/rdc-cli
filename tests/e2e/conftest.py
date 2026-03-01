"""Shared fixtures for e2e black-box tests.

All tests in this package invoke the real CLI via subprocess and require
a working renderdoc installation (GPU marker applied automatically).
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
VKCUBE = FIXTURES_DIR / "vkcube.rdc"
HELLO_TRIANGLE = FIXTURES_DIR / "hello_triangle.rdc"
DYNAMIC_RENDERING = FIXTURES_DIR / "dynamic_rendering.rdc"
OIT_DEPTH_PEELING = FIXTURES_DIR / "oit_depth_peeling.rdc"
VKCUBE_VALIDATION = FIXTURES_DIR / "vkcube_validation.rdc"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def vkcube_session() -> Generator[str, None, None]:
    """Open vkcube.rdc and yield session name; close on teardown."""
    name = f"e2e_vkcube_{uuid.uuid4().hex[:8]}"
    r = rdc("open", str(VKCUBE), session=name)
    assert r.returncode == 0, f"Failed to open vkcube: {r.stderr}"
    yield name
    rdc("close", session=name)


@pytest.fixture(scope="module")
def dynamic_session() -> Generator[str, None, None]:
    """Open dynamic_rendering.rdc and yield session name."""
    if not DYNAMIC_RENDERING.exists():
        pytest.skip("dynamic_rendering.rdc not available")
    name = f"e2e_dynamic_{uuid.uuid4().hex[:8]}"
    r = rdc("open", str(DYNAMIC_RENDERING), session=name)
    assert r.returncode == 0, f"Failed to open dynamic_rendering: {r.stderr}"
    yield name
    rdc("close", session=name)


@pytest.fixture(scope="module")
def oit_session() -> Generator[str, None, None]:
    """Open oit_depth_peeling.rdc and yield session name."""
    if not OIT_DEPTH_PEELING.exists():
        pytest.skip("oit_depth_peeling.rdc not available")
    name = f"e2e_oit_{uuid.uuid4().hex[:8]}"
    r = rdc("open", str(OIT_DEPTH_PEELING), session=name)
    assert r.returncode == 0, f"Failed to open oit_depth_peeling: {r.stderr}"
    yield name
    rdc("close", session=name)


@pytest.fixture(scope="session")
def vulkan_samples_bin() -> str:
    """Path to vulkan_samples binary for live capture testing."""
    path = os.environ.get("VULKAN_SAMPLES_BIN")
    if not path:
        local = Path(__file__).parent.parent.parent / ".local" / "vulkan-samples" / "vulkan_samples"
        path = str(local) if local.exists() else None
    if not path or not Path(path).exists():
        pytest.skip("vulkan_samples binary not available")
    return path


@pytest.fixture
def tmp_out(tmp_path: Path) -> Path:
    """Return a temporary output directory for export tests."""
    return tmp_path
