"""E2E tests for query commands (category 3).

All tests in this module require a vkcube.rdc daemon session and a
working RenderDoc installation. The capture has 6 events, 1 draw call
(EID 11), 46 resources, 2 shaders (111=vs, 112=ps).
"""

from __future__ import annotations

import re

import pytest
from e2e_helpers import rdc, rdc_fail, rdc_ok

pytestmark = pytest.mark.gpu


class TestInfo:
    """3.1: rdc info."""

    def test_contains_capture_metadata(self, vkcube_session: str) -> None:
        """``rdc info`` outputs API type, event count, and draw count."""
        out = rdc_ok("info", session=vkcube_session)
        assert "Vulkan" in out
        assert "Events" in out or "events" in out
        assert "Draw" in out or "draw" in out


class TestStats:
    """3.2: rdc stats."""

    def test_contains_per_pass_breakdown(self, vkcube_session: str) -> None:
        """``rdc stats`` includes per-pass breakdown section (header on stderr)."""
        result = rdc("stats", session=vkcube_session)
        assert result.returncode == 0, f"rdc stats failed:\n{result.stderr}"
        combined = result.stdout + result.stderr
        assert "Per-Pass Breakdown" in combined


class TestLog:
    """3.3: rdc log."""

    def test_tsv_header_present(self, vkcube_session: str) -> None:
        """``rdc log`` outputs TSV with LEVEL, EID, MESSAGE header."""
        out = rdc_ok("log", session=vkcube_session)
        assert "LEVEL" in out
        assert "EID" in out
        assert "MESSAGE" in out


class TestEvents:
    """3.4: rdc events."""

    def test_lists_six_events(self, vkcube_session: str) -> None:
        """``rdc events`` lists 6 events as EID/TYPE/NAME TSV."""
        out = rdc_ok("events", session=vkcube_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        # First line is header, rest are data rows
        assert lines[0].startswith("EID")
        data_lines = lines[1:]
        assert len(data_lines) == 6


class TestEvent:
    """3.5 / 3.6: rdc event."""

    def test_single_event_detail(self, vkcube_session: str) -> None:
        """``rdc event 11`` shows vkCmdDraw detail."""
        out = rdc_ok("event", "11", session=vkcube_session)
        assert "vkCmdDraw" in out

    def test_out_of_range_eid(self, vkcube_session: str) -> None:
        """``rdc event 999`` exits 1 with out-of-range error."""
        out = rdc_fail("event", "999", session=vkcube_session, exit_code=1)
        assert re.search(r"error.*eid.*out of range", out, re.IGNORECASE)


class TestDraws:
    """3.7: rdc draws."""

    def test_one_draw_call(self, vkcube_session: str) -> None:
        """``rdc draws`` reports 1 draw call (summary on stderr)."""
        result = rdc("draws", session=vkcube_session)
        assert result.returncode == 0, f"rdc draws failed:\n{result.stderr}"
        combined = result.stdout + result.stderr
        assert "1 draw call" in combined.lower()


class TestDraw:
    """3.8: rdc draw 11."""

    def test_draw_detail_triangles(self, vkcube_session: str) -> None:
        """``rdc draw 11`` shows 12 triangles."""
        out = rdc_ok("draw", "11", session=vkcube_session)
        assert "12" in out


class TestCount:
    """3.10-3.14: rdc count."""

    def test_count_events(self, vkcube_session: str) -> None:
        """``rdc count events`` outputs 6."""
        out = rdc_ok("count", "events", session=vkcube_session)
        assert out.strip() == "6"

    def test_count_draws(self, vkcube_session: str) -> None:
        """``rdc count draws`` outputs 1."""
        out = rdc_ok("count", "draws", session=vkcube_session)
        assert out.strip() == "1"

    def test_count_resources(self, vkcube_session: str) -> None:
        """``rdc count resources`` outputs 46."""
        out = rdc_ok("count", "resources", session=vkcube_session)
        assert out.strip() == "46"

    def test_count_shaders(self, vkcube_session: str) -> None:
        """``rdc count shaders`` outputs 2."""
        out = rdc_ok("count", "shaders", session=vkcube_session)
        assert out.strip() == "2"

    def test_count_bad_target(self, vkcube_session: str) -> None:
        """``rdc count badtarget`` exits 2 (Click choice error)."""
        rdc_fail("count", "badtarget", session=vkcube_session, exit_code=2)


class TestSearch:
    """3.15-3.17: rdc search."""

    def test_search_main(self, vkcube_session: str) -> None:
        """``rdc search "main"`` finds matches in shader disassembly."""
        out = rdc_ok("search", "main", session=vkcube_session)
        assert "main" in out.lower()

    def test_search_gl_position(self, vkcube_session: str) -> None:
        """``rdc search "gl_Position"`` finds matches in VS disassembly."""
        out = rdc_ok("search", "gl_Position", session=vkcube_session)
        assert "gl_Position" in out

    def test_search_nonexistent(self, vkcube_session: str) -> None:
        """``rdc search "nonexistent_xyz"`` returns empty output, exit 0."""
        out = rdc_ok("search", "nonexistent_xyz", session=vkcube_session)
        assert out.strip() == ""


class TestShaderMap:
    """3.18: rdc shader-map."""

    def test_tsv_columns(self, vkcube_session: str) -> None:
        """``rdc shader-map`` outputs TSV with EID, VS, PS columns."""
        out = rdc_ok("shader-map", session=vkcube_session)
        header = out.splitlines()[0]
        assert "EID" in header
        assert "VS" in header
        assert "PS" in header


class TestPipeline:
    """3.19-3.23: rdc pipeline."""

    def test_pipeline_summary(self, vkcube_session: str) -> None:
        """``rdc pipeline 11`` shows TriangleList topology."""
        out = rdc_ok("pipeline", "11", session=vkcube_session)
        assert "TriangleList" in out

    def test_pipeline_topology_section(self, vkcube_session: str) -> None:
        """``rdc pipeline 11 topology`` shows topology key and TriangleList."""
        out = rdc_ok("pipeline", "11", "topology", session=vkcube_session)
        assert "topology" in out.lower()
        assert "TriangleList" in out

    def test_pipeline_viewport_section(self, vkcube_session: str) -> None:
        """``rdc pipeline 11 viewport`` shows width and height."""
        out = rdc_ok("pipeline", "11", "viewport", session=vkcube_session)
        assert "width" in out.lower()
        assert "height" in out.lower()

    def test_pipeline_blend_section(self, vkcube_session: str) -> None:
        """``rdc pipeline 11 blend`` shows blends array."""
        out = rdc_ok("pipeline", "11", "blend", session=vkcube_session)
        assert "blends" in out.lower()

    def test_pipeline_bad_section(self, vkcube_session: str) -> None:
        """``rdc pipeline 11 badslice`` exits 1 with invalid section error."""
        out = rdc_fail("pipeline", "11", "badslice", session=vkcube_session, exit_code=1)
        assert "error" in out.lower()
        assert "invalid section" in out.lower()


class TestBindings:
    """3.24: rdc bindings 11."""

    def test_descriptor_bindings(self, vkcube_session: str) -> None:
        """``rdc bindings 11`` shows descriptor bindings."""
        out = rdc_ok("bindings", "11", session=vkcube_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        assert len(lines) >= 2  # header + at least 1 row
        assert "EID" in lines[0]
        assert "STAGE" in lines[0]


class TestShader:
    """3.25-3.27: rdc shader."""

    def test_stage_only_form(self, vkcube_session: str) -> None:
        """``rdc shader vs`` shows shader info for VS stage."""
        out = rdc_ok("shader", "vs", session=vkcube_session)
        assert "STAGE" in out or "vs" in out.lower()

    def test_eid_stage_form(self, vkcube_session: str) -> None:
        """``rdc shader 11 vs`` shows shader info for EID 11 VS stage."""
        out = rdc_ok("shader", "11", "vs", session=vkcube_session)
        assert "11" in out
        assert "vs" in out.lower()

    def test_invalid_stage(self, vkcube_session: str) -> None:
        """``rdc shader xx`` exits 2 (bad parameter error)."""
        rdc_fail("shader", "xx", session=vkcube_session, exit_code=2)


class TestShaders:
    """3.29: rdc shaders."""

    def test_shader_list_header(self, vkcube_session: str) -> None:
        """``rdc shaders`` outputs SHADER/STAGES/USES header."""
        out = rdc_ok("shaders", session=vkcube_session)
        header = out.splitlines()[0]
        assert "SHADER" in header
        assert "STAGES" in header
        assert "USES" in header


class TestResources:
    """3.31: rdc resources."""

    def test_lists_46_resources(self, vkcube_session: str) -> None:
        """``rdc resources`` lists 46 resources."""
        out = rdc_ok("resources", session=vkcube_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        # header + 46 data rows
        assert len(lines) == 47


class TestResource:
    """3.32-3.33: rdc resource."""

    def test_resource_detail(self, vkcube_session: str) -> None:
        """``rdc resource 97`` shows 2D Image texture info."""
        out = rdc_ok("resource", "97", session=vkcube_session)
        assert "97" in out
        assert "Texture" in out or "2D Image" in out or "Image" in out

    def test_resource_not_found(self, vkcube_session: str) -> None:
        """``rdc resource 99999`` exits 1 with not-found error."""
        out = rdc_fail("resource", "99999", session=vkcube_session, exit_code=1)
        assert re.search(r"error.*resource.*not found", out, re.IGNORECASE)


class TestPasses:
    """3.34-3.38: rdc passes."""

    def test_pass_list(self, vkcube_session: str) -> None:
        """``rdc passes`` lists passes including Colour Pass."""
        out = rdc_ok("passes", session=vkcube_session)
        assert "Colour Pass" in out

    def test_pass_detail(self, vkcube_session: str) -> None:
        """``rdc pass 0`` shows pass detail."""
        out = rdc_ok("pass", "0", session=vkcube_session)
        assert out.strip() != ""

    def test_passes_deps(self, vkcube_session: str) -> None:
        """``rdc passes --deps`` outputs DAG TSV."""
        out = rdc_ok("passes", "--deps", session=vkcube_session)
        header = out.splitlines()[0]
        assert "SRC" in header or "src" in header.lower()

    def test_passes_dot_without_deps(self, vkcube_session: str) -> None:
        """``rdc passes --dot`` (without --deps) exits 2."""
        rdc_fail("passes", "--dot", session=vkcube_session, exit_code=2)

    def test_passes_deps_dot(self, vkcube_session: str) -> None:
        """``rdc passes --deps --dot`` outputs Graphviz DOT format."""
        out = rdc_ok("passes", "--deps", "--dot", session=vkcube_session)
        assert "digraph" in out


class TestUsage:
    """3.39: rdc usage 97."""

    def test_resource_usage(self, vkcube_session: str) -> None:
        """``rdc usage 97`` shows usage entries including PS_Resource."""
        out = rdc_ok("usage", "97", session=vkcube_session)
        assert "PS_Resource" in out
