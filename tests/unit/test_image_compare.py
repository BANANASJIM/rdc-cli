"""Tests for image_compare module."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from rdc.image_compare import compare_images


def _solid(
    tmp_path: Path,
    name: str,
    color: tuple[int, ...],
    size: tuple[int, int] = (4, 4),
    mode: str = "RGBA",
) -> Path:
    """Create a solid-color image and return its path."""
    p = tmp_path / name
    Image.new(mode, size, color).save(p)
    return p


class TestIdenticalImages:
    def test_identical_rgba(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (255, 0, 0, 255))
        b = _solid(tmp_path, "b.png", (255, 0, 0, 255))
        r = compare_images(a, b)
        assert r.identical is True
        assert r.diff_pixels == 0
        assert r.diff_ratio == 0.0
        assert r.diff_image is None


class TestDifferentImages:
    def test_one_pixel_differs(self, tmp_path: Path) -> None:
        img = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
        a = tmp_path / "a.png"
        img.save(a)
        img.putpixel((0, 0), (255, 0, 0, 255))
        b = tmp_path / "b.png"
        img.save(b)
        r = compare_images(a, b)
        assert r.diff_pixels == 1
        assert r.identical is False

    def test_all_pixels_differ(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255))
        b = _solid(tmp_path, "b.png", (255, 255, 255, 255))
        r = compare_images(a, b)
        assert r.diff_pixels == 16
        assert r.diff_ratio == 100.0


class TestSizeMismatch:
    def test_width_mismatch(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255), size=(4, 4))
        b = _solid(tmp_path, "b.png", (0, 0, 0, 255), size=(8, 4))
        with pytest.raises(ValueError, match="size mismatch"):
            compare_images(a, b)

    def test_height_mismatch(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255), size=(4, 4))
        b = _solid(tmp_path, "b.png", (0, 0, 0, 255), size=(4, 8))
        with pytest.raises(ValueError, match="size mismatch"):
            compare_images(a, b)


class TestThreshold:
    def test_within_threshold(self, tmp_path: Path) -> None:
        """1/16 pixels differ = 6.25%, threshold 10.0 -> identical."""
        img = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
        a = tmp_path / "a.png"
        img.save(a)
        img.putpixel((0, 0), (255, 0, 0, 255))
        b = tmp_path / "b.png"
        img.save(b)
        r = compare_images(a, b, threshold=10.0)
        assert r.identical is True

    def test_at_boundary(self, tmp_path: Path) -> None:
        """1/16 pixels differ = 6.25%, threshold 6.25 -> identical (inclusive)."""
        img = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
        a = tmp_path / "a.png"
        img.save(a)
        img.putpixel((0, 0), (255, 0, 0, 255))
        b = tmp_path / "b.png"
        img.save(b)
        r = compare_images(a, b, threshold=6.25)
        assert r.identical is True

    def test_above_threshold(self, tmp_path: Path) -> None:
        """1/16 pixels differ = 6.25%, threshold 5.0 -> not identical."""
        img = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
        a = tmp_path / "a.png"
        img.save(a)
        img.putpixel((0, 0), (255, 0, 0, 255))
        b = tmp_path / "b.png"
        img.save(b)
        r = compare_images(a, b, threshold=5.0)
        assert r.identical is False


class TestDiffOutput:
    def test_diff_image_written(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255))
        b = _solid(tmp_path, "b.png", (255, 255, 255, 255))
        diff_path = tmp_path / "diff.png"
        r = compare_images(a, b, diff_output=diff_path)
        assert r.diff_image == diff_path
        assert diff_path.exists()
        diff_img = Image.open(diff_path)
        assert diff_img.size == (4, 4)

    def test_no_diff_when_identical(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255))
        b = _solid(tmp_path, "b.png", (0, 0, 0, 255))
        diff_path = tmp_path / "diff.png"
        r = compare_images(a, b, diff_output=diff_path)
        assert r.diff_image is None
        assert not diff_path.exists()


class TestModeNormalization:
    def test_rgb_vs_rgba(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (255, 0, 0), mode="RGB")
        b = _solid(tmp_path, "b.png", (255, 0, 0, 255), mode="RGBA")
        r = compare_images(a, b)
        assert r.diff_pixels == 0
        assert r.identical is True

    def test_grayscale_mode(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", 128, mode="L")
        b = _solid(tmp_path, "b.png", (128, 128, 128, 255), mode="RGBA")
        r = compare_images(a, b)
        assert r.diff_pixels == 0


class TestErrorPaths:
    def test_file_not_found(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255))
        with pytest.raises(FileNotFoundError):
            compare_images(a, tmp_path / "missing.png")

    def test_invalid_image(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255))
        bad = tmp_path / "bad.png"
        bad.write_text("not an image")
        from PIL import UnidentifiedImageError

        with pytest.raises(UnidentifiedImageError):
            compare_images(a, bad)
