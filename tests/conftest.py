"""Shared fixtures and markers for rdc-cli test suite."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from rdc.discover import find_renderdoc

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "gpu: requires real renderdoc module and GPU")


@pytest.fixture(scope="session")
def rd_module() -> Any:
    """Return the real renderdoc module, skip if unavailable."""
    mod = find_renderdoc()
    if mod is None:
        pytest.skip("renderdoc module not available")
    return mod


@pytest.fixture(scope="session")
def rd_init(rd_module: Any) -> Generator[Any, None, None]:
    """Initialise renderdoc replay once per session."""
    rd_module.InitialiseReplay(rd_module.GlobalEnvironment(), [])
    yield rd_module
    rd_module.ShutdownReplay()


@pytest.fixture(scope="session")
def vkcube_replay(rd_init: Any) -> Generator[tuple[Any, Any, Any], None, None]:
    """Open vkcube.rdc and yield (cap, controller, structured_file)."""
    rd = rd_init

    cap = rd.OpenCaptureFile()
    rdc_path = str(FIXTURES_DIR / "vkcube.rdc")
    result = cap.OpenFile(rdc_path, "", None)
    assert result == rd.ResultCode.Succeeded, f"OpenFile failed: {result}"

    assert cap.LocalReplaySupport() == rd.ReplaySupport.Supported
    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    assert result == rd.ResultCode.Succeeded, f"OpenCapture failed: {result}"

    sf = cap.GetStructuredData()
    yield cap, controller, sf

    controller.Shutdown()
    cap.Shutdown()


@pytest.fixture(scope="session")
def adapter(vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> Any:
    """Return a RenderDocAdapter wrapping the real controller."""
    from rdc.adapter import RenderDocAdapter, parse_version_tuple

    _, controller, _ = vkcube_replay
    version = parse_version_tuple(rd_module.GetVersionString())
    return RenderDocAdapter(controller=controller, version=version)
