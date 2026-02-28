"""Tests for scripts/dev_install.py."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GENERATE = "rdc.commands.completion._generate"


def _import_dev_install() -> ModuleType:
    """Import dev_install module from scripts/."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "dev_install",
        Path(__file__).resolve().parents[2] / "scripts" / "dev_install.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dev_install = _import_dev_install()


# =========================================================================
# Shell detection (SD-1 .. SD-7)
# =========================================================================


class TestDetectShell:
    """Shell detection tests."""

    def test_sd1_zsh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/bin/zsh")
        monkeypatch.setattr("sys.platform", "linux")
        assert dev_install.detect_shell() == "zsh"

    def test_sd2_bash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/usr/bin/bash")
        monkeypatch.setattr("sys.platform", "linux")
        assert dev_install.detect_shell() == "bash"

    def test_sd3_fish(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/usr/bin/fish")
        monkeypatch.setattr("sys.platform", "linux")
        assert dev_install.detect_shell() == "fish"

    def test_sd4_unset_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SHELL", raising=False)
        monkeypatch.setattr("sys.platform", "linux")
        assert dev_install.detect_shell() == "bash"

    def test_sd5_win32(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.platform", "win32")
        assert dev_install.detect_shell() == "powershell"

    def test_sd6_nonstandard_zsh_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/usr/local/bin/zsh")
        monkeypatch.setattr("sys.platform", "linux")
        assert dev_install.detect_shell() == "zsh"

    def test_sd7_unsupported_shell_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/usr/bin/tcsh")
        monkeypatch.setattr("sys.platform", "linux")
        assert dev_install.detect_shell() == "bash"


# =========================================================================
# Completion installation (CI-1 .. CI-7)
# =========================================================================


class TestInstallCompletion:
    """Completion installation tests."""

    def test_ci1_bash_correct_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(_GENERATE, lambda shell: f"# bash completion for {shell}")
        assert dev_install.install_completion("bash", home=tmp_path)
        expected = tmp_path / ".local/share/bash-completion/completions/rdc"
        assert expected.read_text() == "# bash completion for bash"

    def test_ci2_zsh_correct_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(_GENERATE, lambda shell: f"# zsh completion for {shell}")
        assert dev_install.install_completion("zsh", home=tmp_path)
        expected = tmp_path / ".zfunc/_rdc"
        assert expected.read_text() == "# zsh completion for zsh"

    def test_ci3_fish_correct_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(_GENERATE, lambda shell: f"# fish completion for {shell}")
        assert dev_install.install_completion("fish", home=tmp_path)
        expected = tmp_path / ".config/fish/completions/rdc.fish"
        assert expected.read_text() == "# fish completion for fish"

    def test_ci4_parent_dirs_created(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(_GENERATE, lambda shell: "# script")
        assert dev_install.install_completion("bash", home=tmp_path)
        parent = tmp_path / ".local/share/bash-completion/completions"
        assert parent.is_dir()

    def test_ci5_powershell_no_file(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert dev_install.install_completion("powershell", home=tmp_path)
        out = capsys.readouterr().out
        assert "$PROFILE" in out
        assert list(tmp_path.iterdir()) == []

    def test_ci6_existing_file_overwritten(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".local/share/bash-completion/completions/rdc"
        target.parent.mkdir(parents=True)
        target.write_text("old content")
        monkeypatch.setattr(_GENERATE, lambda shell: "new content")
        assert dev_install.install_completion("bash", home=tmp_path)
        assert target.read_text() == "new content"

    def test_ci7_zsh_fpath_hint(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(_GENERATE, lambda shell: "# zsh")
        dev_install.install_completion("zsh", home=tmp_path)
        out = capsys.readouterr().out
        assert "fpath" in out


# =========================================================================
# UV install (UV-1, UV-2)
# =========================================================================


class TestInstallBinary:
    """UV binary install tests."""

    def test_uv1_correct_args(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_run = MagicMock()
        monkeypatch.setattr(subprocess, "run", mock_run)
        dev_install.install_binary()
        mock_run.assert_called_once_with(
            ["uv", "tool", "install", "-e", ".", "--force"],
            check=True,
        )

    def test_uv2_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fail(*args: object, **kwargs: object) -> None:
            raise subprocess.CalledProcessError(1, "uv")

        monkeypatch.setattr(subprocess, "run", _fail)
        with pytest.raises(subprocess.CalledProcessError):
            dev_install.install_binary()


# =========================================================================
# Error handling (EH-1, EH-2)
# =========================================================================


class TestErrorHandling:
    """Error handling tests."""

    def test_eh1_generate_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def _boom(shell: str) -> str:
            raise RuntimeError("generation failed")

        monkeypatch.setattr(_GENERATE, _boom)
        ok = dev_install.install_completion("bash", home=tmp_path)
        assert not ok
        assert "WARNING" in capsys.readouterr().out
        assert not (tmp_path / ".local/share/bash-completion/completions/rdc").exists()

    def test_eh2_permission_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(_GENERATE, lambda shell: "# script")

        def _deny(self_: Path, *args: object, **kwargs: object) -> None:
            raise PermissionError("access denied")

        monkeypatch.setattr(Path, "write_text", _deny)
        ok = dev_install.install_completion("bash", home=tmp_path)
        assert not ok
        assert "permission denied" in capsys.readouterr().out


# =========================================================================
# End-to-end (E2E-1, E2E-2)
# =========================================================================


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_e2e1_full_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(subprocess, "run", MagicMock())
        monkeypatch.setattr(_GENERATE, lambda shell: "# completion")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.setenv("SHELL", "/bin/zsh")
        monkeypatch.setattr("sys.platform", "linux")

        dev_install.main()

        out = capsys.readouterr().out
        assert "Binary:     installed" in out
        assert (tmp_path / ".zfunc/_rdc").exists()

    def test_e2e2_binary_fail_no_completion(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _fail(*args: object, **kwargs: object) -> None:
            raise subprocess.CalledProcessError(1, "uv")

        monkeypatch.setattr(subprocess, "run", _fail)
        gen_mock = MagicMock()
        monkeypatch.setattr(_GENERATE, gen_mock)

        with pytest.raises(subprocess.CalledProcessError):
            dev_install.main()

        gen_mock.assert_not_called()
