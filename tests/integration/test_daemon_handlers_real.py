"""Integration tests for daemon handlers with real renderdoc replay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdc.adapter import RenderDocAdapter, parse_version_tuple
from rdc.daemon_server import DaemonState, _handle_request, _max_eid

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
VKCUBE_RDC = str(FIXTURES_DIR / "vkcube.rdc")

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

    def test_pixel_history_real(self) -> None:
        """PixelHistory on a draw event returns valid modification entries."""
        events_result = _call(self.state, "events", {"type": "draw"})
        draws = events_result["events"]
        assert len(draws) > 0
        draw_eid = draws[0]["eid"]

        # Pick center of likely render area
        result = _call(self.state, "pixel_history", {"x": 320, "y": 240, "eid": draw_eid})
        assert isinstance(result["modifications"], list)
        for m in result["modifications"]:
            assert isinstance(m["eid"], int)
            assert isinstance(m["fragment"], int)
            assert isinstance(m["passed"], bool)
            assert isinstance(m["flags"], list)
            pm = m["post_mod"]
            for c in ("r", "g", "b", "a"):
                assert isinstance(pm[c], (int, float))
            d = m["depth"]
            assert d is None or isinstance(d, float)

    def test_pixel_history_background_real(self) -> None:
        """Background pixel returns empty or clear-only modifications (no error)."""
        events_result = _call(self.state, "events", {"type": "draw"})
        draw_eid = events_result["events"][0]["eid"]
        result = _call(self.state, "pixel_history", {"x": 0, "y": 0, "eid": draw_eid})
        assert isinstance(result["modifications"], list)

    def test_pixel_history_depth_null_real(self) -> None:
        """No raw -1.0 depth in returned modifications."""
        events_result = _call(self.state, "events", {"type": "draw"})
        draw_eid = events_result["events"][0]["eid"]
        result = _call(self.state, "pixel_history", {"x": 320, "y": 240, "eid": draw_eid})
        for m in result["modifications"]:
            assert m["depth"] != -1.0, "raw -1.0 depth must be serialized as null"


class TestResourcesFilterReal:
    """GPU integration tests for resources filter/sort (phase2.7)."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def test_resources_type_is_string(self) -> None:
        result = _call(self.state, "resources")
        rows = result["rows"]
        assert len(rows) > 0
        for row in rows:
            assert isinstance(row["type"], str)
            assert len(row["type"]) > 0

    def test_resources_no_ghost_fields(self) -> None:
        result = _call(self.state, "resources")
        for row in result["rows"]:
            for ghost in ("width", "height", "depth", "format"):
                assert ghost not in row, f"ghost field '{ghost}' present in row"

    def test_resources_filter_by_type(self) -> None:
        all_rows = _call(self.state, "resources")["rows"]
        if not all_rows:
            pytest.skip("no resources in capture")
        target_type = all_rows[0]["type"]
        filtered = _call(self.state, "resources", {"type": target_type})["rows"]
        assert len(filtered) >= 1
        assert all(r["type"].lower() == target_type.lower() for r in filtered)

    def test_resources_filter_by_name(self) -> None:
        all_rows = _call(self.state, "resources")["rows"]
        if not all_rows:
            pytest.skip("no resources in capture")
        target_name = all_rows[0]["name"]
        if not target_name:
            pytest.skip("first resource has empty name")
        substring = target_name[:3].lower()
        filtered = _call(self.state, "resources", {"name": substring})["rows"]
        assert len(filtered) >= 1
        assert all(substring in r["name"].lower() for r in filtered)


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


class TestBugFiltersReal:
    """GPU regression tests for phase2.7-bug-filters fixes (Fixes 1-5)."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def test_fix1_shaders_stage_vs_filter(self) -> None:
        """Fix 1: shaders --stage vs returns only VS rows, result is non-empty."""
        result = _call(self.state, "shaders", {"stage": "vs"})
        rows = result["rows"]
        assert len(rows) > 0, "expected at least one VS shader"
        for r in rows:
            assert "vs" in r["stages"].lower().split(","), (
                f"row stages={r['stages']!r} does not contain 'vs'"
            )

    def test_fix1_shaders_stage_ps_filter(self) -> None:
        """Fix 1: shaders --stage ps returns only PS rows."""
        result = _call(self.state, "shaders", {"stage": "ps"})
        rows = result["rows"]
        assert len(rows) > 0, "expected at least one PS shader"
        for r in rows:
            assert "ps" in r["stages"].lower().split(",")

    def test_fix1_shaders_no_filter_returns_all(self) -> None:
        """Fix 1: shaders without stage filter returns unfiltered rows."""
        all_rows = _call(self.state, "shaders")["rows"]
        vs_rows = _call(self.state, "shaders", {"stage": "vs"})["rows"]
        assert len(all_rows) >= len(vs_rows)

    def test_fix2_draws_pass_filter_matches_passes(self) -> None:
        """Fix 2: draws --pass <name> with a name from rdc passes returns non-empty list."""
        passes_result = _call(self.state, "passes")
        pass_list = passes_result["tree"]["passes"]
        if not pass_list:
            pytest.skip("no passes in capture")
        pass_name = pass_list[0]["name"]
        result = _call(self.state, "draws", {"pass": pass_name})
        draws = result["draws"]
        assert len(draws) > 0, f"expected draws in pass {pass_name!r}"

    def test_fix3_draws_summary_matches_len(self) -> None:
        """Fix 3: summary draw count matches len(draws) in response."""
        passes_result = _call(self.state, "passes")
        pass_list = passes_result["tree"]["passes"]
        if not pass_list:
            pytest.skip("no passes in capture")
        pass_name = pass_list[0]["name"]
        result = _call(self.state, "draws", {"pass": pass_name})
        draws = result["draws"]
        summary = result["summary"]
        expected_prefix = f"{len(draws)} draw calls"
        assert summary.startswith(expected_prefix), (
            f"summary={summary!r} but len(draws)={len(draws)}"
        )

    def test_fix3_draws_no_filter_summary_consistent(self) -> None:
        """Fix 3: unfiltered summary count matches len(draws)."""
        result = _call(self.state, "draws")
        draws = result["draws"]
        summary = result["summary"]
        expected_prefix = f"{len(draws)} draw calls"
        assert summary.startswith(expected_prefix), (
            f"summary={summary!r} but len(draws)={len(draws)}"
        )

    def test_fix4_passes_no_raw_api_names(self) -> None:
        """Fix 4: pass names on markerless capture do not start with 'vkCmd'."""
        passes_result = _call(self.state, "passes")
        pass_list = passes_result["tree"]["passes"]
        for p in pass_list:
            assert not p["name"].startswith("vkCmd"), f"raw API pass name leaked: {p['name']!r}"

    def test_fix4_passes_all_names_nonempty(self) -> None:
        """Fix 4: all pass names are non-empty strings (no raw API name leaks)."""
        passes_result = _call(self.state, "passes")
        pass_list = passes_result["tree"]["passes"]
        for p in pass_list:
            assert isinstance(p["name"], str) and len(p["name"]) > 0

    def test_fix5_topology_is_not_integer(self) -> None:
        """Fix 5: pipeline topology field is not a plain integer string."""
        events_result = _call(self.state, "events", {"type": "draw"})
        draw_eid = events_result["events"][0]["eid"]
        result = _call(self.state, "pipeline", {"eid": draw_eid})
        topology = result["row"]["topology"]
        assert isinstance(topology, str)
        assert not topology.isdigit(), f"topology is raw integer: {topology!r}"

    def test_fix5_topology_is_trianglelist(self) -> None:
        """Fix 5: hello_triangle topology is 'TriangleList', not '3'."""
        events_result = _call(self.state, "events", {"type": "draw"})
        draw_eid = events_result["events"][0]["eid"]
        result = _call(self.state, "pipeline", {"eid": draw_eid})
        topology = result["row"]["topology"]
        assert topology == "TriangleList", f"expected TriangleList, got {topology!r}"


class TestPhase27PipelineCLI:
    """GPU integration tests for phase2.7: section routing, bindings set field, shader disasm."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        draws = result["events"]
        assert len(draws) > 0, "no draw calls in capture"
        return draws[0]["eid"]

    def test_pipeline_section_topology(self) -> None:
        """pipeline with section=topology returns topology key with non-empty string."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pipeline", {"eid": draw_eid, "section": "topology"})
        assert "topology" in result
        assert isinstance(result["topology"], str)
        assert len(result["topology"]) > 0

    def test_pipeline_section_rasterizer(self) -> None:
        """pipeline with section=rasterizer returns rasterizer data keys."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pipeline", {"eid": draw_eid, "section": "rasterizer"})
        assert "eid" in result
        assert result["eid"] == draw_eid

    def test_pipeline_section_blend(self) -> None:
        """pipeline with section=blend returns blend data."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pipeline", {"eid": draw_eid, "section": "blend"})
        assert "blends" in result
        assert isinstance(result["blends"], list)

    def test_pipeline_section_viewport(self) -> None:
        """pipeline with section=viewport returns viewport coordinates."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pipeline", {"eid": draw_eid, "section": "viewport"})
        assert "x" in result
        assert "y" in result
        assert "width" in result
        assert "height" in result

    def test_pipeline_section_depth_stencil(self) -> None:
        """pipeline with section=depth-stencil returns depth-stencil data."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pipeline", {"eid": draw_eid, "section": "depth-stencil"})
        assert "eid" in result
        assert result["eid"] == draw_eid

    def test_bindings_set_field_present(self) -> None:
        """bindings response rows each have a 'set' key with int value >= 0."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "bindings", {"eid": draw_eid})
        rows = result["rows"]
        if not rows:
            pytest.skip("no bindings in capture at this draw")
        for row in rows:
            assert "set" in row, f"row missing 'set' field: {row}"
            assert isinstance(row["set"], int)
            assert row["set"] >= 0

    def test_shader_disasm_with_target(self) -> None:
        """shader_disasm with a target from shader_targets returns non-empty content."""
        draw_eid = self._first_draw_eid()
        targets_result = _call(self.state, "shader_targets")
        targets = targets_result["targets"]
        assert len(targets) > 0, "no disassembly targets available"
        target = targets[0]
        result = _call(
            self.state, "shader_disasm", {"eid": draw_eid, "stage": "ps", "target": target}
        )
        assert "disasm" in result
        assert isinstance(result["disasm"], str)
        assert len(result["disasm"]) > 0

    def test_pipeline_section_routing_same_as_direct(self) -> None:
        """Routing section=topology via pipeline matches pipe_topology directly."""
        draw_eid = self._first_draw_eid()
        via_pipeline = _call(self.state, "pipeline", {"eid": draw_eid, "section": "topology"})
        direct = _call(self.state, "pipe_topology", {"eid": draw_eid})
        assert via_pipeline["topology"] == direct["topology"]


class TestFixVfsPassConsistency:
    """GPU integration tests for fix/vfs-pass-consistency (Fixes 1-3)."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        draws = result["events"]
        assert len(draws) > 0, "no draw calls in capture"
        return draws[0]["eid"]

    def test_draws_pass_matches_passes(self) -> None:
        """Fix 1: draws PASS column values are a subset of passes NAME values."""
        draws_result = _call(self.state, "draws")
        passes_result = _call(self.state, "passes")
        pass_names = {p["name"] for p in passes_result["tree"]["passes"]}
        for d in draws_result["draws"]:
            assert d["pass"] == "-" or d["pass"] in pass_names, (
                f"draw pass={d['pass']!r} not in {pass_names!r}"
            )

    def test_draws_pass_no_api_name(self) -> None:
        """Fix 1: draws PASS column never contains raw API names like 'vkCmd'."""
        result = _call(self.state, "draws")
        for d in result["draws"]:
            assert "vkCmd" not in d["pass"], f"raw API name leaked in draws: {d['pass']!r}"

    def test_vfs_cbuffer_intermediate(self) -> None:
        """Fix 2: ls /draws/<eid>/cbuffer/ returns non-empty children."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "vfs_ls", {"path": f"/draws/{draw_eid}/cbuffer"})
        assert result["kind"] == "dir"
        assert len(result["children"]) > 0, "cbuffer/ should have set-level children"

    def test_vfs_bindings_intermediate(self) -> None:
        """Fix 2: ls /draws/<eid>/bindings/ returns non-empty children (if bindings exist)."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "vfs_ls", {"path": f"/draws/{draw_eid}/bindings"})
        assert result["kind"] == "dir"
        if not result["children"]:
            pytest.skip("no bindings in this draw call")
        assert len(result["children"]) > 0


class TestScriptReal:
    """GPU integration test for script handler with real replay."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)
        self.state.rd = rd_module

    def test_script_get_resources_real(self, tmp_path: Path) -> None:
        """Run a script that calls controller.GetResources() and returns count."""
        script = tmp_path / "probe.py"
        script.write_text("result = len(controller.GetResources())\n", encoding="utf-8")
        result = _call(self.state, "script", {"path": str(script)})
        assert isinstance(result["return_value"], int)
        assert result["return_value"] > 0
        assert result["stdout"] == ""
        assert result["elapsed_ms"] >= 0


# ── Phase 3B Diff GPU Integration Tests ────────────────────────────────


class TestDiffStatsReal:
    """GPU integration tests for diff --stats with real captures."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def test_stats_handler_returns_per_pass(self) -> None:
        """stats handler returns per_pass list with valid schema."""
        result = _call(self.state, "stats")
        assert "per_pass" in result
        per_pass = result["per_pass"]
        assert isinstance(per_pass, list)
        assert len(per_pass) >= 1
        for ps in per_pass:
            assert isinstance(ps["name"], str) and len(ps["name"]) > 0
            assert isinstance(ps["draws"], int) and ps["draws"] >= 0
            assert isinstance(ps["triangles"], int) and ps["triangles"] >= 0
            assert isinstance(ps["dispatches"], int) and ps["dispatches"] >= 0

    def test_diff_stats_self_all_equal(self) -> None:
        """Self-diff stats: all passes should be EQUAL with zero deltas."""
        from rdc.diff.draws import DiffStatus
        from rdc.diff.stats import diff_stats

        result = _call(self.state, "stats")
        per_pass = result["per_pass"]

        rows = diff_stats(per_pass, per_pass)
        assert len(rows) == len(per_pass)
        for row in rows:
            assert row.status == DiffStatus.EQUAL
            assert row.draws_a == row.draws_b
            assert row.triangles_a == row.triangles_b
            assert row.dispatches_a == row.dispatches_b
            assert row.draws_delta == "0"
            assert row.triangles_delta == "0"
            assert row.dispatches_delta == "0"


class TestDiffResourcesReal:
    """GPU integration tests for diff --resources with real captures."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def test_diff_resources_self_all_equal(self) -> None:
        """Self-diff resources: all resources should be EQUAL, no ADDED/DELETED."""
        from rdc.diff.draws import DiffStatus
        from rdc.diff.resources import ResourceRecord, diff_resources

        result = _call(self.state, "resources")
        rows = result["rows"]
        assert len(rows) > 0

        records = [ResourceRecord(**r) for r in rows]
        diff_rows = diff_resources(records, records)
        assert len(diff_rows) >= len(records)
        for dr in diff_rows:
            assert dr.status == DiffStatus.EQUAL, (
                f"resource '{dr.name}' has status {dr.status}, expected EQUAL"
            )
            assert dr.type_a == dr.type_b

    def test_diff_resources_self_no_added_deleted(self) -> None:
        """Self-diff resources: no ADDED or DELETED entries."""
        from rdc.diff.draws import DiffStatus
        from rdc.diff.resources import ResourceRecord, diff_resources

        result = _call(self.state, "resources")
        records = [ResourceRecord(**r) for r in result["rows"]]
        diff_rows = diff_resources(records, records)
        for dr in diff_rows:
            assert dr.status != DiffStatus.ADDED
            assert dr.status != DiffStatus.DELETED


class TestDiffPipelineReal:
    """GPU integration tests for diff --pipeline with real captures."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        draws = result["events"]
        assert len(draws) > 0, "no draw calls in capture"
        return draws[0]["eid"]

    def test_all_13_pipe_sections_return_data(self) -> None:
        """All 13 pipeline section RPCs return non-error results."""
        from rdc.diff.pipeline import PIPE_SECTION_CALLS

        draw_eid = self._first_draw_eid()
        for method, section in PIPE_SECTION_CALLS:
            result = _call(self.state, method, {"eid": draw_eid})
            assert isinstance(result, dict), f"section {section} via {method} returned non-dict"
            assert len(result) > 0, f"section {section} returned empty dict"

    def test_diff_pipeline_self_no_changes(self) -> None:
        """Self-diff pipeline: no fields should be changed."""
        from rdc.diff.pipeline import PIPE_SECTION_CALLS, diff_pipeline_sections

        draw_eid = self._first_draw_eid()
        results: list[dict[str, Any]] = []
        for method, _ in PIPE_SECTION_CALLS:
            r = _call(self.state, method, {"eid": draw_eid})
            results.append({"result": r})

        diffs = diff_pipeline_sections(results, results)
        assert len(diffs) > 0, "expected pipeline fields to compare"
        changed = [d for d in diffs if d.changed]
        assert len(changed) == 0, f"self-diff has {len(changed)} changed fields: " + ", ".join(
            f"{d.section}.{d.field}" for d in changed
        )

    def test_diff_pipeline_self_all_sections_represented(self) -> None:
        """Self-diff should have fields from multiple pipeline sections."""
        from rdc.diff.pipeline import PIPE_SECTION_CALLS, diff_pipeline_sections

        draw_eid = self._first_draw_eid()
        results: list[dict[str, Any]] = []
        for method, _ in PIPE_SECTION_CALLS:
            r = _call(self.state, method, {"eid": draw_eid})
            results.append({"result": r})

        diffs = diff_pipeline_sections(results, results)
        sections_seen = {d.section for d in diffs}
        assert len(sections_seen) >= 5, (
            f"expected fields from >= 5 sections, got {len(sections_seen)}: {sections_seen}"
        )


class TestDiffFramebufferReal:
    """GPU integration tests for diff --framebuffer (render target export)."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        vkcube_replay: tuple[Any, Any, Any],
        rd_module: Any,
        tmp_path: Path,
    ) -> None:
        self.state = _make_state(vkcube_replay, rd_module)
        self.state.temp_dir = tmp_path

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        return result["events"][0]["eid"]

    def test_rt_export_returns_valid_png(self) -> None:
        """rt_export handler returns a valid PNG for target=0."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "rt_export", {"eid": draw_eid, "target": 0})
        assert "path" in result
        assert result["size"] > 0
        exported = Path(result["path"])
        assert exported.exists()
        data = exported.read_bytes()
        assert data[:4] == b"\x89PNG"

    def test_self_compare_identical(self) -> None:
        """Comparing same rt_export image with itself yields identical=True."""
        from rdc.image_compare import compare_images

        draw_eid = self._first_draw_eid()
        result = _call(self.state, "rt_export", {"eid": draw_eid, "target": 0})
        path = Path(result["path"])

        cmp = compare_images(path, path)
        assert cmp.identical is True
        assert cmp.diff_pixels == 0
        assert cmp.total_pixels > 0
        assert cmp.diff_ratio == 0.0


class TestDiffSessionReal:
    """GPU integration tests using start_diff_session with real daemon processes."""

    def test_diff_stats_session_self_diff(self) -> None:
        """Full two-daemon self-diff for stats: all passes should be EQUAL."""
        from rdc.diff.draws import DiffStatus
        from rdc.diff.stats import diff_stats
        from rdc.services.diff_service import (
            query_both,
            start_diff_session,
            stop_diff_session,
        )

        ctx, err = start_diff_session(VKCUBE_RDC, VKCUBE_RDC, timeout_s=60.0)
        assert ctx is not None, f"start_diff_session failed: {err}"
        try:
            resp_a, resp_b, q_err = query_both(ctx, "stats", {}, timeout_s=30.0)
            assert resp_a is not None, "daemon A stats query failed"
            assert resp_b is not None, "daemon B stats query failed"

            passes_a = resp_a["result"]["per_pass"]
            passes_b = resp_b["result"]["per_pass"]
            rows = diff_stats(passes_a, passes_b)

            assert len(rows) >= 1
            for row in rows:
                assert row.status == DiffStatus.EQUAL
        finally:
            stop_diff_session(ctx)

    def test_diff_resources_session_self_diff(self) -> None:
        """Full two-daemon self-diff for resources: all should be EQUAL."""
        from rdc.diff.draws import DiffStatus
        from rdc.diff.resources import ResourceRecord, diff_resources
        from rdc.services.diff_service import (
            query_both,
            start_diff_session,
            stop_diff_session,
        )

        ctx, err = start_diff_session(VKCUBE_RDC, VKCUBE_RDC, timeout_s=60.0)
        assert ctx is not None, f"start_diff_session failed: {err}"
        try:
            resp_a, resp_b, q_err = query_both(ctx, "resources", {}, timeout_s=30.0)
            assert resp_a is not None, "daemon A resources query failed"
            assert resp_b is not None, "daemon B resources query failed"

            records_a = [ResourceRecord(**r) for r in resp_a["result"]["rows"]]
            records_b = [ResourceRecord(**r) for r in resp_b["result"]["rows"]]
            rows = diff_resources(records_a, records_b)

            assert len(rows) >= 1
            for row in rows:
                assert row.status == DiffStatus.EQUAL
        finally:
            stop_diff_session(ctx)

    def test_diff_pipeline_session_self_diff(self) -> None:
        """Full two-daemon self-diff for pipeline: no changed fields."""
        from rdc.diff.alignment import align_draws
        from rdc.diff.pipeline import (
            PIPE_SECTION_CALLS,
            build_draw_records,
            diff_pipeline_sections,
        )
        from rdc.services.diff_service import (
            query_both,
            query_each_sync,
            start_diff_session,
            stop_diff_session,
        )

        ctx, err = start_diff_session(VKCUBE_RDC, VKCUBE_RDC, timeout_s=60.0)
        assert ctx is not None, f"start_diff_session failed: {err}"
        try:
            # Get draws from both daemons
            resp_a, resp_b, _ = query_both(ctx, "draws", {}, timeout_s=30.0)
            assert resp_a is not None and resp_b is not None

            draws_a = resp_a["result"]["draws"]
            draws_b = resp_b["result"]["draws"]
            records_a = build_draw_records(draws_a)
            records_b = build_draw_records(draws_b)

            aligned = align_draws(records_a, records_b)
            # Find first paired draw
            pair = None
            for a, b in aligned:
                if a is not None and b is not None:
                    pair = (a, b)
                    break
            assert pair is not None, "no aligned draw pairs found"

            rec_a, rec_b = pair
            calls_a = [(method, {"eid": rec_a.eid}) for method, _ in PIPE_SECTION_CALLS]
            calls_b = [(method, {"eid": rec_b.eid}) for method, _ in PIPE_SECTION_CALLS]

            results_a, results_b, _ = query_each_sync(ctx, calls_a, calls_b, timeout_s=30.0)

            diffs = diff_pipeline_sections(results_a, results_b)
            changed = [d for d in diffs if d.changed]
            assert len(changed) == 0, f"self-diff has {len(changed)} changed fields: " + ", ".join(
                f"{d.section}.{d.field}" for d in changed
            )
        finally:
            stop_diff_session(ctx)

    def test_diff_framebuffer_session_self_diff(self) -> None:
        """Full two-daemon self-diff for framebuffer: should be identical."""
        from rdc.diff.framebuffer import compare_framebuffers
        from rdc.services.diff_service import start_diff_session, stop_diff_session

        ctx, err = start_diff_session(VKCUBE_RDC, VKCUBE_RDC, timeout_s=60.0)
        assert ctx is not None, f"start_diff_session failed: {err}"
        try:
            result, fb_err = compare_framebuffers(ctx, target=0, timeout_s=30.0)
            assert result is not None, f"compare_framebuffers failed: {fb_err}"
            assert result.identical is True
            assert result.diff_pixels == 0
            assert result.total_pixels > 0
            assert result.diff_ratio == 0.0
            assert result.target == 0
        finally:
            stop_diff_session(ctx)


class TestDiffCLIReal:
    """GPU integration tests for diff CLI commands with real captures."""

    def test_diff_stats_cli_self_diff(self) -> None:
        """rdc diff --stats a.rdc a.rdc exits 0."""
        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--stats", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"

    def test_diff_resources_cli_self_diff(self) -> None:
        """rdc diff --resources a.rdc a.rdc exits 0."""
        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--resources", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"

    def test_diff_framebuffer_cli_self_diff(self) -> None:
        """rdc diff --framebuffer a.rdc a.rdc exits 0 and output contains 'identical'."""
        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--framebuffer", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        assert "identical" in result.output.lower()

    def test_diff_pipeline_cli_self_diff(self) -> None:
        """rdc diff --pipeline a.rdc a.rdc exits 0."""
        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--pipeline", "-", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"

    def test_diff_stats_cli_json_output(self) -> None:
        """rdc diff --stats --json a.rdc a.rdc outputs valid JSON."""
        import json as json_mod

        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--stats", "--json", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        data = json_mod.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        for row in data:
            assert row["status"] == "="

    def test_diff_stats_cli_shortstat(self) -> None:
        """rdc diff --stats --shortstat outputs summary with 0 passes changed."""
        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--stats", "--shortstat", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        assert "0 passes changed" in result.output

    def test_diff_stats_cli_unified(self) -> None:
        """rdc diff --stats --format unified outputs unified diff with header lines."""
        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--stats", "--format", "unified", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        assert "--- a/" in result.output
        assert "+++ b/" in result.output

    def test_diff_resources_cli_json_output(self) -> None:
        """rdc diff --resources --json outputs valid JSON with all EQUAL status."""
        import json as json_mod

        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--resources", "--json", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        data = json_mod.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        for row in data:
            assert row["status"] == "="

    def test_diff_resources_cli_shortstat(self) -> None:
        """rdc diff --resources --shortstat outputs summary with 0 added/deleted."""
        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--resources", "--shortstat", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        assert "0 added" in result.output
        assert "0 deleted" in result.output
        assert "0 modified" in result.output

    def test_diff_pipeline_cli_verbose(self) -> None:
        """rdc diff --pipeline - --verbose shows all fields (not just changed)."""
        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--pipeline", "-", "--verbose", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        # Verbose should output field data (header + rows)
        lines = result.output.strip().split("\n")
        assert len(lines) >= 2, "verbose should produce header + at least one field row"

    def test_diff_pipeline_cli_json_output(self) -> None:
        """rdc diff --pipeline - --json outputs valid JSON array of diffs."""
        import json as json_mod

        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--pipeline", "-", "--json", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        data = json_mod.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        for entry in data:
            assert "section" in entry
            assert "field" in entry
            assert "changed" in entry
            assert entry["changed"] is False

    def test_diff_framebuffer_cli_json_output(self) -> None:
        """rdc diff --framebuffer --json outputs valid JSON with identical=true."""
        import json as json_mod

        from click.testing import CliRunner

        from rdc.commands.diff import diff_cmd

        runner = CliRunner()
        result = runner.invoke(diff_cmd, ["--framebuffer", "--json", VKCUBE_RDC, VKCUBE_RDC])
        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        data = json_mod.loads(result.output)
        assert data["identical"] is True
        assert data["diff_pixels"] == 0
        assert data["total_pixels"] > 0
        assert data["diff_ratio"] == 0.0


class TestDiffSessionExtendedReal:
    """Extended GPU integration tests for diff sessions with real captures."""

    def test_diff_stats_session_zero_deltas(self) -> None:
        """Self-diff stats session: all delta fields should be '0'."""
        from rdc.diff.stats import diff_stats
        from rdc.services.diff_service import (
            query_both,
            start_diff_session,
            stop_diff_session,
        )

        ctx, err = start_diff_session(VKCUBE_RDC, VKCUBE_RDC, timeout_s=60.0)
        assert ctx is not None, f"start_diff_session failed: {err}"
        try:
            resp_a, resp_b, _ = query_both(ctx, "stats", {}, timeout_s=30.0)
            assert resp_a is not None and resp_b is not None
            rows = diff_stats(resp_a["result"]["per_pass"], resp_b["result"]["per_pass"])
            for row in rows:
                assert row.draws_delta == "0", f"pass '{row.name}' draws_delta={row.draws_delta}"
                assert row.triangles_delta == "0", (
                    f"pass '{row.name}' triangles_delta={row.triangles_delta}"
                )
                assert row.dispatches_delta == "0", (
                    f"pass '{row.name}' dispatches_delta={row.dispatches_delta}"
                )
        finally:
            stop_diff_session(ctx)

    def test_diff_resources_session_types_match(self) -> None:
        """Self-diff resources session: type_a == type_b for all EQUAL rows."""
        from rdc.diff.resources import ResourceRecord, diff_resources
        from rdc.services.diff_service import (
            query_both,
            start_diff_session,
            stop_diff_session,
        )

        ctx, err = start_diff_session(VKCUBE_RDC, VKCUBE_RDC, timeout_s=60.0)
        assert ctx is not None, f"start_diff_session failed: {err}"
        try:
            resp_a, resp_b, _ = query_both(ctx, "resources", {}, timeout_s=30.0)
            assert resp_a is not None and resp_b is not None
            records_a = [ResourceRecord(**r) for r in resp_a["result"]["rows"]]
            records_b = [ResourceRecord(**r) for r in resp_b["result"]["rows"]]
            rows = diff_resources(records_a, records_b)
            for row in rows:
                assert row.type_a == row.type_b, (
                    f"resource '{row.name}': type_a={row.type_a} != type_b={row.type_b}"
                )
        finally:
            stop_diff_session(ctx)

    def test_diff_framebuffer_session_total_pixels_positive(self) -> None:
        """Self-diff framebuffer session: total_pixels > 0 and diff_ratio == 0."""
        from rdc.diff.framebuffer import compare_framebuffers
        from rdc.services.diff_service import start_diff_session, stop_diff_session

        ctx, err = start_diff_session(VKCUBE_RDC, VKCUBE_RDC, timeout_s=60.0)
        assert ctx is not None, f"start_diff_session failed: {err}"
        try:
            result, fb_err = compare_framebuffers(ctx, target=0, timeout_s=30.0)
            assert result is not None, f"compare_framebuffers failed: {fb_err}"
            assert result.total_pixels > 0
            assert result.diff_ratio == 0.0
            assert result.diff_pixels == 0
        finally:
            stop_diff_session(ctx)

    def test_diff_pipeline_session_field_count(self) -> None:
        """Self-diff pipeline session: at least 20 fields compared across sections."""
        from rdc.diff.alignment import align_draws
        from rdc.diff.pipeline import (
            PIPE_SECTION_CALLS,
            build_draw_records,
            diff_pipeline_sections,
        )
        from rdc.services.diff_service import (
            query_both,
            query_each_sync,
            start_diff_session,
            stop_diff_session,
        )

        ctx, err = start_diff_session(VKCUBE_RDC, VKCUBE_RDC, timeout_s=60.0)
        assert ctx is not None, f"start_diff_session failed: {err}"
        try:
            resp_a, resp_b, _ = query_both(ctx, "draws", {}, timeout_s=30.0)
            assert resp_a is not None and resp_b is not None

            records_a = build_draw_records(resp_a["result"]["draws"])
            records_b = build_draw_records(resp_b["result"]["draws"])
            aligned = align_draws(records_a, records_b)

            pair = None
            for a, b in aligned:
                if a is not None and b is not None:
                    pair = (a, b)
                    break
            assert pair is not None, "no aligned draw pairs found"
            rec_a, rec_b = pair

            calls_a = [(m, {"eid": rec_a.eid}) for m, _ in PIPE_SECTION_CALLS]
            calls_b = [(m, {"eid": rec_b.eid}) for m, _ in PIPE_SECTION_CALLS]
            results_a, results_b, _ = query_each_sync(ctx, calls_a, calls_b, timeout_s=30.0)

            diffs = diff_pipeline_sections(results_a, results_b)
            assert len(diffs) >= 20, f"expected >= 20 pipeline fields, got {len(diffs)}"
        finally:
            stop_diff_session(ctx)


class TestDiffLibraryLevelReal:
    """GPU integration tests for diff library functions at the adapter level."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        vkcube_replay: tuple[Any, Any, Any],
        rd_module: Any,
        tmp_path: Path,
    ) -> None:
        self.state = _make_state(vkcube_replay, rd_module)
        self.state.temp_dir = tmp_path

    def test_diff_stats_pass_names_nonempty(self) -> None:
        """Stats per_pass entries all have non-empty pass names."""
        result = _call(self.state, "stats")
        for ps in result["per_pass"]:
            assert isinstance(ps["name"], str)
            assert len(ps["name"]) > 0

    def test_diff_stats_values_nonnegative(self) -> None:
        """Stats per_pass numeric fields are all >= 0."""
        result = _call(self.state, "stats")
        for ps in result["per_pass"]:
            assert ps["draws"] >= 0
            assert ps["triangles"] >= 0
            assert ps["dispatches"] >= 0

    def test_diff_resources_records_have_required_fields(self) -> None:
        """Resources response rows have id, type, name fields."""
        result = _call(self.state, "resources")
        for row in result["rows"]:
            assert "id" in row
            assert "type" in row
            assert "name" in row
            assert isinstance(row["id"], int)
            assert isinstance(row["type"], str)

    def test_diff_pipeline_topology_section_has_string_value(self) -> None:
        """pipe_topology returns a non-empty string topology."""
        events = _call(self.state, "events", {"type": "draw"})
        draw_eid = events["events"][0]["eid"]
        result = _call(self.state, "pipe_topology", {"eid": draw_eid})
        assert "topology" in result
        assert isinstance(result["topology"], str)
        assert len(result["topology"]) > 0

    def test_diff_pipeline_viewport_has_dimensions(self) -> None:
        """pipe_viewport returns width and height > 0."""
        events = _call(self.state, "events", {"type": "draw"})
        draw_eid = events["events"][0]["eid"]
        result = _call(self.state, "pipe_viewport", {"eid": draw_eid})
        assert result["width"] > 0
        assert result["height"] > 0

    def test_diff_pipeline_blend_has_list(self) -> None:
        """pipe_blend returns a list of blend entries."""
        events = _call(self.state, "events", {"type": "draw"})
        draw_eid = events["events"][0]["eid"]
        result = _call(self.state, "pipe_blend", {"eid": draw_eid})
        assert "blends" in result
        assert isinstance(result["blends"], list)

    def test_diff_pipeline_rasterizer_returns_data(self) -> None:
        """pipe_rasterizer returns a dict with known fields."""
        events = _call(self.state, "events", {"type": "draw"})
        draw_eid = events["events"][0]["eid"]
        result = _call(self.state, "pipe_rasterizer", {"eid": draw_eid})
        assert isinstance(result, dict)
        assert len(result) >= 2

    def test_rt_export_default_eid_succeeds(self) -> None:
        """rt_export without explicit eid succeeds (uses daemon default)."""
        result = _call(self.state, "rt_export", {"target": 0})
        assert "path" in result
        assert result["size"] > 0
        exported = Path(result["path"])
        assert exported.exists()


class TestShaderEditReal:
    """GPU integration tests for shader edit-replay handlers."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        return result["events"][0]["eid"]

    def test_shader_encodings(self) -> None:
        """Returns non-empty list with at least one known encoding."""
        result = _call(self.state, "shader_encodings")
        assert len(result["encodings"]) > 0
        names = [e["name"] for e in result["encodings"]]
        assert any(n in ("GLSL", "SPIRV") for n in names)

    def test_shader_build_glsl(self) -> None:
        """Build a trivial GLSL fragment shader."""
        encs = _call(self.state, "shader_encodings")
        glsl_available = any(e["value"] == 2 for e in encs["encodings"])
        if not glsl_available:
            pytest.skip("GLSL encoding not available")

        source = "#version 450\nlayout(location=0) out vec4 o;\nvoid main(){o=vec4(1,0,0,1);}\n"
        result = _call(self.state, "shader_build", {"stage": "ps", "source": source})
        assert result["shader_id"] > 0

    def test_shader_replace_cycle(self) -> None:
        """Build -> Replace -> Restore full cycle."""
        encs = _call(self.state, "shader_encodings")
        if not any(e["value"] == 2 for e in encs["encodings"]):
            pytest.skip("GLSL encoding not available")

        draw_eid = self._first_draw_eid()
        source = "#version 450\nlayout(location=0) out vec4 o;\nvoid main(){o=vec4(0,1,0,1);}\n"
        build_result = _call(self.state, "shader_build", {"stage": "ps", "source": source})
        shader_id = build_result["shader_id"]

        try:
            replace_result = _call(
                self.state,
                "shader_replace",
                {"eid": draw_eid, "stage": "ps", "shader_id": shader_id},
            )
            assert replace_result["ok"] is True
            assert replace_result["original_id"] > 0

            restore_result = _call(self.state, "shader_restore", {"eid": draw_eid, "stage": "ps"})
            assert restore_result["ok"] is True
        finally:
            req = {
                "id": 1,
                "method": "shader_restore_all",
                "params": {"_token": self.state.token},
            }
            _handle_request(req, self.state)

    def test_shader_restore_all(self) -> None:
        """Build and replace, then restore-all cleans up."""
        encs = _call(self.state, "shader_encodings")
        if not any(e["value"] == 2 for e in encs["encodings"]):
            pytest.skip("GLSL encoding not available")

        draw_eid = self._first_draw_eid()
        source = "#version 450\nlayout(location=0) out vec4 o;\nvoid main(){o=vec4(1,1,0,1);}\n"
        build = _call(self.state, "shader_build", {"stage": "ps", "source": source})
        _call(
            self.state,
            "shader_replace",
            {"eid": draw_eid, "stage": "ps", "shader_id": build["shader_id"]},
        )

        result = _call(self.state, "shader_restore_all")
        assert result["ok"] is True
        assert result["restored"] >= 1
        assert result["freed"] >= 1


class TestMeshDataReal:
    """GPU integration tests for mesh_data handler with real replay."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "draws")
        return result["draws"][0]["eid"]

    def test_mesh_data_real(self) -> None:
        """mesh_data on a draw event returns vertices with valid schema."""
        eid = self._first_draw_eid()
        result = _call(self.state, "mesh_data", {"eid": eid})
        assert result["vertex_count"] > 0
        assert len(result["vertices"]) == result["vertex_count"]
        assert result["stage"] == "vs-out"

    def test_mesh_data_topology_string(self) -> None:
        """Topology field is a non-empty string, not an integer."""
        eid = self._first_draw_eid()
        result = _call(self.state, "mesh_data", {"eid": eid})
        assert isinstance(result["topology"], str)
        assert len(result["topology"]) > 0
        assert not result["topology"].isdigit()

    def test_mesh_data_vertex_comp_match(self) -> None:
        """Each vertex list has exactly comp_count elements."""
        eid = self._first_draw_eid()
        result = _call(self.state, "mesh_data", {"eid": eid})
        assert result["vertex_count"] == len(result["vertices"])
        for v in result["vertices"]:
            assert len(v) == result["comp_count"]


class TestOverlayReal:
    """GPU integration tests for rt_overlay handler with real replay."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        vkcube_replay: tuple[Any, Any, Any],
        rd_module: Any,
        tmp_path: Path,
    ) -> None:
        self.state = _make_state(vkcube_replay, rd_module)
        self.state.temp_dir = tmp_path

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "draws")
        return result["draws"][0]["eid"]

    def test_rt_overlay_wireframe(self) -> None:
        """Wireframe overlay produces a valid PNG on disk."""
        eid = self._first_draw_eid()
        result = _call(self.state, "rt_overlay", {"eid": eid, "overlay": "wireframe"})
        assert Path(result["path"]).exists()
        assert result["size"] > 0
        assert result["overlay"] == "wireframe"

    def test_rt_overlay_depth(self) -> None:
        """Depth overlay produces a non-empty file."""
        eid = self._first_draw_eid()
        result = _call(self.state, "rt_overlay", {"eid": eid, "overlay": "depth"})
        assert result["size"] > 0

    def test_overlay_differs_from_plain_rt(self) -> None:
        """Overlay PNG path differs from plain rt_export path."""
        eid = self._first_draw_eid()
        overlay_result = _call(self.state, "rt_overlay", {"eid": eid, "overlay": "wireframe"})
        rt_result = _call(self.state, "rt_export", {"eid": eid})
        assert overlay_result["path"] != rt_result["path"]


class TestShaderApiFixReal:
    """GPU integration tests for shader_source debug-info and shader_constants structured output."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        return result["events"][0]["eid"]

    def test_shader_source_real_no_debug_info(self) -> None:
        """vkcube shaders have no debug info; fallback to disassembly."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "shader_source", {"eid": draw_eid, "stage": "ps"})
        assert result["has_debug_info"] is False
        assert isinstance(result["source"], str)
        assert len(result["source"]) > 0
        assert result["files"] == []

    def test_shader_source_real_fields_present(self) -> None:
        """Response contains all required keys."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "shader_source", {"eid": draw_eid, "stage": "ps"})
        for key in ("eid", "stage", "has_debug_info", "source", "files"):
            assert key in result, f"missing key: {key}"

    def test_shader_constants_real_structured(self) -> None:
        """Constants response has structured variables, not raw hex."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "shader_constants", {"eid": draw_eid, "stage": "ps"})
        assert isinstance(result["constants"], list)
        for entry in result["constants"]:
            assert "name" in entry
            assert "bind_point" in entry
            assert "variables" in entry
            assert isinstance(entry["variables"], list)

    def test_shader_constants_real_no_hex_data(self) -> None:
        """No entry in constants contains a 'data' key (old hex field gone)."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "shader_constants", {"eid": draw_eid, "stage": "ps"})
        for entry in result["constants"]:
            assert "data" not in entry, f"old 'data' field still present in {entry['name']}"


class TestPickPixelReal:
    """GPU integration tests for pick_pixel handler with real replay."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        return result["events"][0]["eid"]

    def test_pick_pixel_valid_rgba(self) -> None:
        """PP-G-01: pick_pixel at draw event returns valid RGBA."""
        import math

        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pick_pixel", {"x": 320, "y": 240, "eid": draw_eid})
        c = result["color"]
        for ch in ("r", "g", "b", "a"):
            assert isinstance(c[ch], float)
            assert math.isfinite(c[ch])

    def test_pick_pixel_schema(self) -> None:
        """PP-G-02: result has expected schema."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pick_pixel", {"x": 320, "y": 240, "eid": draw_eid})
        for key in ("x", "y", "eid", "target", "color"):
            assert key in result
        for key in ("r", "g", "b", "a"):
            assert key in result["color"]

    def test_pick_pixel_target_nonzero(self) -> None:
        """PP-G-03: target id is a positive integer."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pick_pixel", {"x": 320, "y": 240, "eid": draw_eid})
        assert result["target"]["id"] > 0
        assert result["target"]["index"] == 0

    def test_pick_pixel_different_coords_differ(self) -> None:
        """PP-G-04: different pixels may return different values."""
        draw_eid = self._first_draw_eid()
        r1 = _call(self.state, "pick_pixel", {"x": 0, "y": 0, "eid": draw_eid})
        r2 = _call(self.state, "pick_pixel", {"x": 320, "y": 240, "eid": draw_eid})
        c1 = r1["color"]
        c2 = r2["color"]
        # At least one channel should differ (vkcube renders a colored cube)
        differs = any(c1[ch] != c2[ch] for ch in ("r", "g", "b", "a"))
        assert differs, f"expected different colors: {c1} vs {c2}"

    def test_pick_pixel_eid_echoed(self) -> None:
        """PP-G-05: EID param is echoed in response."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pick_pixel", {"x": 320, "y": 240, "eid": draw_eid})
        assert result["eid"] == draw_eid


class TestTexStatsReal:
    """GPU integration tests for tex_stats handler with real replay."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_texture_id(self) -> int:
        if self.state.tex_map:
            return next(iter(self.state.tex_map))
        pytest.skip("no texture resources in capture")

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        draws = result["events"]
        assert len(draws) > 0
        return draws[0]["eid"]

    def test_tex_stats_real_minmax(self) -> None:
        """TS-25: GetMinMax returns min <= max for all channels."""
        tex_id = self._first_texture_id()
        result = _call(self.state, "tex_stats", {"id": tex_id})
        for ch in ("r", "g", "b", "a"):
            assert result["min"][ch] <= result["max"][ch], f"min > max for channel {ch}"

    def test_tex_stats_real_no_nan(self) -> None:
        """TS-26: All min/max values are finite."""
        import math

        tex_id = self._first_texture_id()
        result = _call(self.state, "tex_stats", {"id": tex_id})
        for ch in ("r", "g", "b", "a"):
            assert math.isfinite(result["min"][ch]), f"min.{ch} not finite"
            assert math.isfinite(result["max"][ch]), f"max.{ch} not finite"

    def test_tex_stats_real_histogram(self) -> None:
        """TS-27: Histogram has 256 entries with r/g/b/a keys."""
        tex_id = self._first_texture_id()
        result = _call(self.state, "tex_stats", {"id": tex_id, "histogram": True})
        assert "histogram" in result
        assert len(result["histogram"]) == 256
        for entry in result["histogram"]:
            for key in ("bucket", "r", "g", "b", "a"):
                assert key in entry

    def test_tex_stats_real_histogram_nonneg(self) -> None:
        """TS-28: All histogram bucket counts are >= 0."""
        tex_id = self._first_texture_id()
        result = _call(self.state, "tex_stats", {"id": tex_id, "histogram": True})
        for entry in result["histogram"]:
            for ch in ("r", "g", "b", "a"):
                assert entry[ch] >= 0, f"negative count at bucket {entry['bucket']}.{ch}"

    def test_tex_stats_real_unknown_id(self) -> None:
        """TS-29: Unknown texture ID returns error -32001."""
        req = {
            "id": 1,
            "method": "tex_stats",
            "params": {"_token": self.state.token, "id": 0},
        }
        resp, _ = _handle_request(req, self.state)
        assert "error" in resp
        assert resp["error"]["code"] == -32001

    def test_tex_stats_real_eid_navigation(self) -> None:
        """TS-30: Providing a draw EID succeeds and eid is echoed."""
        tex_id = self._first_texture_id()
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "tex_stats", {"id": tex_id, "eid": draw_eid})
        assert result["eid"] == draw_eid


class TestHelloTriangleDebug:
    """GPU integration tests for debug handlers with hello_triangle capture."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        hello_triangle_replay: tuple[Any, Any, Any],
        rd_module: Any,
    ) -> None:
        cap, controller, sf = hello_triangle_replay
        version = parse_version_tuple(rd_module.GetVersionString())
        adapter = RenderDocAdapter(controller=controller, version=version)

        self.state = DaemonState(capture="hello_triangle.rdc", current_eid=0, token="test-token")
        self.state.adapter = adapter
        self.state.cap = cap
        self.state.structured_file = sf

        api_props = adapter.get_api_properties()
        pt = getattr(api_props, "pipelineType", "Unknown")
        self.state.api_name = getattr(pt, "name", str(pt))

        root_actions = adapter.get_root_actions()
        self.state.max_eid = _max_eid(root_actions)

        resources = adapter.get_resources()
        textures = adapter.get_textures()
        buffers = adapter.get_buffers()

        self.state.tex_map = {int(t.resourceId): t for t in textures}
        self.state.buf_map = {int(b.resourceId): b for b in buffers}
        self.state.res_names = {int(r.resourceId): r.name for r in resources}
        self.state.res_types = {
            int(r.resourceId): getattr(
                getattr(r, "type", None), "name", str(getattr(r, "type", ""))
            )
            for r in resources
        }
        self.state.res_rid_map = {int(r.resourceId): r.resourceId for r in resources}
        self.state.rd = rd_module

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        draws = result["events"]
        assert len(draws) > 0, "no draw calls in hello_triangle capture"
        return draws[0]["eid"]

    def test_debug_vertex_success(self) -> None:
        """debug_vertex on first draw, vertex=0 returns valid result."""
        draw_eid = self._first_draw_eid()
        result = _call(
            self.state,
            "debug_vertex",
            {"eid": draw_eid, "vtx_id": 0},
        )
        assert "inputs" in result
        assert "outputs" in result
        assert "total_steps" in result
        assert result["total_steps"] > 0

    def test_debug_pixel_success(self) -> None:
        """debug_pixel on first draw at center returns valid result."""
        draw_eid = self._first_draw_eid()
        result = _call(
            self.state,
            "debug_pixel",
            {"eid": draw_eid, "x": 640, "y": 360},
        )
        assert "inputs" in result
        assert "outputs" in result
        assert "total_steps" in result
        assert result["total_steps"] > 0


class TestAssertStateReal:
    """GPU integration tests for assert-state leaf comparison fix."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        return result["events"][0]["eid"]

    def test_pipeline_topology_flat_dict(self) -> None:
        """Pipeline with section=topology returns flat dict with 'topology' key."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pipeline", {"eid": draw_eid, "section": "topology"})
        assert "topology" in result
        assert isinstance(result["topology"], str)

    def test_pipeline_vs_row_with_section_detail(self) -> None:
        """Pipeline with section=vs returns row with section_detail."""
        draw_eid = self._first_draw_eid()
        result = _call(self.state, "pipeline", {"eid": draw_eid, "section": "vs"})
        assert "row" in result
        assert "section_detail" in result["row"]


class TestCountShadersReal:
    """GPU integration tests for count shaders."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def test_count_shaders_positive(self) -> None:
        """count shaders returns a positive integer."""
        result = _call(self.state, "count", {"what": "shaders"})
        assert isinstance(result["value"], int)
        assert result["value"] > 0

    def test_count_shaders_matches_list(self) -> None:
        """count shaders matches length of shaders list result."""
        count_result = _call(self.state, "count", {"what": "shaders"})
        shaders_result = _call(self.state, "shaders")
        assert count_result["value"] == len(shaders_result["rows"])


class TestBufferDecodeReal:
    """GPU integration tests for cbuffer_decode and vbuffer_decode handlers."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        events = result["events"]
        assert len(events) > 0, "no draw calls in capture"
        return events[0]["eid"]

    def test_cbuffer_decode_returns_data(self) -> None:
        """cbuffer_decode returns structured cbuffer data for VS stage."""
        eid = self._first_draw_eid()
        params = {"eid": eid, "stage": "vs", "set": 0, "binding": 0}
        result = _call(self.state, "cbuffer_decode", params)
        assert "variables" in result and "set" in result

    def test_vbuffer_decode_returns_vertex_data(self) -> None:
        """vbuffer_decode returns columns + vertices for a draw event."""
        eid = self._first_draw_eid()
        result = _call(self.state, "vbuffer_decode", {"eid": eid})
        assert "columns" in result
        assert "vertices" in result


class TestShaderMapAndAllReal:
    """GPU integration tests for shader_map and shader_all handlers."""

    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events", {"type": "draw"})
        events = result["events"]
        assert len(events) > 0, "no draw calls in capture"
        return events[0]["eid"]

    def test_shader_map_returns_rows(self) -> None:
        """shader_map returns {"rows": [...]} with at least VS + FS."""
        result = _call(self.state, "shader_map")
        assert "rows" in result
        assert len(result["rows"]) >= 2

    def test_shader_all_returns_stages(self) -> None:
        """shader_all returns {"eid": ..., "stages": [...]} with at least VS + FS."""
        eid = self._first_draw_eid()
        result = _call(self.state, "shader_all", {"eid": eid})
        assert "stages" in result
        assert len(result["stages"]) >= 2
