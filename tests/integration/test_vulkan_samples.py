"""GPU integration tests parametrized over Vulkan Samples .rdc captures.

Opens captures one at a time (yield + shutdown) to avoid exhausting Vulkan device handles.

Control sample size via env var RDC_GPU_SAMPLES:
    all         — test every capture (default)
    N           — randomly pick N captures
    N%          — randomly pick N% of captures
"""

from __future__ import annotations

import os
import random
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from rdc.adapter import RenderDocAdapter, parse_version_tuple
from rdc.daemon_server import DaemonState, _handle_request, _max_eid
from rdc.vfs.tree_cache import build_vfs_skeleton

pytestmark = pytest.mark.gpu

VULKAN_SAMPLES_DIR = Path(__file__).parent.parent / "fixtures" / "vulkan_samples"


def _discover_captures() -> list[str]:
    """Return .rdc paths, sampled according to RDC_GPU_SAMPLES env var."""
    if not VULKAN_SAMPLES_DIR.is_dir():
        return []
    all_caps = sorted(str(p) for p in VULKAN_SAMPLES_DIR.glob("*.rdc"))
    if not all_caps:
        return []

    spec = os.environ.get("RDC_GPU_SAMPLES", "all").strip()
    if spec == "all":
        return all_caps
    if spec.endswith("%"):
        pct = max(1, int(float(spec[:-1]) / 100 * len(all_caps)))
        return sorted(random.sample(all_caps, min(pct, len(all_caps))))
    n = int(spec)
    return sorted(random.sample(all_caps, min(n, len(all_caps))))


def _capture_id(path: str) -> str:
    """Extract human-readable test id from capture path."""
    return Path(path).stem


def _open_capture(rd: Any, rdc_path: str) -> tuple[Any, Any, Any] | None:
    """Open a capture file and return (cap, controller, sf) or None on failure."""
    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(rdc_path, "", None)
    if result != rd.ResultCode.Succeeded:
        return None
    if cap.LocalReplaySupport() != rd.ReplaySupport.Supported:
        cap.Shutdown()
        return None
    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    if result != rd.ResultCode.Succeeded:
        cap.Shutdown()
        return None
    sf = cap.GetStructuredData()
    return cap, controller, sf


def _build_state(rd: Any, rdc_path: str) -> tuple[Any, Any, DaemonState]:
    """Open capture and build DaemonState. Returns (cap, controller, state)."""
    opened = _open_capture(rd, rdc_path)
    if opened is None:
        pytest.skip(f"cannot open capture: {rdc_path}")

    cap, controller, sf = opened
    version = parse_version_tuple(rd.GetVersionString())
    adapter = RenderDocAdapter(controller=controller, version=version)

    state = DaemonState(capture=rdc_path, current_eid=0, token="test-token")
    state.adapter = adapter
    state.cap = cap
    state.structured_file = sf

    api_props = adapter.get_api_properties()
    pt = getattr(api_props, "pipelineType", "Unknown")
    state.api_name = getattr(pt, "name", str(pt))

    root_actions = adapter.get_root_actions()
    state.max_eid = _max_eid(root_actions)

    resources = adapter.get_resources()
    state.vfs_tree = build_vfs_skeleton(root_actions, resources, sf)

    return cap, controller, state


def _call(state: DaemonState, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send a JSON-RPC request and return the result, asserting no error."""
    req = {
        "id": 1,
        "method": method,
        "params": {"_token": state.token, **(params or {})},
    }
    resp, _running = _handle_request(req, state)
    assert "error" not in resp, f"handler error on {method}: {resp.get('error')}"
    return resp["result"]


def _first_draw_eid(state: DaemonState) -> int | None:
    """Return the eid of the first draw event, or None if capture has no draws."""
    result = _call(state, "events", {"type": "draw"})
    events = result["events"]
    return events[0]["eid"] if events else None


_captures = _discover_captures()


@pytest.fixture(params=_captures, ids=[_capture_id(c) for c in _captures])
def state(request: pytest.FixtureRequest, rd_init: Any) -> Generator[DaemonState, None, None]:
    """Open a single capture, yield its DaemonState, then shut it down."""
    cap, controller, s = _build_state(rd_init, request.param)
    yield s
    controller.Shutdown()
    cap.Shutdown()


# -- Status -------------------------------------------------------------------


def test_status(state: DaemonState) -> None:
    result = _call(state, "status")
    assert "Vulkan" in result["api"]
    assert result["event_count"] > 0


# -- Info ----------------------------------------------------------------------


def test_info(state: DaemonState) -> None:
    result = _call(state, "info")
    assert "Capture" in result
    assert "API" in result


# -- Events --------------------------------------------------------------------


def test_events(state: DaemonState) -> None:
    result = _call(state, "events")
    events = result["events"]
    assert len(events) > 0
    assert all("eid" in e and "type" in e for e in events)


# -- Draws ---------------------------------------------------------------------


def test_draws(state: DaemonState) -> None:
    result = _call(state, "draws")
    draws = result["draws"]
    if not draws:
        pytest.skip("capture has no draw calls (compute-only)")
    assert "summary" in result


# -- Passes --------------------------------------------------------------------


def test_passes(state: DaemonState) -> None:
    result = _call(state, "passes")
    tree = result["tree"]
    assert "passes" in tree


def test_pass_detail(state: DaemonState) -> None:
    passes = _call(state, "passes")["tree"]["passes"]
    if not passes:
        pytest.skip("capture has no passes")
    result = _call(state, "pass", {"index": 0})
    assert "name" in result
    assert result["begin_eid"] >= 0
    assert result["end_eid"] >= result["begin_eid"]


# -- Resources -----------------------------------------------------------------


def test_resources(state: DaemonState) -> None:
    result = _call(state, "resources")
    assert len(result["rows"]) > 0


# -- Pipeline ------------------------------------------------------------------


def test_pipeline(state: DaemonState) -> None:
    draw_eid = _first_draw_eid(state)
    if draw_eid is None:
        pytest.skip("no draw calls in capture")
    result = _call(state, "pipeline", {"eid": draw_eid})
    row = result["row"]
    assert isinstance(row, dict)
    assert len(row) > 0


# -- Shader disasm -------------------------------------------------------------


def test_shader_disasm(state: DaemonState) -> None:
    draw_eid = _first_draw_eid(state)
    if draw_eid is None:
        pytest.skip("no draw calls in capture")

    stages_result = _call(state, "shader_all", {"eid": draw_eid})
    stages = stages_result.get("stages", [])
    if not stages:
        pytest.skip("no active shader stages for first draw")

    stage = stages[0]["stage"]
    result = _call(state, "shader_disasm", {"eid": draw_eid, "stage": stage})
    assert "disasm" in result
    assert isinstance(result["disasm"], str)


# -- Log -----------------------------------------------------------------------


def test_log(state: DaemonState) -> None:
    result = _call(state, "log")
    assert "messages" in result
    assert isinstance(result["messages"], list)


# -- VFS -----------------------------------------------------------------------


def test_vfs_ls_root(state: DaemonState) -> None:
    result = _call(state, "vfs_ls", {"path": "/"})
    names = [c["name"] for c in result["children"]]
    assert "draws" in names
    assert "info" in names
    assert "events" in names


def test_vfs_ls_draws(state: DaemonState) -> None:
    result = _call(state, "vfs_ls", {"path": "/draws"})
    children = result["children"]
    if not children:
        pytest.skip("no draws in VFS tree (compute-only)")
    assert all(c["kind"] == "dir" for c in children)


def test_vfs_ls_draw_shader(state: DaemonState) -> None:
    draw_eid = _first_draw_eid(state)
    if draw_eid is None:
        pytest.skip("no draw calls in capture")
    result = _call(state, "vfs_ls", {"path": f"/draws/{draw_eid}/shader"})
    stages = [c["name"] for c in result["children"]]
    if not stages:
        pytest.skip("no shader stages for first draw")
    assert all(s in ("vs", "hs", "ds", "gs", "ps", "cs") for s in stages)


def test_vfs_tree_draw(state: DaemonState) -> None:
    draw_eid = _first_draw_eid(state)
    if draw_eid is None:
        pytest.skip("no draw calls in capture")
    result = _call(state, "vfs_tree", {"path": f"/draws/{draw_eid}", "depth": 2})
    tree = result["tree"]
    assert tree["name"] == str(draw_eid)
    child_names = [c["name"] for c in tree["children"]]
    assert "shader" in child_names
    shader_node = next(c for c in tree["children"] if c["name"] == "shader")
    if shader_node["children"]:
        stage_names = [s["name"] for s in shader_node["children"]]
        assert all(s in ("vs", "hs", "ds", "gs", "ps", "cs") for s in stage_names)
