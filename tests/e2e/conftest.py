"""Shared fixtures for e2e black-box tests.

All tests in this package invoke the real CLI via subprocess and require
a working renderdoc installation (GPU marker applied automatically).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from e2e_helpers import (
    DYNAMIC_RENDERING,
    OIT_DEPTH_PEELING,
    VKCUBE,
    rdc,
)

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
    candidate = Path(path) if path else None
    if not candidate:
        local = Path(__file__).parent.parent.parent / ".local" / "vulkan-samples" / "vulkan_samples"
        candidate = local if local.exists() else None
    if not candidate or not candidate.is_file() or not os.access(candidate, os.X_OK):
        pytest.skip("vulkan_samples binary not available")
    return str(candidate)


@pytest.fixture
def tmp_out(tmp_path: Path) -> Path:
    """Return a temporary output directory for export tests."""
    return tmp_path
