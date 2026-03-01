"""E2E tests for CI assertion commands (category 8).

All tests require a vkcube.rdc daemon session and a working RenderDoc
installation. The capture has 6 events, 1 draw at EID 11, and pixel at
(300, 300) is approximately (0.337, 0.337, 0.337, 0.522).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import rdc, rdc_fail, rdc_ok

pytestmark = pytest.mark.gpu


class TestAssertPixel:
    """8.1-8.2: rdc assert-pixel."""

    def test_pixel_pass_within_tolerance(self, vkcube_session: str) -> None:
        """``rdc assert-pixel 11 300 300`` matches expected RGBA within tolerance."""
        r = rdc(
            "assert-pixel",
            "11",
            "300",
            "300",
            "--expect",
            "0.33 0.33 0.33 0.52",
            "--tolerance",
            "0.02",
            session=vkcube_session,
            timeout=60,
        )
        assert r.returncode == 0, f"Expected exit 0:\n{r.stdout}\n{r.stderr}"
        assert "pass:" in r.stdout.lower()

    def test_pixel_fail_wrong_color(self, vkcube_session: str) -> None:
        """``rdc assert-pixel 11 300 300`` fails when expected color is wrong."""
        r = rdc(
            "assert-pixel",
            "11",
            "300",
            "300",
            "--expect",
            "1.0 0.0 0.0 1.0",
            session=vkcube_session,
            timeout=60,
        )
        assert r.returncode == 1, f"Expected exit 1:\n{r.stdout}\n{r.stderr}"
        assert "fail:" in r.stdout.lower()


class TestAssertClean:
    """8.3: rdc assert-clean."""

    def test_fails_on_validation_messages(self, vkcube_session: str) -> None:
        """``rdc assert-clean`` fails because vkcube has HIGH validation messages."""
        out = rdc_fail("assert-clean", session=vkcube_session, exit_code=1)
        assert "fail:" in out.lower()


class TestAssertCount:
    """8.4-8.9: rdc assert-count."""

    def test_events_eq_6_pass(self, vkcube_session: str) -> None:
        """``rdc assert-count events --expect 6`` passes."""
        out = rdc_ok("assert-count", "events", "--expect", "6", session=vkcube_session)
        assert "pass:" in out.lower()

    def test_events_eq_10_fail(self, vkcube_session: str) -> None:
        """``rdc assert-count events --expect 10`` fails."""
        out = rdc_fail("assert-count", "events", "--expect", "10", session=vkcube_session)
        assert "fail:" in out.lower()

    def test_draws_eq_1_pass(self, vkcube_session: str) -> None:
        """``rdc assert-count draws --expect 1`` passes."""
        out = rdc_ok("assert-count", "draws", "--expect", "1", session=vkcube_session)
        assert "pass:" in out.lower()

    def test_resources_gt_10_pass(self, vkcube_session: str) -> None:
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

    def test_triangles_eq_12_pass(self, vkcube_session: str) -> None:
        """``rdc assert-count triangles --expect 12`` passes."""
        out = rdc_ok(
            "assert-count",
            "triangles",
            "--expect",
            "12",
            session=vkcube_session,
        )
        assert "pass:" in out.lower()

    def test_shaders_eq_2_pass(self, vkcube_session: str) -> None:
        """``rdc assert-count shaders --expect 2`` passes."""
        out = rdc_ok(
            "assert-count",
            "shaders",
            "--expect",
            "2",
            session=vkcube_session,
        )
        assert "pass:" in out.lower()


class TestAssertState:
    """8.10-8.11: rdc assert-state."""

    def test_topology_triangle_list_pass(self, vkcube_session: str) -> None:
        """``rdc assert-state 11 topology --expect TriangleList`` passes."""
        out = rdc_ok(
            "assert-state",
            "11",
            "topology",
            "--expect",
            "TriangleList",
            session=vkcube_session,
        )
        assert "pass:" in out.lower()

    def test_topology_point_list_fail(self, vkcube_session: str) -> None:
        """``rdc assert-state 11 topology --expect PointList`` fails."""
        out = rdc_fail(
            "assert-state",
            "11",
            "topology",
            "--expect",
            "PointList",
            session=vkcube_session,
        )
        assert "fail:" in out.lower()


class TestAssertImage:
    """8.12-8.13: rdc assert-image (requires exported files)."""

    def test_identical_image_match(self, vkcube_session: str, tmp_out: Path) -> None:
        """Export RT then compare the image against itself -- should match."""
        rt_path = str(tmp_out / "rt.png")
        r = rdc(
            "rt",
            "11",
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

    def test_size_mismatch_error(self, vkcube_session: str, tmp_out: Path) -> None:
        """Compare RT export with texture export -- size mismatch exits 2."""
        rt_path = str(tmp_out / "rt.png")
        tex_path = str(tmp_out / "tex.png")

        r = rdc("rt", "11", "-o", rt_path, session=vkcube_session, timeout=60)
        assert r.returncode == 0, f"rt export failed:\n{r.stderr}"

        r = rdc("texture", "97", "-o", tex_path, session=vkcube_session, timeout=60)
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
