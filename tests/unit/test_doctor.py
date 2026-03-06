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
    _check_win_vulkan_layer,
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
    assert "[ok]" in result.output
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
        "  Run: rdc setup-renderdoc\n"
        "  Full instructions: https://bananasjim.github.io/rdc-cli/docs/install/\n"
        "  Then re-run: rdc doctor",
    )
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: None)
    monkeypatch.setattr("rdc.commands.doctor._get_diagnostic", lambda: None)
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoccmd", lambda: None)

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 1
    assert "not found" in result.output
    assert "renderdoc is not available on PyPI" in result.output


def test_doctor_hint_contains_docs_url() -> None:
    from rdc.commands.doctor import _RENDERDOC_BUILD_HINT

    assert "https://bananasjim.github.io/rdc-cli/docs/install/" in _RENDERDOC_BUILD_HINT


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

    def test_pyd_version_mismatch_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-003: tagged pyd mismatches running Python, falls through to plain pyd."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [r"C:\RenderDoc"])
        monkeypatch.setattr(
            "rdc.commands.doctor.glob.glob",
            lambda _pattern: [r"C:\RenderDoc\renderdoc.cpython-310-win_amd64.pyd"],
        )
        vi = type("VI", (), {"__getitem__": lambda s, k: (3, 12)[k]})()
        monkeypatch.setattr("rdc.commands.doctor.sys.version_info", vi)
        monkeypatch.setattr("rdc.commands.doctor.Path.is_file", lambda _self: False)
        r = _check_win_python_version()
        assert r.ok is False
        assert "not found" in r.detail.lower()

    def test_pyd_mismatch_fallback_to_plain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tagged pyd mismatches but plain renderdoc.pyd exists -- accept MSBuild output."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [r"C:\RenderDoc"])
        monkeypatch.setattr(
            "rdc.commands.doctor.glob.glob",
            lambda _pattern: [r"C:\RenderDoc\renderdoc.cpython-310-win_amd64.pyd"],
        )
        vi = type("VI", (), {"__getitem__": lambda s, k: (3, 12)[k]})()
        monkeypatch.setattr("rdc.commands.doctor.sys.version_info", vi)
        monkeypatch.setattr("rdc.commands.doctor.Path.is_file", lambda _self: True)
        r = _check_win_python_version()
        assert r.ok is True
        assert "MSBuild" in r.detail

    def test_no_pyd_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-004: no .pyd found in search paths."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [r"C:\RenderDoc"])
        monkeypatch.setattr("rdc.commands.doctor.glob.glob", lambda _pattern: [])
        monkeypatch.setattr("rdc.commands.doctor.Path.is_file", lambda _self: False)
        r = _check_win_python_version()
        assert r.ok is False
        assert "not found" in r.detail.lower()

    def test_msbuild_plain_pyd_accepted(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """MSBuild-produced renderdoc.pyd (no cpython tag) is accepted."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        (tmp_path / "renderdoc.pyd").write_text("fake")
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [str(tmp_path)])
        monkeypatch.setattr("rdc.commands.doctor.glob.glob", lambda _pattern: [])
        r = _check_win_python_version()
        assert r.ok is True
        assert "MSBuild" in r.detail
        assert "renderdoc.pyd" in r.detail


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
        monkeypatch.setattr("rdc.commands.doctor.os.environ", {})
        monkeypatch.setattr(
            "rdc._platform.renderdoc_search_paths",
            lambda: [r"C:\Program Files\RenderDoc"],
        )

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
        env = {"RENDERDOC_PYTHON_PATH": str(tmp_path)}
        monkeypatch.setattr("rdc.commands.doctor.os.environ", env)
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [])
        r = _check_win_renderdoc_install()
        assert r.ok is True
        assert str(tmp_path) in r.detail

    def test_found_at_localappdata_rdc(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """renderdoc.dll found at %LOCALAPPDATA%\\rdc\\renderdoc via search paths."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        rdc_dir = tmp_path / "rdc" / "renderdoc"
        rdc_dir.mkdir(parents=True)
        (rdc_dir / "renderdoc.dll").write_text("fake")
        monkeypatch.setattr("rdc.commands.doctor.os.environ", {})
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [str(rdc_dir)])
        r = _check_win_renderdoc_install()
        assert r.ok is True
        assert "renderdoc.dll" in r.detail

    def test_not_found_anywhere(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TP-W3-014: renderdoc.dll not found anywhere."""
        monkeypatch.setattr("rdc.commands.doctor.sys.platform", "win32")
        monkeypatch.setattr("rdc.commands.doctor.os.environ", {})
        monkeypatch.setattr("rdc._platform.renderdoc_search_paths", lambda: [])
        monkeypatch.setattr("rdc.commands.doctor.Path.exists", lambda _self: False)
        r = _check_win_renderdoc_install()
        assert r.ok is False
        assert "RENDERDOC_PYTHON_PATH" in r.detail


# ── Group Z: _make_build_hint() ───────────────────────────────────────


class TestMakeBuildHint:
    """TP-W3-015 and TP-W3-016."""

    def test_linux_hint_contains_setup_renderdoc(self) -> None:
        """TP-W3-015: Linux hint has rdc setup-renderdoc."""
        hint = _make_build_hint("linux")
        assert "rdc setup-renderdoc" in hint
        assert "https://bananasjim.github.io/rdc-cli/docs/install/" in hint

    def test_windows_hint_contains_setup_renderdoc(self) -> None:
        """TP-W3-016: Windows hint has rdc setup-renderdoc."""
        hint = _make_build_hint("win32")
        assert "rdc setup-renderdoc" in hint
        assert "https://bananasjim.github.io/rdc-cli/docs/install/" in hint


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
    monkeypatch.setattr(
        "rdc.commands.doctor._check_win_vulkan_layer",
        lambda: CheckResult("win-vulkan-layer", True, "ok"),
    )
    win_count = len(run_doctor())

    assert win_count - linux_count == 4


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

    def test_darwin_hint_contains_setup_renderdoc(self) -> None:
        hint = _make_build_hint("darwin")
        assert "rdc setup-renderdoc" in hint
        assert "https://bananasjim.github.io/rdc-cli/docs/install/" in hint


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


# ── Vulkan layer check ───────────────────────────────────────────────


class TestCheckWinVulkanLayer:
    @pytest.mark.skipif(sys.platform == "win32", reason="non-Windows test")
    def test_skipped_on_non_windows(self) -> None:
        result = _check_win_vulkan_layer()
        assert result.ok is True
        assert result.detail == "n/a"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_fail_when_not_registered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import winreg

        def _fake_open(hive: int, path: str) -> None:
            raise OSError("not found")

        monkeypatch.setattr(winreg, "OpenKey", _fake_open)
        result = _check_win_vulkan_layer()
        assert result.ok is False
        assert "not registered" in result.detail

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_fail_when_json_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        import winreg

        fake_json = str(tmp_path / "renderdoc_layer.json")

        class _FakeKey:
            def __enter__(self) -> _FakeKey:
                return self

            def __exit__(self, *a: object) -> None:
                pass

        def _fake_open(hive: int, path: str) -> _FakeKey:
            return _FakeKey()

        call_count = [0]

        def _fake_enum(_key: object, i: int) -> tuple[str, int, int]:
            if call_count[0] > 0:
                raise OSError("done")
            call_count[0] += 1
            return (fake_json, 0, winreg.REG_DWORD)

        monkeypatch.setattr(winreg, "OpenKey", _fake_open)
        monkeypatch.setattr(winreg, "EnumValue", _fake_enum)
        result = _check_win_vulkan_layer()
        assert result.ok is False
        assert "not found" in result.detail

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_success_when_registered(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        import winreg

        dll = tmp_path / "renderdoc.dll"
        dll.write_bytes(b"\x00")
        layer_json = tmp_path / "renderdoc.json"
        layer_json.write_text(
            '{"layer":{"library_path":".\\\\renderdoc.dll"}}',
            encoding="utf-8",
        )

        class _FakeKey:
            def __enter__(self) -> _FakeKey:
                return self

            def __exit__(self, *a: object) -> None:
                pass

        def _fake_open(hive: int, path: str) -> _FakeKey:
            return _FakeKey()

        call_count = [0]

        def _fake_enum(_key: object, i: int) -> tuple[str, int, int]:
            if call_count[0] > 0:
                raise OSError("done")
            call_count[0] += 1
            return (str(layer_json), 0, winreg.REG_DWORD)

        monkeypatch.setattr(winreg, "OpenKey", _fake_open)
        monkeypatch.setattr(winreg, "EnumValue", _fake_enum)
        result = _check_win_vulkan_layer()
        assert result.ok is True
        assert "registered" in result.detail
