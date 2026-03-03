"""E2E tests for CI assertion commands (category 8).

All tests require a captured session and a working RenderDoc installation.
Counts, EIDs, and pixel values are discovered dynamically via ``capture_meta``.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from e2e_helpers import VKCUBE_VALIDATION, CaptureMetadata, rdc, rdc_fail, rdc_ok

pytestmark = pytest.mark.gpu


class TestAssertPixel:
    """8.1-8.2: rdc assert-pixel."""

    def test_pixel_pass_within_tolerance(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """``rdc assert-pixel`` matches discovered RGBA within tolerance."""
        r, g, b, a = capture_meta.pixel_rgba
        expect = f"{r:.2f} {g:.2f} {b:.2f} {a:.2f}"
        result = rdc(
            "assert-pixel",
            str(capture_meta.draw_eid),
            str(capture_meta.pixel_x),
            str(capture_meta.pixel_y),
            "--expect",
            expect,
            "--tolerance",
            "0.02",
            session=vkcube_session,
            timeout=60,
        )
        assert result.returncode == 0, f"Expected exit 0:\n{result.stdout}\n{result.stderr}"
        assert "pass:" in result.stdout.lower()

    def test_pixel_fail_wrong_color(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """``rdc assert-pixel`` fails when expected color is wrong."""
        r, g, b, a = capture_meta.pixel_rgba
        wrong = f"{1.0 - r:.2f} {1.0 - g:.2f} {1.0 - b:.2f} {a:.2f}"
        result = rdc(
            "assert-pixel",
            str(capture_meta.draw_eid),
            str(capture_meta.pixel_x),
            str(capture_meta.pixel_y),
            "--expect",
            wrong,
            session=vkcube_session,
            timeout=60,
        )
        assert result.returncode == 1, f"Expected exit 1:\n{result.stdout}\n{result.stderr}"
        assert "fail:" in result.stdout.lower()


class TestAssertClean:
    """8.3: rdc assert-clean."""

    def test_fails_on_validation_messages(self) -> None:
        """``rdc assert-clean`` fails on capture with HIGH validation messages."""
        if not VKCUBE_VALIDATION.exists():
            pytest.skip("vkcube_validation.rdc not available")
        name = f"e2e_ac_{uuid.uuid4().hex[:8]}"
        r = rdc("open", str(VKCUBE_VALIDATION), session=name)
        if r.returncode != 0:
            rdc("close", session=name)
            pytest.skip("vkcube_validation.rdc cannot replay on this GPU")
        try:
            out = rdc_fail("assert-clean", session=name, exit_code=1)
            assert "fail:" in out.lower()
        finally:
            rdc("close", session=name)


class TestAssertCount:
    """8.4-8.9: rdc assert-count."""

    def test_events_pass(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc assert-count events --expect N`` passes."""
        out = rdc_ok(
            "assert-count",
            "events",
            "--expect",
            str(capture_meta.total_events),
            session=vkcube_session,
        )
        assert "pass:" in out.lower()

    def test_events_fail(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc assert-count events`` fails with wrong expect value."""
        wrong = capture_meta.total_events + 100
        out = rdc_fail(
            "assert-count",
            "events",
            "--expect",
            str(wrong),
            session=vkcube_session,
        )
        assert "fail:" in out.lower()

    def test_draws_pass(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc assert-count draws --expect N`` passes."""
        out = rdc_ok(
            "assert-count",
            "draws",
            "--expect",
            str(capture_meta.total_draws),
            session=vkcube_session,
        )
        assert "pass:" in out.lower()

    def test_resources_gt_pass(self, vkcube_session: str) -> None:
        """``rdc assert-count resources --expect 10 --op gt`` passes."""
        out = rdc_ok(
            "assert-count",
            "resources",
            "--expect",
            "10",
            "--op",
            "gt",
            session=vkcube_session,
        )
        assert "pass:" in out.lower()

    def test_triangles_pass(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc assert-count triangles --expect N`` passes."""
        out = rdc_ok(
            "assert-count",
            "triangles",
            "--expect",
            str(capture_meta.triangle_count),
            session=vkcube_session,
        )
        assert "pass:" in out.lower()

    def test_shaders_pass(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc assert-count shaders --expect N`` passes."""
        out = rdc_ok(
            "assert-count",
            "shaders",
            "--expect",
            str(capture_meta.total_shaders),
            session=vkcube_session,
        )
        assert "pass:" in out.lower()


class TestAssertState:
    """8.10-8.11: rdc assert-state."""

    def test_topology_triangle_list_pass(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """``rdc assert-state <eid> topology --expect TriangleList`` passes."""
        out = rdc_ok(
            "assert-state",
            str(capture_meta.draw_eid),
            "topology",
            "--expect",
            "TriangleList",
            session=vkcube_session,
        )
        assert "pass:" in out.lower()

    def test_topology_point_list_fail(
        self, vkcube_session: str, capture_meta: CaptureMetadata
    ) -> None:
        """``rdc assert-state <eid> topology --expect PointList`` fails."""
        out = rdc_fail(
            "assert-state",
            str(capture_meta.draw_eid),
            "topology",
            "--expect",
            "PointList",
            session=vkcube_session,
        )
        assert "fail:" in out.lower()


class TestAssertImage:
    """8.12-8.13: rdc assert-image (requires exported files)."""

    def test_identical_image_match(
        self,
        vkcube_session: str,
        capture_meta: CaptureMetadata,
        tmp_out: Path,
    ) -> None:
        """Export RT then compare the image against itself -- should match."""
        rt_path = str(tmp_out / "rt.png")
        r = rdc(
            "rt",
            str(capture_meta.draw_eid),
            "-o",
            rt_path,
            session=vkcube_session,
            timeout=60,
        )
        assert r.returncode == 0, f"rt export failed:\n{r.stderr}"
        assert Path(rt_path).exists()

        r = rdc(
            "assert-image",
            rt_path,
            rt_path,
            session=vkcube_session,
            timeout=60,
        )
        assert r.returncode == 0, f"assert-image failed:\n{r.stdout}\n{r.stderr}"
        assert "match" in r.stdout.lower()

    def test_size_mismatch_error(
        self,
        vkcube_session: str,
        capture_meta: CaptureMetadata,
        tmp_out: Path,
    ) -> None:
        """Compare RT export with texture export -- size mismatch exits 2."""
        rt_path = str(tmp_out / "rt.png")
        tex_path = str(tmp_out / "tex.png")

        r = rdc(
            "rt",
            str(capture_meta.draw_eid),
            "-o",
            rt_path,
            session=vkcube_session,
            timeout=60,
        )
        assert r.returncode == 0, f"rt export failed:\n{r.stderr}"

        r = rdc(
            "texture",
            str(capture_meta.texture_id),
            "-o",
            tex_path,
            session=vkcube_session,
            timeout=60,
        )
        assert r.returncode == 0, f"texture export failed:\n{r.stderr}"

        r = rdc(
            "assert-image",
            rt_path,
            tex_path,
            session=vkcube_session,
            timeout=60,
        )
        assert r.returncode == 2, (
            f"Expected exit 2, got {r.returncode}\nstdout: {r.stdout}\nstderr: {r.stderr}"
        )
        assert "size mismatch" in (r.stdout + r.stderr).lower()
