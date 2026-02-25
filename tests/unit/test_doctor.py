from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from rdc.commands.doctor import (
    CheckResult,
    _check_mac_homebrew,
    _check_mac_renderdoc_dylib,
    _check_mac_xcode_cli,
    _check_renderdoccmd,
    _check_win_python_version,
    _check_win_renderdoc_install,
    _check_win_vs_build_tools,
    _import_renderdoc,
    _make_build_hint,
    doctor_cmd,
    run_doctor,
)
from rdc.discover import ProbeOutcome, ProbeResult


def _fake_renderdoc(*, with_replay: bool = True) -> SimpleNamespace:
    """Create a fake renderdoc module for testing."""
    attrs = {"GetVersionString": lambda: "1.33"}
    if with_replay:
        attrs.update(
            InitialiseReplay=lambda *args, **kwargs: 0,
            ShutdownReplay=lambda: None,
            GlobalEnvironment=lambda: object(),
        )
    return SimpleNamespace(**attrs)


# ── Existing tests (unchanged) ───────────────────────────────────────


def test_doctor_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: _fake_renderdoc())
    monkeypatch.setattr(
        "rdc.commands.doctor.find_renderdoccmd", lambda: Path("/usr/bin/renderdoccmd")
    )
    monkeypatch.setattr(
        "rdc.commands.doctor.subprocess.run",
        lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=0, stdout="v1.33"),
    )

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 0
    assert "\u2705" in result.output
    assert "platform" in result.output
    assert "replay-support" in result.output


def test_doctor_failure_when_missing_renderdoccmd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
    monkeypatch.setattr(
        "rdc.commands.doctor.find_renderdoc", lambda: _fake_renderdoc(with_replay=False)
    )
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoccmd", lambda: None)

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 1
    assert "renderdoccmd" in result.output


def test_doctor_shows_build_hint_when_renderdoc_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
    monkeypatch.setattr(
        "rdc.commands.doctor._RENDERDOC_BUILD_HINT",
        "  renderdoc is not available on PyPI and must be built from source.\n"
        "  Quick build script (no pixi required):\n"
        "    bash <(curl -fsSL"
        " https://raw.githubusercontent.com/BANANASJIM/rdc-cli/master/scripts/build-renderdoc.sh)\n"
        "  Full instructions: https://bananasjim.github.io/rdc-cli/\n"
        "  Then re-run: rdc doctor",
    )
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: None)
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoccmd", lambda: None)

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 1
    assert "not found" in result.output
    assert "renderdoc is not available on PyPI" in result.output


def test_doctor_hint_contains_docs_url() -> None:
    from rdc.commands.doctor import _RENDERDOC_BUILD_HINT

    assert "https://bananasjim.github.io/rdc-cli/" in _RENDERDOC_BUILD_HINT


# ── Group W: _check_win_python_version() ─────────────────────────────


class TestWinPythonVersion:
    """TP-W3-001 through TP-W3-005."""

    def test_non_windows_returns_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-001: non-Windows returns ok=True, detail='n/a'."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
        r = _check_win_python_version()
        assert r.ok is True
        assert r.name == "win-python-version"
        assert "n/a" in r.detail

    def test_pyd_version_matches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-002: pyd version matches running Python."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [r"C:\RenderDoc"])
        monkeypatch.setattr(
            "rdc.commands.doctor.glob.glob",
            lambda _pattern: [r"C:\RenderDoc\renderdoc.cpython-312-win_amd64.pyd"],
        )
        vi = type("VI", (), {"__getitem__": lambda s, k: (3, 12)[k]})()
        monkeypatch.setattr("rdc.commands.doctor.sys.version_info", vi)
        r = _check_win_python_version()
        assert r.ok is True
        assert "3.12" in r.detail
        assert "matches" in r.detail

    def test_pyd_version_mismatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-003: pyd version mismatches running Python."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [r"C:\RenderDoc"])
        monkeypatch.setattr(
            "rdc.commands.doctor.glob.glob",
            lambda _pattern: [r"C:\RenderDoc\renderdoc.cpython-310-win_amd64.pyd"],
        )
        vi = type("VI", (), {"__getitem__": lambda s, k: (3, 12)[k]})()
        monkeypatch.setattr("rdc.commands.doctor.sys.version_info", vi)
        r = _check_win_python_version()
        assert r.ok is False
        assert "3.12" in r.detail
        assert "3.10" in r.detail

    def test_no_pyd_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-004: no .pyd found in search paths."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [r"C:\RenderDoc"])
        monkeypatch.setattr("rdc.commands.doctor.glob.glob", lambda _pattern: [])
        r = _check_win_python_version()
        assert r.ok is False
        assert "not found" in r.detail.lower()


# ── Group X: _check_win_vs_build_tools() ──────────────────────────────


class TestWinVsBuildTools:
    """TP-W3-006 through TP-W3-010."""

    def test_non_windows_returns_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-006: non-Windows returns ok=True, detail='n/a'."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
        r = _check_win_vs_build_tools()
        assert r.ok is True
        assert r.name == "win-vs-build-tools"
        assert "n/a" in r.detail

    def test_vswhere_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-007: vswhere.exe not found anywhere."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc.commands.doctor.Path.exists", lambda _self: False)
        monkeypatch.setattr("rdc.commands.doctor.shutil.which", lambda _name: None)
        r = _check_win_vs_build_tools()
        assert r.ok is False
        assert "vswhere" in r.detail.lower()

    def test_vs_tools_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-008: vswhere found via which, VC++ present."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc.commands.doctor.Path.exists", lambda _self: False)
        monkeypatch.setattr(
            "rdc.commands.doctor.shutil.which",
            lambda name: r"C:\VS\vswhere.exe" if name == "vswhere" else None,
        )
        monkeypatch.setattr(
            "rdc.commands.doctor.subprocess.run",
            lambda *_a, **_kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout='[{"installationVersion":"17.9"}]'
            ),
        )
        r = _check_win_vs_build_tools()
        assert r.ok is True
        assert "17.9" in r.detail

    def test_vs_tools_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-009: vswhere returns empty list (no VC++ workload)."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc.commands.doctor.Path.exists", lambda _self: False)
        monkeypatch.setattr(
            "rdc.commands.doctor.shutil.which",
            lambda name: r"C:\VS\vswhere.exe" if name == "vswhere" else None,
        )
        monkeypatch.setattr(
            "rdc.commands.doctor.subprocess.run",
            lambda *_a, **_kw: subprocess.CompletedProcess(args=[], returncode=0, stdout="[]"),
        )
        r = _check_win_vs_build_tools()
        assert r.ok is False
        assert "build tools" in r.detail.lower()

    def test_vswhere_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-010: vswhere subprocess times out."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc.commands.doctor.Path.exists", lambda _self: False)
        monkeypatch.setattr(
            "rdc.commands.doctor.shutil.which",
            lambda name: r"C:\VS\vswhere.exe" if name == "vswhere" else None,
        )

        def _timeout(*_a: object, **_kw: object) -> None:
            raise subprocess.TimeoutExpired(cmd="vswhere", timeout=5)

        monkeypatch.setattr("rdc.commands.doctor.subprocess.run", _timeout)
        r = _check_win_vs_build_tools()
        assert r.ok is False
        assert "timed out" in r.detail.lower()


# ── Group Y: _check_win_renderdoc_install() ───────────────────────────


class TestWinRenderdocInstall:
    """TP-W3-011 through TP-W3-014."""

    def test_non_windows_returns_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-011: non-Windows returns ok=True, detail='n/a'."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
        r = _check_win_renderdoc_install()
        assert r.ok is True
        assert r.name == "win-renderdoc-install"
        assert "n/a" in r.detail

    def test_found_at_program_files(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-012: renderdoc.dll found at Program Files."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        env = {"LOCALAPPDATA": r"C:\Users\test\AppData\Local"}
        monkeypatch.setattr("rdc.commands.doctor.os.environ", env)

        original_exists = Path.exists

        def _exists(self: Path) -> bool:
            if "Program Files" in str(self) and str(self).endswith("renderdoc.dll"):
                return True
            return original_exists(self)

        monkeypatch.setattr("rdc.commands.doctor.Path.exists", _exists)
        r = _check_win_renderdoc_install()
        assert r.ok is True
        assert "RenderDoc" in r.detail

    def test_found_via_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """TP-W3-013: renderdoc.dll found via RENDERDOC_PYTHON_PATH."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        (tmp_path / "renderdoc.dll").write_text("fake")
        env = {"RENDERDOC_PYTHON_PATH": str(tmp_path), "LOCALAPPDATA": ""}
        monkeypatch.setattr("rdc.commands.doctor.os.environ", env)
        r = _check_win_renderdoc_install()
        assert r.ok is True
        assert str(tmp_path) in r.detail

    def test_not_found_anywhere(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-014: renderdoc.dll not found anywhere."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        env: dict[str, str] = {"LOCALAPPDATA": ""}
        monkeypatch.setattr("rdc.commands.doctor.os.environ", env)
        monkeypatch.setattr("rdc.commands.doctor.Path.exists", lambda _self: False)
        r = _check_win_renderdoc_install()
        assert r.ok is False
        assert "RENDERDOC_PYTHON_PATH" in r.detail


# ── Group Z: _make_build_hint() ───────────────────────────────────────


class TestMakeBuildHint:
    """TP-W3-015 and TP-W3-016."""

    def test_linux_hint_contains_bash_script(self) -> None:
        """TP-W3-015: Linux hint has bash script URL."""
        hint = _make_build_hint("linux")
        assert "build-renderdoc.sh" in hint
        assert "https://bananasjim.github.io/rdc-cli/" in hint

    def test_windows_hint_contains_py_script(self) -> None:
        """TP-W3-016: Windows hint has Python build script."""
        hint = _make_build_hint("win32")
        assert "build_renderdoc.py" in hint
        assert "https://bananasjim.github.io/rdc-cli/" in hint


# ── TP-W3-017: run_doctor() result count ─────────────────────────────


def test_run_doctor_linux_returns_5_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """TP-W3-017a: Linux run_doctor returns 5 results."""
    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: _fake_renderdoc())
    monkeypatch.setattr(
        "rdc.commands.doctor.find_renderdoccmd", lambda: Path("/usr/bin/renderdoccmd")
    )
    monkeypatch.setattr(
        "rdc.commands.doctor.subprocess.run",
        lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=0, stdout="v1.33"),
    )
    results = run_doctor()
    assert len(results) == 5
    win_names = {"win-python-version", "win-vs-build-tools", "win-renderdoc-install"}
    assert all(r.name not in win_names for r in results)


def test_run_doctor_windows_has_3_more_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """TP-W3-017b: Windows has exactly 3 more checks than Linux."""
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: _fake_renderdoc())
    monkeypatch.setattr(
        "rdc.commands.doctor.find_renderdoccmd", lambda: Path("/usr/bin/renderdoccmd")
    )
    monkeypatch.setattr(
        "rdc.commands.doctor.subprocess.run",
        lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=0, stdout="v1.33"),
    )

    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
    linux_count = len(run_doctor())

    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
    # Stub the win checks to avoid actual Windows calls
    monkeypatch.setattr(
        "rdc.commands.doctor._check_win_python_version",
        lambda: CheckResult("win-python-version", True, "ok"),
    )
    monkeypatch.setattr(
        "rdc.commands.doctor._check_win_vs_build_tools",
        lambda: CheckResult("win-vs-build-tools", True, "ok"),
    )
    monkeypatch.setattr(
        "rdc.commands.doctor._check_win_renderdoc_install",
        lambda: CheckResult("win-renderdoc-install", True, "ok"),
    )
    win_count = len(run_doctor())

    assert win_count - linux_count == 3


# ── _check_renderdoccmd() version probing ─────────────────────────────


class TestCheckRenderdoccmd:
    def test_found_with_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rdc.commands.doctor.find_renderdoccmd", lambda: Path("/usr/bin/renderdoccmd")
        )
        monkeypatch.setattr(
            "rdc.commands.doctor.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=0, stdout="v1.33\n"),
        )
        r = _check_renderdoccmd()
        assert r.ok is True
        assert "v1.33" in r.detail
        assert str(Path("/usr/bin/renderdoccmd")) in r.detail

    def test_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands.doctor.find_renderdoccmd", lambda: None)
        r = _check_renderdoccmd()
        assert r.ok is False
        assert "not found" in r.detail

    def test_version_timeout_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rdc.commands.doctor.find_renderdoccmd", lambda: Path("/usr/bin/renderdoccmd")
        )

        def _timeout(*_a: object, **_kw: object) -> None:
            raise subprocess.TimeoutExpired(cmd="renderdoccmd", timeout=3)

        monkeypatch.setattr("rdc.commands.doctor.subprocess.run", _timeout)
        r = _check_renderdoccmd()
        assert r.ok is True
        assert str(Path("/usr/bin/renderdoccmd")) in r.detail

    def test_version_in_stderr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rdc.commands.doctor.find_renderdoccmd", lambda: Path("/usr/bin/renderdoccmd")
        )
        monkeypatch.setattr(
            "rdc.commands.doctor.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr="v1.33\n"
            ),
        )
        r = _check_renderdoccmd()
        assert r.ok is True
        assert "v1.33" in r.detail


# ── Group M2: macOS doctor checks ─────────────────────────────────────


class TestMacXcodeCli:
    """M2-01, M2-02: _check_mac_xcode_cli()."""

    def test_non_darwin_returns_na(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
        r = _check_mac_xcode_cli()
        assert r.ok is True
        assert r.name == "mac-xcode-cli"
        assert "n/a" in r.detail

    def test_ok_when_xcode_select_exits_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M2-01: xcode-select exits 0."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "darwin")
        monkeypatch.setattr(
            "rdc.commands.doctor.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="/Library/Developer/CommandLineTools\n"
            ),
        )
        r = _check_mac_xcode_cli()
        assert r.ok is True
        assert "CommandLineTools" in r.detail

    def test_fail_when_xcode_select_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M2-02: xcode-select exits non-zero."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "darwin")
        monkeypatch.setattr(
            "rdc.commands.doctor.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=2, stdout=""),
        )
        r = _check_mac_xcode_cli()
        assert r.ok is False
        assert "xcode-select --install" in r.detail

    def test_fail_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "darwin")

        def _raise(*_a: object, **_kw: object) -> None:
            raise FileNotFoundError("xcode-select not found")

        monkeypatch.setattr("rdc.commands.doctor.subprocess.run", _raise)
        r = _check_mac_xcode_cli()
        assert r.ok is False
        assert "xcode-select --install" in r.detail


class TestMacHomebrew:
    """M2-03, M2-04: _check_mac_homebrew()."""

    def test_non_darwin_returns_na(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
        r = _check_mac_homebrew()
        assert r.ok is True
        assert r.name == "mac-homebrew"
        assert "n/a" in r.detail

    def test_ok_when_brew_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M2-03: brew found, version succeeds."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "darwin")
        monkeypatch.setattr(
            "rdc.commands.doctor.shutil.which", lambda name: "/opt/homebrew/bin/brew"
        )
        monkeypatch.setattr(
            "rdc.commands.doctor.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Homebrew 4.2.0\n"
            ),
        )
        r = _check_mac_homebrew()
        assert r.ok is True
        assert "Homebrew 4.2.0" in r.detail

    def test_fail_when_brew_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M2-04: shutil.which and all fallback paths return nothing."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "darwin")
        monkeypatch.setattr("rdc.commands.doctor.shutil.which", lambda name: None)
        monkeypatch.setattr("rdc.commands.doctor.Path.is_file", lambda _self: False)
        r = _check_mac_homebrew()
        assert r.ok is False
        assert "brew.sh" in r.detail

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX paths only")
    def test_fallback_opt_homebrew(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """B40: brew found via /opt/homebrew/bin/brew when shutil.which fails."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "darwin")
        monkeypatch.setattr("rdc.commands.doctor.shutil.which", lambda name: None)
        monkeypatch.setattr(
            "rdc.commands.doctor.Path.is_file",
            lambda self: str(self) == "/opt/homebrew/bin/brew",
        )
        monkeypatch.setattr(
            "rdc.commands.doctor.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Homebrew 4.3.0\n"
            ),
        )
        r = _check_mac_homebrew()
        assert r.ok is True
        assert "Homebrew 4.3.0" in r.detail

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX paths only")
    def test_fallback_usr_local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """B40: brew found via /usr/local/bin/brew when shutil.which and opt/homebrew fail."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "darwin")
        monkeypatch.setattr("rdc.commands.doctor.shutil.which", lambda name: None)
        monkeypatch.setattr(
            "rdc.commands.doctor.Path.is_file",
            lambda self: str(self) == "/usr/local/bin/brew",
        )
        monkeypatch.setattr(
            "rdc.commands.doctor.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Homebrew 4.1.0\n"
            ),
        )
        r = _check_mac_homebrew()
        assert r.ok is True
        assert "Homebrew 4.1.0" in r.detail


class TestMacRenderdocDylib:
    """M2-05, M2-06: _check_mac_renderdoc_dylib()."""

    def test_non_darwin_returns_na(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
        r = _check_mac_renderdoc_dylib()
        assert r.ok is True
        assert r.name == "mac-renderdoc-dylib"
        assert "n/a" in r.detail

    def test_ok_when_so_exists(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """M2-05: renderdoc.so exists at search path."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "darwin")
        (tmp_path / "renderdoc.so").write_text("fake")
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [str(tmp_path)])
        r = _check_mac_renderdoc_dylib()
        assert r.ok is True
        assert "renderdoc.so" in r.detail

    def test_ok_when_dylib_exists(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """M2-05b: librenderdoc.dylib exists at search path."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "darwin")
        (tmp_path / "librenderdoc.dylib").write_text("fake")
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [str(tmp_path)])
        r = _check_mac_renderdoc_dylib()
        assert r.ok is True
        assert "librenderdoc.dylib" in r.detail

    def test_fail_when_not_found(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """M2-06: no library found."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "darwin")
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [str(tmp_path)])
        r = _check_mac_renderdoc_dylib()
        assert r.ok is False
        assert "not found" in r.detail


class TestMakeBuildHintDarwin:
    """M2-07: _make_build_hint("darwin") contains Homebrew instructions."""

    def test_darwin_hint_contains_homebrew(self) -> None:
        hint = _make_build_hint("darwin")
        assert "brew install cmake ninja" in hint
        assert "build_renderdoc.py" in hint
        assert "https://bananasjim.github.io/rdc-cli/" in hint


class TestImportRenderdocDiagnostics:
    """B45: _import_renderdoc surfaces crash-prone diagnostic."""

    def test_crash_prone_shows_path_and_rebuild_hint(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When candidate is crash-prone, show path and rebuild message."""
        crash_path = str(tmp_path / "incompatible")
        monkeypatch.setattr(
            "rdc.commands.doctor.find_renderdoc",
            lambda: None,
        )
        monkeypatch.setattr(
            "rdc.commands.doctor._get_diagnostic",
            lambda: ProbeOutcome(ProbeResult.CRASH_PRONE, crash_path),
        )

        _, result = _import_renderdoc()

        assert result.ok is False
        assert crash_path in result.detail
        assert "rebuild" in result.detail.lower() or "incompatible" in result.detail.lower()

    def test_no_diagnostic_shows_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no diagnostic available, show generic not found message."""
        monkeypatch.setattr(
            "rdc.commands.doctor.find_renderdoc",
            lambda: None,
        )
        monkeypatch.setattr(
            "rdc.commands.doctor._get_diagnostic",
            lambda: None,
        )

        _, result = _import_renderdoc()

        assert result.ok is False
        assert "not found" in result.detail.lower()

    def test_success_module_returns_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When module found, return ok with version."""
        fake_mod = SimpleNamespace(GetVersionString=lambda: "1.41")
        monkeypatch.setattr(
            "rdc.commands.doctor.find_renderdoc",
            lambda: fake_mod,
        )
        monkeypatch.setattr(
            "rdc.commands.doctor._get_diagnostic",
            lambda: None,
        )

        module, result = _import_renderdoc()

        assert result.ok is True
        assert module is fake_mod
        assert "1.41" in result.detail
