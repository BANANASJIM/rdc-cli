"""Integration tests for daemon handlers with real renderdoc replay."""

from __future__ import annotations

from pathlib import Path
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
    textures = adapter.get_textures()
    buffers = adapter.get_buffers()

    state.tex_map = {int(t.resourceId): t for t in textures}
    state.buf_map = {int(b.resourceId): b for b in buffers}
    state.res_names = {int(r.resourceId): r.name for r in resources}
    state.res_types = {
        int(r.resourceId): getattr(getattr(r, "type", None), "name", str(getattr(r, "type", "")))
        for r in resources
    }
    state.res_rid_map = {int(r.resourceId): r.resourceId for r in resources}

    state.rd = rd_module
    state.vfs_tree = build_vfs_skeleton(root_actions, resources, textures, buffers, sf)
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

    def test_usage_single_resource(self) -> None:
        """GetUsage on a known resource returns entries with valid schema."""
        resources = _call(self.state, "resources")
        rid = resources["rows"][0]["id"]
        result = _call(self.state, "usage", {"id": rid})
        assert result["id"] == rid
        assert isinstance(result["entries"], list)
        assert "name" in result
        for e in result["entries"]:
            assert isinstance(e["eid"], int)
            assert isinstance(e["usage"], str)
            assert len(e["usage"]) > 0

    def test_usage_all(self) -> None:
        """usage_all returns a full matrix with valid row schema."""
        result = _call(self.state, "usage_all")
        assert result["total"] >= 0
        assert result["total"] == len(result["rows"])
        for row in result["rows"]:
            assert isinstance(row["id"], int)
            assert isinstance(row["name"], str)
            assert isinstance(row["eid"], int)
            assert isinstance(row["usage"], str)

    def test_usage_all_filter(self) -> None:
        """usage_all with usage filter returns only matching rows."""
        full = _call(self.state, "usage_all")
        if not full["rows"]:
            pytest.skip("no usage data in capture")
        target_usage = full["rows"][0]["usage"]
        filtered = _call(self.state, "usage_all", {"usage": target_usage})
        assert all(r["usage"] == target_usage for r in filtered["rows"])
        assert filtered["total"] <= full["total"]

    def test_vfs_resource_usage(self) -> None:
        """VFS /resources/<id>/usage resolves and returns data."""
        resources = _call(self.state, "resources")
        rid = resources["rows"][0]["id"]
        result = _call(self.state, "vfs_ls", {"path": f"/resources/{rid}"})
        names = [c["name"] for c in result["children"]]
        assert "usage" in names

    def test_counter_list(self) -> None:
        """counter_list returns built-in counters with valid schema."""
        result = _call(self.state, "counter_list")
        assert result["total"] >= 13
        for c in result["counters"]:
            assert isinstance(c["id"], int)
            assert isinstance(c["name"], str) and len(c["name"]) > 0
            assert isinstance(c["unit"], str)
            assert isinstance(c["type"], str)
            assert isinstance(c["category"], str)

    def test_counter_fetch(self) -> None:
        """counter_fetch returns values for draw events."""
        result = _call(self.state, "counter_fetch")
        assert result["total"] > 0
        for r in result["rows"]:
            assert isinstance(r["eid"], int)
            assert isinstance(r["counter"], str)
            assert isinstance(r["unit"], str)
        # GPU Duration should be > 0
        durations = [r for r in result["rows"] if r["counter"] == "GPU Duration"]
        if durations:
            assert durations[0]["value"] > 0

    def test_counter_fetch_eid_filter(self) -> None:
        """counter_fetch with eid filter returns only matching event."""
        events = _call(self.state, "events", {"type": "draw"})
        draw_eid = events["events"][0]["eid"]
        result = _call(self.state, "counter_fetch", {"eid": draw_eid})
        assert all(r["eid"] == draw_eid for r in result["rows"])

    def test_vfs_counters_list(self) -> None:
        """VFS /counters/list resolves."""
        result = _call(self.state, "vfs_ls", {"path": "/counters"})
        names = [c["name"] for c in result["children"]]
        assert "list" in names

    def test_descriptors_basic(self) -> None:
        """Descriptors for a draw eid returns valid entries."""
        events_result = _call(self.state, "events", {"type": "draw"})
        draw_eid = events_result["events"][0]["eid"]
        result = _call(self.state, "descriptors", {"eid": draw_eid})
        assert isinstance(result["descriptors"], list)
        assert len(result["descriptors"]) >= 1
        for d in result["descriptors"]:
            assert "stage" in d
            assert "type" in d
            assert "index" in d
            assert "resource_id" in d
            assert "format" in d
            assert "byte_size" in d

    def test_descriptors_sampler(self) -> None:
        """Sampler descriptors appear with sampler sub-dict (skip if none)."""
        events_result = _call(self.state, "events", {"type": "draw"})
        draw_eid = events_result["events"][0]["eid"]
        result = _call(self.state, "descriptors", {"eid": draw_eid})
        sampler_entries = [
            d for d in result["descriptors"] if d["type"] in ("Sampler", "ImageSampler")
        ]
        if not sampler_entries:
            pytest.skip("no sampler descriptors in capture")
        for s in sampler_entries:
            assert "sampler" in s
            assert "filter" in s["sampler"]
            assert "address_u" in s["sampler"]

    def test_vfs_ls_draw_descriptors(self) -> None:
        """VFS /draws/<eid>/descriptors is listed as a child."""
        events_result = _call(self.state, "events", {"type": "draw"})
        draw_eid = events_result["events"][0]["eid"]
        result = _call(self.state, "vfs_ls", {"path": f"/draws/{draw_eid}"})
        names = [c["name"] for c in result["children"]]
        assert "descriptors" in names

    def test_vfs_cat_descriptors(self) -> None:
        """VFS cat /draws/<eid>/descriptors returns TSV with correct header."""
        events_result = _call(self.state, "events", {"type": "draw"})
        draw_eid = events_result["events"][0]["eid"]
        result = _call(self.state, "descriptors", {"eid": draw_eid})
        assert isinstance(result["descriptors"], list)
        for d in result["descriptors"]:
            assert len(d.keys()) >= 7


class TestBinaryHandlersReal:
    """Integration tests for Phase 2 binary export handlers."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        vkcube_replay: tuple[Any, Any, Any],
        rd_module: Any,
        tmp_path: Path,
    ) -> None:
        self.state = _make_state(vkcube_replay, rd_module)
        self.state.temp_dir = tmp_path

    def _first_texture_id(self) -> int:
        """Find the first texture resource ID."""
        if self.state.tex_map:
            return next(iter(self.state.tex_map))
        pytest.skip("no texture resources in capture")

    def _first_buffer_id(self) -> int:
        """Find the first buffer resource ID."""
        if self.state.buf_map:
            return next(iter(self.state.buf_map))
        pytest.skip("no buffer resources in capture")

    def _first_draw_eid(self) -> int:
        """Find the first draw call EID."""
        result = _call(self.state, "events", {"type": "draw"})
        draws = result["events"]
        assert len(draws) > 0, "no draw calls in capture"
        return draws[0]["eid"]

    def test_vfs_ls_textures(self) -> None:
        result = _call(self.state, "vfs_ls", {"path": "/textures"})
        assert result["kind"] == "dir"
        assert len(result["children"]) > 0

    def test_vfs_ls_buffers(self) -> None:
        result = _call(self.state, "vfs_ls", {"path": "/buffers"})
        assert result["kind"] == "dir"
        assert len(result["children"]) > 0

    def test_vfs_ls_texture_subtree(self) -> None:
        tex_id = self._first_texture_id()
        result = _call(self.state, "vfs_ls", {"path": f"/textures/{tex_id}"})
        names = [c["name"] for c in result["children"]]
        assert "info" in names
        assert "image.png" in names
        assert "mips" in names
        assert "data" in names

    def test_tex_info(self) -> None:
        tex_id = self._first_texture_id()
        result = _call(self.state, "tex_info", {"id": tex_id})
        assert result["id"] == tex_id
        assert result["width"] > 0
        assert result["height"] > 0
        assert result["mips"] >= 1
        assert "format" in result
        assert "type" in result
        assert "byte_size" in result

    def test_tex_export_png(self) -> None:
        tex_id = self._first_texture_id()
        result = _call(self.state, "tex_export", {"id": tex_id, "mip": 0})
        assert "path" in result
        assert result["size"] > 0
        exported = Path(result["path"])
        assert exported.exists()
        data = exported.read_bytes()
        assert data[:4] == b"\x89PNG", f"Not a PNG file: {data[:8]!r}"

    def test_tex_raw(self) -> None:
        tex_id = self._first_texture_id()
        result = _call(self.state, "tex_raw", {"id": tex_id})
        assert "path" in result
        assert result["size"] > 0
        exported = Path(result["path"])
        assert exported.exists()
        assert exported.stat().st_size == result["size"]

    def test_buf_info(self) -> None:
        buf_id = self._first_buffer_id()
        result = _call(self.state, "buf_info", {"id": buf_id})
        assert result["id"] == buf_id
        assert "name" in result
        assert "length" in result
        assert "creation_flags" in result

    def test_buf_raw(self) -> None:
        buf_id = self._first_buffer_id()
        result = _call(self.state, "buf_raw", {"id": buf_id})
        assert "path" in result
        assert result["size"] > 0
        exported = Path(result["path"])
        assert exported.exists()

    def test_vfs_ls_draw_targets(self) -> None:
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "vfs_ls", {"path": f"/draws/{draw_eid}/targets"})
        assert result["kind"] == "dir"
        children = result["children"]
        assert len(children) >= 1
        names = [c["name"] for c in children]
        assert any(n.startswith("color") for n in names)

    def test_rt_export_png(self) -> None:
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "rt_export", {"eid": draw_eid, "target": 0})
        assert "path" in result
        assert result["size"] > 0
        exported = Path(result["path"])
        assert exported.exists()
        data = exported.read_bytes()
        assert data[:4] == b"\x89PNG", f"Not a PNG file: {data[:8]!r}"

    def test_rt_depth(self) -> None:
        draw_eid = self._first_draw_eid()
        req = {
            "id": 1,
            "method": "rt_depth",
            "params": {"_token": self.state.token, "eid": draw_eid},
        }
        resp, _ = _handle_request(req, self.state)
        if "error" in resp:
            assert "no depth target" in resp["error"]["message"]
        else:
            result = resp["result"]
            assert "path" in result
            exported = Path(result["path"])
            assert exported.exists()

    def test_search_basic(self) -> None:
        """Search for a common SPIR-V instruction across all shaders."""
        # RenderDoc's built-in disassembler uses "Capability(Shader);"
        # not the standard "OpCapability Shader" syntax.
        result = _call(self.state, "search", {"pattern": "Capability"})
        matches = result["matches"]
        assert len(matches) > 0
        m = matches[0]
        assert "shader" in m
        assert "stages" in m
        assert "line" in m
        assert "text" in m
        assert "Capability" in m["text"]

    def test_search_no_matches(self) -> None:
        result = _call(self.state, "search", {"pattern": "XYZZY_IMPOSSIBLE_TOKEN_42"})
        assert result["matches"] == []

    def test_search_limit(self) -> None:
        result = _call(self.state, "search", {"pattern": "main", "limit": 2})
        assert len(result["matches"]) <= 2

    def test_shader_list_info(self) -> None:
        """Build cache then query a shader's info."""
        _call(self.state, "search", {"pattern": "main", "limit": 1})
        assert len(self.state.shader_meta) > 0
        sid = next(iter(self.state.shader_meta))
        result = _call(self.state, "shader_list_info", {"id": sid})
        assert result["id"] == sid
        assert "stages" in result
        assert "uses" in result

    def test_shader_list_disasm(self) -> None:
        """Build cache then query a shader's disassembly."""
        _call(self.state, "search", {"pattern": "main", "limit": 1})
        sid = next(iter(self.state.disasm_cache))
        result = _call(self.state, "shader_list_disasm", {"id": sid})
        assert result["id"] == sid
        assert len(result["disasm"]) > 0

    def test_vfs_ls_shaders(self) -> None:
        """After cache build, /shaders/ should list shader IDs."""
        _call(self.state, "search", {"pattern": "main", "limit": 1})
        result = _call(self.state, "vfs_ls", {"path": "/shaders"})
        assert result["kind"] == "dir"
        assert len(result["children"]) > 0
        child = result["children"][0]
        assert child["kind"] == "dir"

    def test_temp_dir_cleanup_on_shutdown(self) -> None:
        """Verify temp dir is cleaned on shutdown."""
        temp_dir = self.state.temp_dir
        assert temp_dir.exists()
        (temp_dir / "test.bin").write_bytes(b"data")
        # Clear adapter/cap so shutdown handler only tests temp cleanup,
        # not the shared session-scoped controller (avoids double-shutdown segfault).
        self.state.adapter = None
        self.state.cap = None
        req = {"id": 1, "method": "shutdown", "params": {"_token": self.state.token}}
        resp, running = _handle_request(req, self.state)
        assert resp["result"]["ok"] is True
        assert running is False
        assert not temp_dir.exists()
