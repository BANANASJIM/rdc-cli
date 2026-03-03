"""Shared fixtures for e2e black-box tests.

All tests in this package invoke the real CLI via subprocess and require
a working renderdoc installation (GPU marker applied automatically).
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from e2e_helpers import (
    DYNAMIC_RENDERING,
    OIT_DEPTH_PEELING,
    VKCUBE,
    VKCUBE_BIN,
    CaptureMetadata,
    rdc,
    rdc_json,
    rdc_ok,
    self_capture,
)

# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------

_log = logging.getLogger(__name__)
_DISCOVER_SESSION = "e2e_discover"


@pytest.fixture(scope="session")
def captured_rdc(tmp_path_factory: pytest.TempPathFactory) -> Generator[Path, None, None]:
    """Self-capture vkcube or fall back to pre-recorded fixture."""
    if VKCUBE_BIN is None:
        _log.info("vkcube not found; falling back to pre-recorded fixture")
        yield VKCUBE
        return

    tmp = tmp_path_factory.mktemp("selfcap")
    output = tmp / "selfcap.rdc"
    try:
        path = self_capture(VKCUBE_BIN, output)
        _log.info("self-captured: %s", path)
        yield path
    except Exception:
        _log.warning("self-capture failed; falling back to pre-recorded fixture")
        yield VKCUBE


@pytest.fixture(scope="session")
def capture_meta(captured_rdc: Path) -> CaptureMetadata:
    """Open capture, discover all IDs dynamically, close session."""
    session = f"{_DISCOVER_SESSION}_{uuid.uuid4().hex[:8]}"
    r = rdc("open", str(captured_rdc), session=session)
    assert r.returncode == 0, f"Failed to open capture for discovery: {r.stderr}"

    try:
        return _discover_metadata(session)
    finally:
        rdc("close", session=session)


@pytest.fixture(scope="session")
def can_replay_prerecorded() -> bool:
    """Check if pre-recorded NVIDIA fixtures can replay on this GPU."""
    if not VKCUBE.exists():
        return False
    name = f"e2e_probe_{uuid.uuid4().hex[:8]}"
    r = rdc("open", str(VKCUBE), session=name)
    rdc("close", session=name)
    return r.returncode == 0


def _discover_metadata(session: str) -> CaptureMetadata:
    """Run discovery queries against an open session."""
    # events
    events_data = rdc_json("events", session=session)
    all_eids = [e["eid"] for e in events_data]
    total_events = len(all_eids)

    # draws
    draws_data = rdc_json("draws", session=session)
    assert draws_data, "Discovery found no draw calls -- capture may be corrupt"
    total_draws = len(draws_data)
    primary_draw = draws_data[0]
    draw_eid = primary_draw["eid"]
    triangle_count = primary_draw["triangles"]

    # resources
    resources_data = rdc_json("resources", session=session)
    total_resources = len(resources_data)

    # Use VFS listings as source of truth (resources may list IDs not routable in VFS)
    textures_out = rdc_ok("ls", "/textures", session=session)
    texture_ids = [
        int(ln.strip()) for ln in textures_out.strip().splitlines() if ln.strip().isdigit()
    ]

    buffers_out = rdc_ok("ls", "/buffers", session=session)
    buffer_ids = [
        int(ln.strip()) for ln in buffers_out.strip().splitlines() if ln.strip().isdigit()
    ]

    texture_id = texture_ids[0] if texture_ids else 0
    buffer_id = buffer_ids[0] if buffer_ids else 0

    # shaders
    shaders_data = rdc_json("shaders", session=session)
    total_shaders = len(shaders_data)
    shader_ids: list[int] = [s["shader"] for s in shaders_data]

    vs_id = 0
    ps_id = 0
    for s in shaders_data:
        stages = s.get("stages", "").lower()
        if "vs" in stages and vs_id == 0:
            vs_id = s["shader"]
        if "ps" in stages and ps_id == 0:
            ps_id = s["shader"]
    if vs_id == 0 and shader_ids:
        vs_id = shader_ids[0]
    if ps_id == 0 and len(shader_ids) > 1:
        ps_id = shader_ids[1]
    elif ps_id == 0 and shader_ids:
        ps_id = shader_ids[0]

    # passes
    passes_data = rdc_json("passes", session=session)
    if isinstance(passes_data, dict):
        passes_list = passes_data.get("passes", passes_data)
    else:
        passes_list = passes_data
    if isinstance(passes_list, list):
        pass_count = len(passes_list)
        pass_name = passes_list[0].get("name", "") if passes_list else ""
    else:
        pass_count = 0
        pass_name = ""
    assert pass_name, "Discovery found no pass name -- capture may be corrupt"

    # stats (for framebuffer dimensions)
    stats_data = rdc_json("stats", session=session)
    fb_width = 0
    fb_height = 0
    per_pass = stats_data.get("per_pass", [])
    for pp in per_pass:
        w = pp.get("rt_w")
        h = pp.get("rt_h")
        if isinstance(w, int) and w > 0 and isinstance(h, int) and h > 0:
            fb_width = w
            fb_height = h
            break

    # pixel color at center
    assert fb_width > 0 and fb_height > 0, (
        f"Discovery could not determine framebuffer size (got {fb_width}x{fb_height})"
    )
    pixel_x = fb_width // 2
    pixel_y = fb_height // 2

    pixel_data = rdc_json(
        "pick-pixel",
        str(pixel_x),
        str(pixel_y),
        str(draw_eid),
        session=session,
        timeout=60,
    )
    color = pixel_data.get("color", {})
    pixel_rgba = (
        color.get("r", 0.0),
        color.get("g", 0.0),
        color.get("b", 0.0),
        color.get("a", 0.0),
    )

    return CaptureMetadata(
        draw_eid=draw_eid,
        all_eids=all_eids,
        texture_id=texture_id,
        texture_ids=texture_ids,
        buffer_id=buffer_id,
        vs_id=vs_id,
        ps_id=ps_id,
        shader_ids=shader_ids,
        total_events=total_events,
        total_draws=total_draws,
        total_resources=total_resources,
        total_shaders=total_shaders,
        triangle_count=triangle_count,
        pass_name=pass_name,
        pass_count=pass_count,
        fb_width=fb_width,
        fb_height=fb_height,
        pixel_x=pixel_x,
        pixel_y=pixel_y,
        pixel_rgba=pixel_rgba,
    )


# ---------------------------------------------------------------------------
# Module-scoped session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def vkcube_session(captured_rdc: Path) -> Generator[str, None, None]:
    """Open captured .rdc and yield session name; close on teardown."""
    name = f"e2e_vkcube_{uuid.uuid4().hex[:8]}"
    r = rdc("open", str(captured_rdc), session=name)
    assert r.returncode == 0, f"Failed to open capture: {r.stderr}"
    yield name
    rdc("close", session=name)


@pytest.fixture(scope="module")
def dynamic_session() -> Generator[str, None, None]:
    """Open dynamic_rendering.rdc and yield session name.

    Skips if the fixture is missing or fails to open (GPU mismatch).
    """
    if not DYNAMIC_RENDERING.exists():
        pytest.skip("dynamic_rendering.rdc not available")
    name = f"e2e_dynamic_{uuid.uuid4().hex[:8]}"
    r = rdc("open", str(DYNAMIC_RENDERING), session=name)
    if r.returncode != 0:
        pytest.skip(f"dynamic_rendering.rdc failed to open (GPU mismatch?): {r.stderr}")
    yield name
    rdc("close", session=name)


@pytest.fixture(scope="module")
def oit_session() -> Generator[str, None, None]:
    """Open oit_depth_peeling.rdc and yield session name.

    Skips if the fixture is missing or fails to open (GPU mismatch).
    """
    if not OIT_DEPTH_PEELING.exists():
        pytest.skip("oit_depth_peeling.rdc not available")
    name = f"e2e_oit_{uuid.uuid4().hex[:8]}"
    r = rdc("open", str(OIT_DEPTH_PEELING), session=name)
    if r.returncode != 0:
        pytest.skip(f"oit_depth_peeling.rdc failed to open (GPU mismatch?): {r.stderr}")
    yield name
    rdc("close", session=name)


@pytest.fixture(scope="session")
def vulkan_samples_bin() -> str:
    """Path to vulkan_samples binary for live capture testing."""
    path = os.environ.get("VULKAN_SAMPLES_BIN")
    candidate = Path(path) if path else None
    if not candidate:
        bin_name = "vulkan_samples.exe" if os.name == "nt" else "vulkan_samples"
        local = Path(__file__).parent.parent.parent / ".local" / "vulkan-samples" / bin_name
        candidate = local if local.exists() else None
    if not candidate or not candidate.is_file() or not os.access(candidate, os.X_OK):
        pytest.skip("vulkan_samples binary not available")
    return str(candidate)


@pytest.fixture
def tmp_out(tmp_path: Path) -> Path:
    """Return a temporary output directory for export tests."""
    return tmp_path
