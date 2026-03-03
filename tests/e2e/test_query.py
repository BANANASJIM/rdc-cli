"""E2E tests for query commands (category 3).

All tests in this module require a vkcube session and a working RenderDoc
installation. Capture metadata (EIDs, counts, IDs) is discovered dynamically
via the ``capture_meta`` fixture.
"""

from __future__ import annotations

import re

import pytest
from conftest import CaptureMetadata
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

    def test_lists_expected_events(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """``rdc events`` lists the expected number of events."""
        out = rdc_ok("events", session=vkcube_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        assert lines[0].startswith("EID")
        data_lines = lines[1:]
        assert len(data_lines) == capture_meta.total_events


class TestEvent:
    """3.5 / 3.6: rdc event."""

    def test_single_event_detail(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc event <draw_eid>`` shows draw detail."""
        out = rdc_ok("event", str(capture_meta.draw_eid), session=vkcube_session)
        assert "Draw" in out or "draw" in out.lower()

    def test_out_of_range_eid(self, vkcube_session: str) -> None:
        """``rdc event 999`` exits 1 with out-of-range error."""
        out = rdc_fail("event", "999", session=vkcube_session, exit_code=1)
        assert re.search(r"error.*eid.*out of range", out, re.IGNORECASE)


class TestDraws:
    """3.7: rdc draws."""

    def test_draw_call_count(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc draws`` reports expected draw call count."""
        result = rdc("draws", session=vkcube_session)
        assert result.returncode == 0, f"rdc draws failed:\n{result.stderr}"
        combined = result.stdout + result.stderr
        assert f"{capture_meta.total_draws} draw call" in combined.lower()


class TestDraw:
    """3.8: rdc draw <eid>."""

    def test_draw_detail_triangles(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """``rdc draw <draw_eid>`` shows triangle count."""
        out = rdc_ok("draw", str(capture_meta.draw_eid), session=vkcube_session)
        assert str(capture_meta.triangle_count) in out


class TestCount:
    """3.10-3.14: rdc count."""

    def test_count_events(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc count events`` outputs expected count."""
        out = rdc_ok("count", "events", session=vkcube_session)
        assert out.strip() == str(capture_meta.total_events)

    def test_count_draws(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc count draws`` outputs expected count."""
        out = rdc_ok("count", "draws", session=vkcube_session)
        assert out.strip() == str(capture_meta.total_draws)

    def test_count_resources(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc count resources`` outputs expected count."""
        out = rdc_ok("count", "resources", session=vkcube_session)
        assert out.strip() == str(capture_meta.total_resources)

    def test_count_shaders(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc count shaders`` outputs expected count."""
        out = rdc_ok("count", "shaders", session=vkcube_session)
        assert out.strip() == str(capture_meta.total_shaders)

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

    def test_pipeline_summary(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc pipeline <draw_eid>`` shows TriangleList topology."""
        out = rdc_ok("pipeline", str(capture_meta.draw_eid), session=vkcube_session)
        assert "TriangleList" in out

    def test_pipeline_topology_section(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """``rdc pipeline <draw_eid> topology`` shows TriangleList."""
        out = rdc_ok("pipeline", str(capture_meta.draw_eid), "topology", session=vkcube_session)
        assert "topology" in out.lower()
        assert "TriangleList" in out

    def test_pipeline_viewport_section(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """``rdc pipeline <draw_eid> viewport`` shows width and height."""
        out = rdc_ok("pipeline", str(capture_meta.draw_eid), "viewport", session=vkcube_session)
        assert "width" in out.lower()
        assert "height" in out.lower()

    def test_pipeline_blend_section(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """``rdc pipeline <draw_eid> blend`` shows blends array."""
        out = rdc_ok("pipeline", str(capture_meta.draw_eid), "blend", session=vkcube_session)
        assert "blends" in out.lower()

    def test_pipeline_bad_section(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc pipeline <draw_eid> badslice`` exits 1."""
        out = rdc_fail(
            "pipeline",
            str(capture_meta.draw_eid),
            "badslice",
            session=vkcube_session,
            exit_code=1,
        )
        assert "error" in out.lower()
        assert "invalid section" in out.lower()


class TestBindings:
    """3.24: rdc bindings <draw_eid>."""

    def test_descriptor_bindings(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc bindings <draw_eid>`` shows descriptor bindings."""
        out = rdc_ok("bindings", str(capture_meta.draw_eid), session=vkcube_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        assert len(lines) >= 2
        assert "EID" in lines[0]
        assert "STAGE" in lines[0]


class TestShader:
    """3.25-3.27: rdc shader."""

    def test_stage_only_form(self, vkcube_session: str) -> None:
        """``rdc shader vs`` shows shader info for VS stage."""
        out = rdc_ok("shader", "vs", session=vkcube_session)
        assert "STAGE" in out or "vs" in out.lower()

    def test_eid_stage_form(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc shader <draw_eid> vs`` shows shader info."""
        eid_str = str(capture_meta.draw_eid)
        out = rdc_ok("shader", eid_str, "vs", session=vkcube_session)
        assert eid_str in out
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

    def test_lists_expected_resources(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """``rdc resources`` lists expected number of resources."""
        out = rdc_ok("resources", session=vkcube_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        # header + N data rows
        assert len(lines) == capture_meta.total_resources + 1


class TestResource:
    """3.32-3.33: rdc resource."""

    def test_resource_detail(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc resource <texture_id>`` shows resource info."""
        tid_str = str(capture_meta.texture_id)
        out = rdc_ok("resource", tid_str, session=vkcube_session)
        assert tid_str in out

    def test_resource_not_found(self, vkcube_session: str) -> None:
        """``rdc resource 99999`` exits 1 with not-found error."""
        out = rdc_fail("resource", "99999", session=vkcube_session, exit_code=1)
        assert re.search(r"error.*resource.*not found", out, re.IGNORECASE)


class TestPasses:
    """3.34-3.38: rdc passes."""

    def test_pass_list(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc passes`` lists passes including the primary pass."""
        out = rdc_ok("passes", session=vkcube_session)
        assert capture_meta.pass_name in out

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
    """3.39: rdc usage <texture_id>."""

    def test_resource_usage(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc usage <texture_id>`` shows usage entries."""
        out = rdc_ok("usage", str(capture_meta.texture_id), session=vkcube_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        assert len(lines) >= 2, f"expected header + usage rows, got {len(lines)} lines"
