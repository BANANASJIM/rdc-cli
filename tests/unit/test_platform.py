"""Tests for rdc._platform — Unix branch coverage."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rdc._platform import (
    data_dir,
    install_shutdown_signal,
    is_pid_alive,
    popen_flags,
    renderdoc_search_paths,
    renderdoccmd_search_paths,
    secure_dir_permissions,
    secure_permissions,
    secure_write_text,
    terminate_process,
)

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Unix-only _platform tests")

# ── Group A: data_dir() ──────────────────────────────────────────────


class TestDataDir:
    def test_returns_home_dot_rdc(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """TP-W1-001: Unix data_dir is ~/.rdc."""
        monkeypatch.setattr("rdc._platform.Path.home", staticmethod(lambda: tmp_path))
        assert data_dir() == tmp_path / ".rdc"

    def test_no_side_effects(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """TP-W1-002: data_dir does not create the directory."""
        monkeypatch.setattr("rdc._platform.Path.home", staticmethod(lambda: tmp_path))
        result = data_dir()
        assert not result.exists()


# ── Group B: terminate_process() ─────────────────────────────────────


class TestTerminateProcess:
    def test_sends_sigterm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-003: os.kill called with SIGTERM; returns True."""
        calls: list[tuple[int, int]] = []
        monkeypatch.setattr("rdc._platform.os.kill", lambda pid, sig: calls.append((pid, sig)))
        assert terminate_process(42) is True
        assert calls == [(42, signal.SIGTERM)]

    def test_process_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-004: ProcessLookupError -> False."""

        def _raise(_pid: int, _sig: int) -> None:
            raise ProcessLookupError

        monkeypatch.setattr("rdc._platform.os.kill", _raise)
        assert terminate_process(42) is False

    def test_permission_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-005: PermissionError -> False."""

        def _raise(_pid: int, _sig: int) -> None:
            raise PermissionError

        monkeypatch.setattr("rdc._platform.os.kill", _raise)
        assert terminate_process(42) is False

    def test_pid_zero(self) -> None:
        """TP-W1-006: pid=0 -> False without calling os.kill."""
        assert terminate_process(0) is False


# ── Group C: is_pid_alive() ──────────────────────────────────────────


class TestIsPidAlive:
    @pytest.fixture(autouse=True)
    def _force_linux(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc._platform._MAC", False)
        monkeypatch.setattr("rdc._platform._WIN", False)

    def test_alive_cmdline_matches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-007: alive + cmdline contains 'rdc' -> True."""
        pid = os.getpid()
        monkeypatch.setattr(
            "rdc._platform.Path.read_bytes",
            lambda _self: b"python\x00-m\x00rdc\x00daemon\x00",
        )
        assert is_pid_alive(pid) is True

    def test_alive_cmdline_no_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-008: alive + cmdline missing tag -> False."""
        pid = os.getpid()
        monkeypatch.setattr(
            "rdc._platform.Path.read_bytes",
            lambda _self: b"nginx\x00--daemon\x00",
        )
        assert is_pid_alive(pid) is False

    def test_custom_tag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-009: custom tag='renderdoccmd' matches -> True."""
        pid = os.getpid()
        monkeypatch.setattr(
            "rdc._platform.Path.read_bytes",
            lambda _self: b"/opt/renderdoc/bin/renderdoccmd\x00--serve\x00",
        )
        assert is_pid_alive(pid, tag="renderdoccmd") is True

    def test_proc_oserror_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-010: /proc read raises OSError -> fallback True."""
        pid = os.getpid()

        def _raise(_self: Path) -> bytes:
            raise OSError("no /proc")

        monkeypatch.setattr("rdc._platform.Path.read_bytes", _raise)
        assert is_pid_alive(pid) is True

    def test_process_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-011: kill(0) raises ProcessLookupError -> False."""

        def _raise(_pid: int, _sig: int) -> None:
            raise ProcessLookupError

        monkeypatch.setattr("rdc._platform.os.kill", _raise)
        assert is_pid_alive(999999) is False

    def test_negative_pid(self) -> None:
        """TP-W1-012: pid=-1 -> False without calling os.kill."""
        assert is_pid_alive(-1) is False


# ── Group D: install_shutdown_signal() ───────────────────────────────


class TestInstallShutdownSignal:
    def test_default_handler_registers_sigterm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-013: SIGTERM handler registered; invocation raises SystemExit(0)."""
        registered: list[tuple[int, object]] = []
        monkeypatch.setattr(
            "rdc._platform.signal.signal",
            lambda signum, handler: registered.append((signum, handler)),
        )
        install_shutdown_signal()
        assert len(registered) == 1
        assert registered[0][0] == signal.SIGTERM
        with pytest.raises(SystemExit, match="0"):
            registered[0][1](None, None)  # type: ignore[misc]

    def test_custom_handler(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-014: custom handler is called on signal."""
        registered: list[tuple[int, object]] = []
        monkeypatch.setattr(
            "rdc._platform.signal.signal",
            lambda signum, handler: registered.append((signum, handler)),
        )
        sentinel: list[int] = []
        install_shutdown_signal(handler=lambda: sentinel.append(1))
        assert len(registered) == 1
        registered[0][1](None, None)  # type: ignore[misc]
        assert sentinel == [1]

    def test_none_handler_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W1-015: handler=None explicitly -> SystemExit(0)."""
        registered: list[tuple[int, object]] = []
        monkeypatch.setattr(
            "rdc._platform.signal.signal",
            lambda signum, handler: registered.append((signum, handler)),
        )
        install_shutdown_signal(handler=None)
        with pytest.raises(SystemExit, match="0"):
            registered[0][1](None, None)  # type: ignore[misc]


# ── Group E-0: secure_write_text() ───────────────────────────────────


class TestSecureWriteText:
    def test_creates_file_with_0600(self, tmp_path: Path) -> None:
        """File created atomically with 0o600 permissions."""
        f = tmp_path / "secret.json"
        secure_write_text(f, '{"token": "abc"}')
        assert f.read_text() == '{"token": "abc"}'
        assert f.stat().st_mode & 0o777 == 0o600

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        """Existing file is truncated and rewritten."""
        f = tmp_path / "secret.json"
        f.write_text("old")
        secure_write_text(f, "new")
        assert f.read_text() == "new"
        assert f.stat().st_mode & 0o777 == 0o600


# ── Group E: secure_permissions() ────────────────────────────────────


class TestSecurePermissions:
    def test_sets_0600(self, tmp_path: Path) -> None:
        """TP-W1-016: file permissions set to 0o600."""
        f = tmp_path / "secret"
        f.write_text("data")
        secure_permissions(f)
        assert f.stat().st_mode & 0o777 == 0o600

    def test_corrects_existing_perms(self, tmp_path: Path) -> None:
        """TP-W1-017: file at 0o644 corrected to 0o600."""
        f = tmp_path / "secret"
        f.write_text("data")
        f.chmod(0o644)
        secure_permissions(f)
        assert f.stat().st_mode & 0o777 == 0o600


# ── Group F: secure_dir_permissions() ────────────────────────────────


class TestSecureDirPermissions:
    def test_sets_0700(self, tmp_path: Path) -> None:
        """TP-W1-018: existing directory set to 0o700."""
        d = tmp_path / "secure"
        d.mkdir()
        secure_dir_permissions(d)
        assert d.stat().st_mode & 0o777 == 0o700

    def test_corrects_existing_perms(self, tmp_path: Path) -> None:
        """TP-W1-019: directory at 0o755 corrected to 0o700."""
        d = tmp_path / "secure"
        d.mkdir(mode=0o755)
        secure_dir_permissions(d)
        assert d.stat().st_mode & 0o777 == 0o700


# ── Group G: popen_flags() ──────────────────────────────────────────


class TestPopenFlags:
    def test_returns_empty_dict(self) -> None:
        """TP-W1-020: Unix popen_flags returns {}."""
        assert popen_flags() == {}


# ── Group H: renderdoc_search_paths() ────────────────────────────────


class TestRenderdocSearchPaths:
    def test_returns_list_of_str(self) -> None:
        """TP-W1-021: returns list[str]."""
        result = renderdoc_search_paths()
        assert isinstance(result, list)
        assert all(isinstance(p, str) for p in result)

    def test_contains_expected_paths(self) -> None:
        """TP-W1-022: contains standard system paths."""
        result = renderdoc_search_paths()
        assert "/usr/lib/renderdoc" in result
        assert "/usr/local/lib/renderdoc" in result


# ── Group I: renderdoccmd_search_paths() ─────────────────────────────


class TestRenderdoccmdSearchPaths:
    def test_returns_list_of_path(self) -> None:
        """TP-W1-023: returns list[Path]."""
        result = renderdoccmd_search_paths()
        assert isinstance(result, list)
        assert all(isinstance(p, Path) for p in result)

    def test_contains_expected_paths(self) -> None:
        """TP-W1-024: contains standard binary paths."""
        result = renderdoccmd_search_paths()
        assert Path("/opt/renderdoc/bin/renderdoccmd") in result
        assert Path("/usr/local/bin/renderdoccmd") in result


# ── Group H-mac: renderdoc_search_paths() on darwin ───────────────────


class TestRenderdocSearchPathsDarwin:
    """M1: Homebrew search paths on macOS."""

    def test_includes_homebrew_arm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M1-01: darwin includes /opt/homebrew/opt/renderdoc/lib."""
        monkeypatch.setattr("rdc._platform._MAC", True)
        monkeypatch.setattr("rdc._platform._WIN", False)
        result = renderdoc_search_paths()
        assert "/opt/homebrew/opt/renderdoc/lib" in result

    def test_includes_homebrew_intel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M1-02: darwin includes /usr/local/opt/renderdoc/lib."""
        monkeypatch.setattr("rdc._platform._MAC", True)
        monkeypatch.setattr("rdc._platform._WIN", False)
        result = renderdoc_search_paths()
        assert "/usr/local/opt/renderdoc/lib" in result

    def test_includes_user_build(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """M1-03: darwin includes ~/.local/renderdoc."""
        monkeypatch.setattr("rdc._platform._MAC", True)
        monkeypatch.setattr("rdc._platform._WIN", False)
        monkeypatch.setattr("rdc._platform.Path.home", staticmethod(lambda: tmp_path))
        result = renderdoc_search_paths()
        assert str(tmp_path / ".local" / "renderdoc") in result

    def test_linux_excludes_homebrew(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M1-06: linux paths exclude Homebrew paths."""
        monkeypatch.setattr("rdc._platform._MAC", False)
        monkeypatch.setattr("rdc._platform._WIN", False)
        result = renderdoc_search_paths()
        assert "/opt/homebrew/opt/renderdoc/lib" not in result
        assert "/usr/local/opt/renderdoc/lib" not in result


# ── Group I-mac: renderdoccmd_search_paths() on darwin ────────────────


class TestRenderdoccmdSearchPathsDarwin:
    """M1: renderdoccmd Homebrew paths on macOS."""

    def test_includes_homebrew_bin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M1-04: darwin includes /opt/homebrew/bin/renderdoccmd."""
        monkeypatch.setattr("rdc._platform._MAC", True)
        monkeypatch.setattr("rdc._platform._WIN", False)
        result = renderdoccmd_search_paths()
        assert Path("/opt/homebrew/bin/renderdoccmd") in result

    def test_includes_usr_local_bin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M1-05: darwin includes /usr/local/bin/renderdoccmd."""
        monkeypatch.setattr("rdc._platform._MAC", True)
        monkeypatch.setattr("rdc._platform._WIN", False)
        result = renderdoccmd_search_paths()
        assert Path("/usr/local/bin/renderdoccmd") in result


# ── Group C-mac: is_pid_alive() on darwin ─────────────────────────────


class TestIsPidAliveDarwin:
    """M5: is_pid_alive uses ps on macOS."""

    def test_ps_tag_match_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M5-01: ps output contains tag -> True."""
        monkeypatch.setattr("rdc._platform._MAC", True)
        monkeypatch.setattr("rdc._platform._WIN", False)
        pid = os.getpid()
        mock_result = MagicMock(returncode=0, stdout="/usr/bin/python -m rdc daemon\n")
        monkeypatch.setattr("rdc._platform.subprocess.run", lambda *a, **kw: mock_result)
        assert is_pid_alive(pid) is True

    def test_ps_tag_no_match_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M5-02: ps output missing tag -> False."""
        monkeypatch.setattr("rdc._platform._MAC", True)
        monkeypatch.setattr("rdc._platform._WIN", False)
        pid = os.getpid()
        mock_result = MagicMock(returncode=0, stdout="/usr/sbin/nginx --daemon\n")
        monkeypatch.setattr("rdc._platform.subprocess.run", lambda *a, **kw: mock_result)
        assert is_pid_alive(pid) is False

    def test_ps_failure_falls_back_to_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M5-03: SubprocessError -> fallback True (kill-only check passed)."""
        monkeypatch.setattr("rdc._platform._MAC", True)
        monkeypatch.setattr("rdc._platform._WIN", False)
        pid = os.getpid()

        def _raise(*_a: object, **_kw: object) -> None:
            raise subprocess.SubprocessError("ps failed")

        monkeypatch.setattr("rdc._platform.subprocess.run", _raise)
        assert is_pid_alive(pid) is True

    def test_linux_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M5-04: on linux, /proc path is used (no regression)."""
        monkeypatch.setattr("rdc._platform._MAC", False)
        monkeypatch.setattr("rdc._platform._WIN", False)
        pid = os.getpid()
        monkeypatch.setattr(
            "rdc._platform.Path.read_bytes",
            lambda _self: b"python\x00-m\x00rdc\x00daemon\x00",
        )
        assert is_pid_alive(pid) is True


# ── Group J: backward compat ─────────────────────────────────────────


def test_session_state_reexports_is_pid_alive() -> None:
    """TP-W1-025: session_state.is_pid_alive delegates to _platform."""
    from rdc import _platform, session_state

    assert session_state.is_pid_alive is _platform.is_pid_alive


def test_capture_core_wraps_terminate(monkeypatch: pytest.MonkeyPatch) -> None:
    """TP-W1-026: capture_core.terminate_process delegates to _platform."""
    monkeypatch.setattr("rdc._platform.terminate_process", lambda pid: True)
    from rdc import capture_core

    assert capture_core.terminate_process(42) is True
