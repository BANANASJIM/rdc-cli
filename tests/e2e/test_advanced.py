"""E2E tests for advanced features (categories 10, 11, 12).

Covers script execution, shader encodings, quiet-mode line counts,
and multi-fixture captures (dynamic_rendering, oit_depth_peeling).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from e2e_helpers import HELLO_TRIANGLE, rdc, rdc_fail, rdc_ok

pytestmark = pytest.mark.gpu


# ---------------------------------------------------------------------------
# Category 10: Script execution
# ---------------------------------------------------------------------------


class TestScript:
    """10.1-10.2: rdc script."""

    def test_script_prints_ok(self, vkcube_session: str, tmp_out: Path) -> None:
        """``rdc script`` executes a Python script and captures stdout."""
        script = tmp_out / "ok_script.py"
        script.write_text('import renderdoc\nprint("ok")\n')

        out = rdc_ok("script", str(script), session=vkcube_session)
        assert "ok" in out

    def test_script_error_exits_1(self, vkcube_session: str, tmp_out: Path) -> None:
        """``rdc script`` with a raising script exits 1 with error message."""
        script = tmp_out / "bad_script.py"
        script.write_text('raise ValueError("boom")\n')

        out = rdc_fail("script", str(script), session=vkcube_session, exit_code=1)
        assert "error" in out.lower()


# ---------------------------------------------------------------------------
# Category 11: Advanced features
# ---------------------------------------------------------------------------


class TestShaderEncodings:
    """11.1: rdc shader-encodings."""

    def test_lists_glsl(self, vkcube_session: str) -> None:
        """``rdc shader-encodings`` output contains GLSL encoding."""
        out = rdc_ok("shader-encodings", session=vkcube_session)
        assert "GLSL" in out


class TestEventsQuiet:
    """11.4: rdc events -q line count."""

    def test_quiet_mode_six_lines(self, vkcube_session: str) -> None:
        """``rdc events -q`` outputs exactly 6 EID lines."""
        out = rdc_ok("events", "-q", session=vkcube_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        assert len(lines) == 6


# ---------------------------------------------------------------------------
# Category 12: Multi-fixture tests
# ---------------------------------------------------------------------------


class TestHelloTriangleSession:
    """12.2: Open hello_triangle.rdc in its own session."""

    def test_open_status_close(self) -> None:
        """Open hello_triangle, verify status, then close."""
        name = f"e2e_ht_{uuid.uuid4().hex[:8]}"
        try:
            r = rdc("open", str(HELLO_TRIANGLE), session=name)
            assert r.returncode == 0, f"open failed:\n{r.stderr}"

            status = rdc_ok("status", session=name)
            assert "hello_triangle" in status.lower()

            close_out = rdc_ok("close", session=name)
            assert "closed" in close_out.lower()
        finally:
            rdc("close", session=name)


class TestDynamicRendering:
    """12.4: dynamic_rendering.rdc -- 4 draws, 2 passes."""

    def test_count_draws(self, dynamic_session: str) -> None:
        """``rdc count draws`` outputs 4 for dynamic_rendering capture."""
        out = rdc_ok("count", "draws", session=dynamic_session)
        assert out.strip() == "4"

    def test_passes_count(self, dynamic_session: str) -> None:
        """``rdc passes`` lists 2 passes for dynamic_rendering capture."""
        out = rdc_ok("passes", session=dynamic_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        # Header + 2 data rows
        data_lines = [ln for ln in lines if not ln.startswith("NAME")]
        assert len(data_lines) == 2


class TestOitDepthPeeling:
    """12.5: oit_depth_peeling.rdc -- 9 passes, has deps."""

    def test_count_passes(self, oit_session: str) -> None:
        """``rdc count passes`` outputs 9 for oit_depth_peeling capture."""
        out = rdc_ok("count", "passes", session=oit_session)
        assert out.strip() == "9"

    def test_passes_deps_has_edges(self, oit_session: str) -> None:
        """``rdc passes --deps`` outputs a DAG with dependency edges."""
        out = rdc_ok("passes", "--deps", session=oit_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        # Should have header + at least one edge row
        assert len(lines) >= 2
