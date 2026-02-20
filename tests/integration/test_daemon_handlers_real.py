"""Integration tests for daemon handlers with real renderdoc replay."""

from __future__ import annotations

from typing import Any

import pytest

from rdc.adapter import RenderDocAdapter, parse_version_tuple
from rdc.daemon_server import DaemonState, _handle_request, _max_eid

pytestmark = pytest.mark.gpu


def _make_state(
    vkcube_replay: tuple[Any, Any, Any],
    rd_module: Any,
) -> DaemonState:
    """Build a DaemonState from real replay fixtures."""
    cap, controller, sf = vkcube_replay
    version = parse_version_tuple(rd_module.GetVersionString())
    adapter = RenderDocAdapter(controller=controller, version=version)

    state = DaemonState(capture="vkcube.rdc", current_eid=0, token="test-token")
    state.adapter = adapter
    state.cap = cap
    state.structured_file = sf

    api_props = adapter.get_api_properties()
    pt = getattr(api_props, "pipelineType", "Unknown")
    state.api_name = getattr(pt, "name", str(pt))

    root_actions = adapter.get_root_actions()
    state.max_eid = _max_eid(root_actions)

    from rdc.vfs.tree_cache import build_vfs_skeleton

    resources = adapter.get_resources()
    state.vfs_tree = build_vfs_skeleton(root_actions, resources, sf)
    return state


def _call(state: DaemonState, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send a request to _handle_request and return the result."""
    req = {
        "id": 1,
        "method": method,
        "params": {"_token": state.token, **(params or {})},
    }
    resp, _running = _handle_request(req, state)
    assert "error" not in resp, f"handler error: {resp.get('error')}"
    return resp["result"]


class TestDaemonHandlersReal:
    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def test_status(self) -> None:
        result = _call(self.state, "status")
        assert "Vulkan" in result["api"]
        assert result["event_count"] > 0

    def test_info(self) -> None:
        result = _call(self.state, "info")
        assert "Capture" in result
        assert "API" in result
        assert "Draw Calls" in result
        assert "Clears" in result

    def test_events(self) -> None:
        result = _call(self.state, "events")
        events = result["events"]
        assert len(events) > 0
        assert all("eid" in e and "type" in e for e in events)

    def test_draws(self) -> None:
        result = _call(self.state, "draws")
        assert len(result["draws"]) > 0
        assert "summary" in result

    def test_pipeline(self) -> None:
        # Find first draw eid
        events_result = _call(self.state, "events", {"type": "draw"})
        draw_eid = events_result["events"][0]["eid"]

        result = _call(self.state, "pipeline", {"eid": draw_eid})
        row = result["row"]
        assert "topology" in row
        assert "graphics_pipeline" in row

    def test_count_draws(self) -> None:
        result = _call(self.state, "count", {"what": "draws"})
        assert result["value"] == 1

    def test_resources(self) -> None:
        result = _call(self.state, "resources")
        assert len(result["rows"]) > 0

    def test_passes(self) -> None:
        result = _call(self.state, "passes")
        tree = result["tree"]
        assert len(tree["passes"]) >= 1

    def test_pass_detail(self) -> None:
        result = _call(self.state, "pass", {"index": 0})
        assert "name" in result
        assert result["begin_eid"] > 0
        assert result["end_eid"] >= result["begin_eid"]
        assert result["draws"] >= 0
        assert "triangles" in result
        assert "color_targets" in result
        assert "depth_target" in result

    def test_log(self) -> None:
        result = _call(self.state, "log")
        assert "messages" in result
        assert isinstance(result["messages"], list)

    def test_vfs_ls_root(self) -> None:
        result = _call(self.state, "vfs_ls", {"path": "/"})
        names = [c["name"] for c in result["children"]]
        assert "draws" in names
        assert "info" in names
        assert "events" in names

    def test_vfs_ls_draws(self) -> None:
        result = _call(self.state, "vfs_ls", {"path": "/draws"})
        assert len(result["children"]) >= 1
        assert all(c["kind"] == "dir" for c in result["children"])

    def test_vfs_ls_draw_shader(self) -> None:
        events_result = _call(self.state, "events", {"type": "draw"})
        draw_eid = events_result["events"][0]["eid"]
        result = _call(self.state, "vfs_ls", {"path": f"/draws/{draw_eid}/shader"})
        stages = [c["name"] for c in result["children"]]
        assert len(stages) >= 1
        assert all(s in ("vs", "hs", "ds", "gs", "ps", "cs") for s in stages)

    def test_vfs_tree_root(self) -> None:
        result = _call(self.state, "vfs_tree", {"path": "/", "depth": 1})
        tree = result["tree"]
        assert tree["name"] == "/"
        child_names = [c["name"] for c in tree["children"]]
        assert "draws" in child_names
        assert "info" in child_names
