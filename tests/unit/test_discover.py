"""Tests for discover.py — sys.path insertion order (P2-ARCH-1)."""

from __future__ import annotations

import sys
from unittest.mock import patch

from rdc.discover import _try_import_from


class TestTryImportFrom:
    """_try_import_from appends to sys.path (not insert at 0) and cleans up on failure."""

    def test_success_appends_to_end(self, tmp_path: str, monkeypatch: object) -> None:
        """On success, directory appears at the END of sys.path."""
        import types

        fake_dir = str(tmp_path)
        fake_mod = types.ModuleType("renderdoc")
        fake_mod.GetVersionString = lambda: "1.41"  # type: ignore[attr-defined]

        # Ensure directory is not already in sys.path
        if fake_dir in sys.path:
            sys.path.remove(fake_dir)

        with patch("importlib.import_module", return_value=fake_mod):
            result = _try_import_from(fake_dir)

        assert result is fake_mod
        assert fake_dir in sys.path
        # It should be at the end, not at index 0
        assert sys.path[-1] == fake_dir

        # Cleanup
        sys.path.remove(fake_dir)

    def test_failure_removes_from_path(self, tmp_path: str) -> None:
        """On import failure, directory is removed from sys.path."""

        fake_dir = str(tmp_path)

        # Ensure directory is not already in sys.path
        if fake_dir in sys.path:
            sys.path.remove(fake_dir)

        with patch("importlib.import_module", side_effect=ImportError("no module")):
            result = _try_import_from(fake_dir)

        assert result is None
        assert fake_dir not in sys.path
