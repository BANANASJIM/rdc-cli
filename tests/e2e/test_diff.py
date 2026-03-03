"""E2E tests for diff commands (category 9).

The diff command opens two captures via internal daemon sessions, so it
needs a running daemon but does NOT reuse the caller's session for replay.
A vkcube_session fixture is used to ensure the daemon infrastructure is
available.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from e2e_helpers import HELLO_TRIANGLE, VKCUBE, VKCUBE_VALIDATION, rdc, rdc_ok

pytestmark = pytest.mark.gpu


class TestDiffSameCapture:
    """9.1-9.2: diff identical captures (self-captured)."""

    def test_stats_all_equal(self, vkcube_session: str, captured_rdc: Path) -> None:
        """``rdc diff CAP CAP --stats`` shows all '=' status, exit 0."""
        out = rdc_ok(
            "diff",
            str(captured_rdc),
            str(captured_rdc),
            "--stats",
            session=vkcube_session,
        )
        assert "=" in out

    def test_framebuffer_identical(self, vkcube_session: str, captured_rdc: Path) -> None:
        """``rdc diff CAP CAP --framebuffer`` reports identical, exit 0."""
        r = rdc(
            "diff",
            str(captured_rdc),
            str(captured_rdc),
            "--framebuffer",
            session=vkcube_session,
            timeout=60,
        )
        assert r.returncode == 0, f"Expected exit 0:\n{r.stdout}\n{r.stderr}"
        assert "identical" in r.stdout.lower()

    def test_draws_shortstat_identical(self, vkcube_session: str, captured_rdc: Path) -> None:
        """``rdc diff CAP CAP --draws --shortstat`` shows all unchanged."""
        out = rdc_ok(
            "diff",
            str(captured_rdc),
            str(captured_rdc),
            "--draws",
            "--shortstat",
            session=vkcube_session,
        )
        assert "unchanged" in out.lower()


class TestDiffVkcubeVsValidation:
    """9.3-9.4: diff VKCUBE vs VKCUBE_VALIDATION (requires pre-recorded fixtures)."""

    @pytest.fixture(autouse=True)
    def _require_prerecorded(self, can_replay_prerecorded: bool) -> None:
        if not can_replay_prerecorded:
            pytest.skip("pre-recorded fixtures cannot be replayed on this GPU")

    def test_stats_comparison(self, vkcube_session: str) -> None:
        """``rdc diff VKCUBE VKCUBE_VALIDATION --stats`` produces stats comparison."""
        r = rdc(
            "diff",
            str(VKCUBE),
            str(VKCUBE_VALIDATION),
            "--stats",
            session=vkcube_session,
        )
        assert r.returncode == 0, f"Expected exit 0:\n{r.stdout}\n{r.stderr}"
        combined = r.stdout + r.stderr
        assert combined.strip() != ""

    def test_framebuffer_size_mismatch(self, vkcube_session: str) -> None:
        """``rdc diff VKCUBE VKCUBE_VALIDATION --framebuffer`` exits 2 on size mismatch."""
        r = rdc(
            "diff",
            str(VKCUBE),
            str(VKCUBE_VALIDATION),
            "--framebuffer",
            session=vkcube_session,
            timeout=60,
        )
        assert r.returncode == 2, (
            f"Expected exit 2, got {r.returncode}\nstdout: {r.stdout}\nstderr: {r.stderr}"
        )
        assert "size mismatch" in (r.stdout + r.stderr).lower()


class TestDiffVkcubeVsTriangle:
    """9.5-9.7: diff VKCUBE vs HELLO_TRIANGLE (requires pre-recorded fixtures)."""

    @pytest.fixture(autouse=True)
    def _require_prerecorded(self, can_replay_prerecorded: bool) -> None:
        if not can_replay_prerecorded:
            pytest.skip("pre-recorded fixtures cannot be replayed on this GPU")

    def test_draws_has_status_and_eid(self, vkcube_session: str) -> None:
        """``rdc diff VKCUBE HELLO_TRIANGLE --draws`` outputs STATUS/EID columns."""
        r = rdc(
            "diff",
            str(VKCUBE),
            str(HELLO_TRIANGLE),
            "--draws",
            session=vkcube_session,
        )
        assert r.returncode == 0, f"Expected exit 0:\n{r.stdout}\n{r.stderr}"
        combined = r.stdout + r.stderr
        assert "STATUS" in combined or "status" in combined.lower()
        assert "EID" in combined or "eid" in combined.lower()

    def test_resources_has_status_and_name(self, vkcube_session: str) -> None:
        """``rdc diff VKCUBE HELLO_TRIANGLE --resources`` outputs STATUS/NAME/TYPE."""
        r = rdc(
            "diff",
            str(VKCUBE),
            str(HELLO_TRIANGLE),
            "--resources",
            session=vkcube_session,
        )
        assert r.returncode == 0, f"Expected exit 0:\n{r.stdout}\n{r.stderr}"
        combined = r.stdout + r.stderr
        assert "STATUS" in combined or "status" in combined.lower()
        assert "NAME" in combined or "name" in combined.lower()
        assert "TYPE" in combined or "type" in combined.lower()
