"""E2E tests for export commands (texture, rt, buffer, mesh, snapshot, etc.).

Black-box tests that invoke the real CLI via subprocess against a vkcube.rdc
capture session. Requires a working renderdoc installation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import rdc_fail, rdc_ok

pytestmark = pytest.mark.gpu

PNG_MAGIC = b"\x89PNG"


class TestTextureExport:
    """6.1: rdc texture 97 -o {tmp}/tex.png exports a PNG file."""

    def test_texture_png(self, vkcube_session: str, tmp_out: Path) -> None:
        """Exported texture is a valid PNG with non-zero size."""
        dest = tmp_out / "tex.png"
        rdc_ok("texture", "97", "-o", str(dest), session=vkcube_session)
        assert dest.exists()
        assert dest.stat().st_size > 0
        assert dest.read_bytes()[:4] == PNG_MAGIC


class TestTextureNotFound:
    """6.2: rdc texture 99999 errors with exit 1."""

    def test_bad_texture_id(self, vkcube_session: str, tmp_out: Path) -> None:
        """Non-existent texture ID produces an error."""
        dest = tmp_out / "bad.png"
        out = rdc_fail("texture", "99999", "-o", str(dest), session=vkcube_session, exit_code=1)
        assert "error" in out.lower()


class TestRtExport:
    """6.3: rdc rt 11 -o {tmp}/rt.png exports render target as PNG."""

    def test_rt_png(self, vkcube_session: str, tmp_out: Path) -> None:
        """Exported render target is a valid PNG with non-zero size."""
        dest = tmp_out / "rt.png"
        rdc_ok("rt", "11", "-o", str(dest), session=vkcube_session)
        assert dest.exists()
        assert dest.stat().st_size > 0
        assert dest.read_bytes()[:4] == PNG_MAGIC


class TestRtOverlay:
    """6.4: rdc rt 11 --overlay wireframe -o {tmp}/wire.png exports with overlay."""

    def test_rt_overlay_png(self, vkcube_session: str, tmp_out: Path) -> None:
        """Overlay render produces a valid PNG file."""
        dest = tmp_out / "wire.png"
        rdc_ok(
            "rt",
            "11",
            "--overlay",
            "wireframe",
            "-o",
            str(dest),
            session=vkcube_session,
        )
        assert dest.exists()
        assert dest.stat().st_size > 0
        assert dest.read_bytes()[:4] == PNG_MAGIC


class TestBufferExport:
    """6.5: rdc buffer 102 -o {tmp}/buf.bin exports raw buffer data."""

    def test_buffer_binary(self, vkcube_session: str, tmp_out: Path) -> None:
        """Exported buffer has non-zero size."""
        dest = tmp_out / "buf.bin"
        rdc_ok("buffer", "102", "-o", str(dest), session=vkcube_session)
        assert dest.exists()
        assert dest.stat().st_size > 0


class TestMeshExport:
    """6.6: rdc mesh 11 -o {tmp}/mesh.obj exports OBJ with vertices and faces."""

    def test_mesh_obj(self, vkcube_session: str, tmp_out: Path) -> None:
        """Exported OBJ file contains vertex and face lines."""
        dest = tmp_out / "mesh.obj"
        rdc_ok("mesh", "11", "-o", str(dest), session=vkcube_session)
        assert dest.exists()
        assert dest.stat().st_size > 0
        text = dest.read_text()
        assert any(line.startswith("v ") for line in text.splitlines())
        assert any(line.startswith("f ") for line in text.splitlines())


class TestThumbnailExport:
    """6.7: rdc thumbnail -o {tmp}/thumb.png exports capture thumbnail."""

    def test_thumbnail_image(self, vkcube_session: str, tmp_out: Path) -> None:
        """Exported thumbnail is a valid image file (PNG or JPEG)."""
        dest = tmp_out / "thumb.jpg"
        rdc_ok("thumbnail", "-o", str(dest), session=vkcube_session)
        assert dest.exists()
        assert dest.stat().st_size > 0
        magic = dest.read_bytes()[:4]
        is_jpeg = magic[:3] == b"\xff\xd8\xff"
        assert magic == PNG_MAGIC or is_jpeg, f"Expected PNG or JPEG, got {magic!r}"


class TestSnapshotExport:
    """6.8: rdc snapshot 11 -o {tmp}/snap creates a snapshot directory."""

    def test_snapshot_directory(self, vkcube_session: str, tmp_out: Path) -> None:
        """Snapshot creates directory with pipeline.json and color0.png."""
        dest = tmp_out / "snap"
        rdc_ok("snapshot", "11", "-o", str(dest), session=vkcube_session)
        assert dest.is_dir()
        assert (dest / "pipeline.json").exists()
        assert (dest / "color0.png").exists()
        assert (dest / "color0.png").read_bytes()[:4] == PNG_MAGIC


class TestGpus:
    """6.9: rdc gpus lists GPU name(s)."""

    def test_gpu_names(self, vkcube_session: str) -> None:
        """GPU listing is non-empty."""
        out = rdc_ok("gpus", session=vkcube_session)
        assert len(out.strip()) > 0


class TestSections:
    """6.10: rdc sections lists section names with bytes."""

    def test_section_list(self, vkcube_session: str) -> None:
        """Section listing contains section names and byte counts."""
        out = rdc_ok("sections", session=vkcube_session)
        assert "bytes" in out.lower()


class TestSectionContent:
    """6.11: rdc section "renderdoc/internal/framecapture" outputs content."""

    def test_section_content(self, vkcube_session: str) -> None:
        """Known section outputs non-empty content."""
        out = rdc_ok("section", "renderdoc/internal/framecapture", session=vkcube_session)
        assert len(out.strip()) > 0


class TestSectionNotFound:
    """6.12: rdc section "0" errors with exit 1."""

    def test_bad_section_name(self, vkcube_session: str) -> None:
        """Non-existent section produces an error."""
        out = rdc_fail("section", "0", session=vkcube_session, exit_code=1)
        assert "error" in out.lower()


class TestTexStats:
    """6.13: rdc tex-stats 97 shows CHANNEL/MIN/MAX table."""

    def test_tex_stats_table(self, vkcube_session: str) -> None:
        """Texture stats output contains CHANNEL, MIN, MAX columns."""
        out = rdc_ok("tex-stats", "97", session=vkcube_session)
        assert "CHANNEL" in out
        assert "MIN" in out
        assert "MAX" in out


class TestTexStatsNoArg:
    """6.14: rdc tex-stats (no arg) exits with usage error."""

    def test_missing_argument(self, vkcube_session: str) -> None:
        """Missing required argument produces exit code 2."""
        rdc_fail("tex-stats", session=vkcube_session, exit_code=2)
