"""Tests for scripts/setup_vulkan_samples.py."""

from __future__ import annotations

from pathlib import Path

import pytest
from setup_vulkan_samples import _BIN_NAME, _find_binary


class TestFindBinary:
    """_find_binary searches recursively under build/app/bin/."""

    def test_flat_release(self, tmp_path: Path) -> None:
        """Binary directly under build/app/bin/Release/."""
        binary = tmp_path / "build" / "app" / "bin" / "Release" / _BIN_NAME
        binary.parent.mkdir(parents=True)
        binary.touch()
        assert _find_binary(tmp_path) == binary

    def test_platform_subdirectory(self, tmp_path: Path) -> None:
        """MSBuild adds a $(Platform) subdirectory like AMD64."""
        binary = tmp_path / "build" / "app" / "bin" / "Release" / "AMD64" / _BIN_NAME
        binary.parent.mkdir(parents=True)
        binary.touch()
        assert _find_binary(tmp_path) == binary

    def test_bare_bin(self, tmp_path: Path) -> None:
        """Binary directly under build/app/bin/ (no Release dir)."""
        binary = tmp_path / "build" / "app" / "bin" / _BIN_NAME
        binary.parent.mkdir(parents=True)
        binary.touch()
        assert _find_binary(tmp_path) == binary

    def test_not_found(self, tmp_path: Path) -> None:
        """Raises SystemExit when binary is missing."""
        (tmp_path / "build" / "app" / "bin").mkdir(parents=True)
        with pytest.raises(SystemExit):
            _find_binary(tmp_path)
