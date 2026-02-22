"""Tests for CLI assert-image command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from PIL import Image

from rdc.cli import main


def _solid(
    tmp_path: Path,
    name: str,
    color: tuple[int, ...],
    size: tuple[int, int] = (4, 4),
) -> Path:
    """Create a solid-color image and return its path."""
    p = tmp_path / name
    Image.new("RGBA", size, color).save(p)
    return p


class TestAssertImageExitCodes:
    def test_identical_exit_0(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255))
        b = _solid(tmp_path, "b.png", (0, 0, 0, 255))
        result = CliRunner().invoke(main, ["assert-image", str(a), str(b)])
        assert result.exit_code == 0
        assert "match" in result.output

    def test_differs_exit_1(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255))
        b = _solid(tmp_path, "b.png", (255, 255, 255, 255))
        result = CliRunner().invoke(main, ["assert-image", str(a), str(b)])
        assert result.exit_code == 1
        assert "diff:" in result.output
        assert "pixels" in result.output

    def test_size_mismatch_exit_2(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255), size=(4, 4))
        b = _solid(tmp_path, "b.png", (0, 0, 0, 255), size=(8, 8))
        result = CliRunner().invoke(main, ["assert-image", str(a), str(b)])
        assert result.exit_code == 2
        assert "error: size mismatch" in result.output


class TestAssertImageThreshold:
    def test_threshold_allows_diff(self, tmp_path: Path) -> None:
        img = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
        a = tmp_path / "a.png"
        img.save(a)
        img.putpixel((0, 0), (255, 0, 0, 255))
        b = tmp_path / "b.png"
        img.save(b)
        result = CliRunner().invoke(main, ["assert-image", "--threshold", "10.0", str(a), str(b)])
        assert result.exit_code == 0

    def test_threshold_rejects_diff(self, tmp_path: Path) -> None:
        img = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
        a = tmp_path / "a.png"
        img.save(a)
        img.putpixel((0, 0), (255, 0, 0, 255))
        b = tmp_path / "b.png"
        img.save(b)
        result = CliRunner().invoke(main, ["assert-image", "--threshold", "5.0", str(a), str(b)])
        assert result.exit_code == 1


class TestAssertImageDiffOutput:
    def test_diff_file_written(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255))
        b = _solid(tmp_path, "b.png", (255, 255, 255, 255))
        diff = tmp_path / "diff.png"
        result = CliRunner().invoke(
            main, ["assert-image", "--diff-output", str(diff), str(a), str(b)]
        )
        assert result.exit_code == 1
        assert diff.exists()


class TestAssertImageJson:
    def test_json_identical(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255))
        b = _solid(tmp_path, "b.png", (0, 0, 0, 255))
        result = CliRunner().invoke(main, ["assert-image", "--json", str(a), str(b)])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["identical"] is True
        assert data["diff_pixels"] == 0

    def test_json_differs(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255))
        b = _solid(tmp_path, "b.png", (255, 255, 255, 255))
        result = CliRunner().invoke(main, ["assert-image", "--json", str(a), str(b)])
        assert result.exit_code == 1
        data = json.loads(result.output.strip())
        assert data["identical"] is False
        assert data["threshold"] == 0.0

    def test_json_error_exit_2(self, tmp_path: Path) -> None:
        a = _solid(tmp_path, "a.png", (0, 0, 0, 255), size=(4, 4))
        b = _solid(tmp_path, "b.png", (0, 0, 0, 255), size=(8, 8))
        result = CliRunner().invoke(main, ["assert-image", "--json", str(a), str(b)])
        assert result.exit_code == 2
        assert "error:" in result.output


class TestAssertImageHelp:
    def test_help_exits_0(self) -> None:
        result = CliRunner().invoke(main, ["assert-image", "--help"])
        assert result.exit_code == 0
        assert "assert-image" in result.output
