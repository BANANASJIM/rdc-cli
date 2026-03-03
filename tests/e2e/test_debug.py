"""E2E tests for debug and pixel history commands.

Black-box tests that invoke the real CLI via subprocess against a captured
session. Requires a working renderdoc installation.

Debug commands may take longer than typical CLI calls, so raw ``rdc()`` calls
use timeout=60.
"""

from __future__ import annotations

import pytest
from conftest import CaptureMetadata
from e2e_helpers import rdc_fail, rdc_json, rdc_ok

pytestmark = pytest.mark.gpu

TIMEOUT = 60


class TestDebugPixel:
    """7.1: rdc debug pixel <eid> X Y shows shader debug summary."""

    def test_pixel_summary(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """Debug pixel summary contains stage and steps fields."""
        out = rdc_ok(
            "debug",
            "pixel",
            str(capture_meta.draw_eid),
            str(capture_meta.pixel_x),
            str(capture_meta.pixel_y),
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert "stage:" in out.lower() or "stage:" in out
        assert "steps:" in out.lower() or "steps:" in out


class TestDebugPixelTrace:
    """7.2: rdc debug pixel <eid> X Y --trace shows execution trace."""

    def test_pixel_trace_columns(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """Trace output contains STEP, INSTR, FILE header columns."""
        out = rdc_ok(
            "debug",
            "pixel",
            str(capture_meta.draw_eid),
            str(capture_meta.pixel_x),
            str(capture_meta.pixel_y),
            "--trace",
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert "STEP" in out
        assert "INSTR" in out
        assert "FILE" in out


class TestDebugVertex:
    """7.3: rdc debug vertex <eid> 0 shows vertex shader debug."""

    def test_vertex_summary(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """Debug vertex summary reports stage as vs."""
        out = rdc_ok(
            "debug",
            "vertex",
            str(capture_meta.draw_eid),
            "0",
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert "stage:" in out.lower() or "stage:" in out
        assert "vs" in out.lower()


class TestDebugPixelNoFragment:
    """7.4: rdc debug pixel <eid> 99999 99999 errors when no fragment hit."""

    def test_no_fragment_error(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """Debugging a pixel outside the draw area produces an error."""
        out = rdc_fail(
            "debug",
            "pixel",
            str(capture_meta.draw_eid),
            "99999",
            "99999",
            session=vkcube_session,
            exit_code=1,
            timeout=TIMEOUT,
        )
        assert "error" in out.lower()


class TestPickPixel:
    """7.5: rdc pick-pixel X Y EID returns RGBA color values."""

    def test_pick_pixel_returns_color(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """pick-pixel returns r= g= b= a= formatted color."""
        out = rdc_ok(
            "pick-pixel",
            str(capture_meta.pixel_x),
            str(capture_meta.pixel_y),
            str(capture_meta.draw_eid),
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert "r=" in out
        assert "g=" in out
        assert "b=" in out
        assert "a=" in out

    def test_pick_pixel_json(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """pick-pixel --json returns JSON with color object."""
        data = rdc_json(
            "pick-pixel",
            str(capture_meta.pixel_x),
            str(capture_meta.pixel_y),
            str(capture_meta.draw_eid),
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert "color" in data
        color = data["color"]
        for channel in ("r", "g", "b", "a"):
            assert channel in color


class TestPixelHistory:
    """7.6: rdc pixel X Y EID shows pixel history table."""

    def test_pixel_history_columns(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """Pixel history output has EID, FRAG, DEPTH, PASSED columns."""
        out = rdc_ok(
            "pixel",
            str(capture_meta.pixel_x),
            str(capture_meta.pixel_y),
            str(capture_meta.draw_eid),
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert "EID" in out
        assert "FRAG" in out
        assert "DEPTH" in out
        assert "PASSED" in out


class TestPixelHistoryJson:
    """7.7: rdc pixel X Y EID --json returns JSON with modifications."""

    def test_pixel_history_json(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """JSON output contains a modifications key."""
        data = rdc_json(
            "pixel",
            str(capture_meta.pixel_x),
            str(capture_meta.pixel_y),
            str(capture_meta.draw_eid),
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert "modifications" in data
