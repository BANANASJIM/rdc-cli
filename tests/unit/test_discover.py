"""Tests for discover.py — sys.path insertion order (P2-ARCH-1)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from rdc.discover import (
    ProbeOutcome,
    ProbeResult,
    _get_diagnostic,
    _probe_candidate,
    _try_import_from,
    find_renderdoc,
)


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


class TestProbeCandidate:
    """_probe_candidate classifies subprocess outcomes correctly."""

    def test_success_returns_zero(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """rc=0: success."""
        from unittest.mock import MagicMock

        fake_dir = str(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1.41\n"

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: mock_result)
        outcome = _probe_candidate(fake_dir, timeout=5.0)

        assert outcome.result == ProbeResult.SUCCESS
        assert outcome.candidate_path == fake_dir
        assert outcome.version == "1.41"

    def test_import_failed_returns_nonzero(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """rc>0: import failure."""
        from unittest.mock import MagicMock

        fake_dir = str(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: mock_result)
        outcome = _probe_candidate(fake_dir, timeout=5.0)

        assert outcome.result == ProbeResult.IMPORT_FAILED
        assert outcome.candidate_path == fake_dir

    def test_crash_prone_returns_negative(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """rc<0: crash-prone (incompatible ABI)."""
        from unittest.mock import MagicMock

        fake_dir = str(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = -11
        mock_result.stdout = ""

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: mock_result)
        outcome = _probe_candidate(fake_dir, timeout=5.0)

        assert outcome.result == ProbeResult.CRASH_PRONE
        assert outcome.candidate_path == fake_dir

    def test_timeout_returns_timeout(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Timeout: returns timeout result."""
        import subprocess

        fake_dir = str(tmp_path)

        def raise_timeout(*a: object, **kw: object) -> object:
            raise subprocess.TimeoutExpired("test", 5)

        monkeypatch.setattr("subprocess.run", raise_timeout)
        outcome = _probe_candidate(fake_dir, timeout=5.0)

        assert outcome.result == ProbeResult.TIMEOUT
        assert outcome.candidate_path == fake_dir


class TestFindRenderdocFallback:
    """find_renderdoc skips crash-prone candidates and falls back correctly."""

    def test_skips_crash_prone_candidate(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """B45: crash-prone candidate is skipped, fallback to later candidate."""
        crash_dir = tmp_path / "crash"
        crash_dir.mkdir()
        success_dir = tmp_path / "success"
        success_dir.mkdir()

        import types

        real_fake_mod = types.ModuleType("renderdoc")
        real_fake_mod.GetVersionString = lambda: "1.41"

        mock_outcomes = [
            ProbeOutcome(ProbeResult.CRASH_PRONE, str(crash_dir)),
            ProbeOutcome(ProbeResult.SUCCESS, str(success_dir), "1.41"),
        ]

        outcome_iter = iter(mock_outcomes)

        def mock_probe(path: str, timeout: float = 5.0) -> ProbeOutcome:
            return next(outcome_iter)

        def mock_renderdoc_search_paths():
            return [str(crash_dir), str(success_dir)]

        def mock_which(cmd: str):
            return None

        monkeypatch.setattr("rdc.discover._try_import", lambda: None)
        monkeypatch.setattr("rdc.discover._probe_candidate", mock_probe)
        monkeypatch.setattr("rdc.discover._try_import_from", lambda d: real_fake_mod)
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", mock_renderdoc_search_paths)
        monkeypatch.setattr("rdc.discover.shutil.which", mock_which)

        result = find_renderdoc()

        assert result is real_fake_mod

    def test_diagnostic_set_after_crash_prone(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Diagnostic is set when crash-prone candidate is detected."""
        crash_dir = tmp_path / "crash"
        crash_dir.mkdir()

        def mock_renderdoc_search_paths():
            return [str(crash_dir)]

        def mock_which(cmd: str):
            return None

        monkeypatch.setattr("rdc.discover._try_import", lambda: None)
        monkeypatch.setattr(
            "rdc.discover._probe_candidate",
            lambda path, timeout=5.0: ProbeOutcome(ProbeResult.CRASH_PRONE, str(crash_dir)),
        )
        monkeypatch.setattr("rdc.discover._try_import_from", lambda d: None)
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", mock_renderdoc_search_paths)
        monkeypatch.setattr("rdc.discover.shutil.which", mock_which)

        result = find_renderdoc()

        assert result is None
        diag = _get_diagnostic()
        assert diag is not None
        assert diag.result == ProbeResult.CRASH_PRONE
        assert diag.candidate_path == str(crash_dir)
