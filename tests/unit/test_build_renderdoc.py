"""Unit tests for scripts/build_renderdoc.py."""

from __future__ import annotations

import hashlib
import importlib
import io
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

br = importlib.import_module("build_renderdoc")

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def test_platform_linux() -> None:
    with patch.object(sys, "platform", "linux"):
        assert br._platform() == "linux"


def test_platform_macos() -> None:
    with patch.object(sys, "platform", "darwin"):
        assert br._platform() == "macos"


def test_platform_windows() -> None:
    with patch.object(sys, "platform", "win32"):
        assert br._platform() == "windows"


# ---------------------------------------------------------------------------
# Default install dir
# ---------------------------------------------------------------------------


def test_default_install_dir_linux() -> None:
    with patch("build_renderdoc._platform", return_value="linux"):
        assert br.default_install_dir() == Path.home() / ".local" / "renderdoc"


def test_default_install_dir_macos() -> None:
    with patch("build_renderdoc._platform", return_value="macos"):
        assert br.default_install_dir() == Path.home() / ".local" / "renderdoc"


def test_default_install_dir_windows() -> None:
    with (
        patch("build_renderdoc._platform", return_value="windows"),
        patch.dict("os.environ", {"LOCALAPPDATA": r"C:\Users\X\AppData\Local"}),
    ):
        assert br.default_install_dir() == Path(r"C:\Users\X\AppData\Local") / "rdc" / "renderdoc"


def test_default_install_dir_windows_no_localappdata() -> None:
    fake_home = Path("/fake/home")
    with (
        patch("build_renderdoc._platform", return_value="windows"),
        patch.dict("os.environ", {}, clear=True),
        patch("build_renderdoc.Path.home", return_value=fake_home),
    ):
        assert br.default_install_dir() == fake_home / "rdc" / "renderdoc"


# ---------------------------------------------------------------------------
# Prerequisite checking
# ---------------------------------------------------------------------------


def _which_factory(available: set[str]):
    """Return a shutil.which replacement that reports only listed tools."""

    def _which(cmd: str) -> str | None:
        return f"/usr/bin/{cmd}" if cmd in available else None

    return _which


def test_check_prerequisites_all_present_linux() -> None:
    with (
        patch("shutil.which", _which_factory({"cmake", "git", "ninja", "python3"})),
    ):
        br.check_prerequisites("linux")


def test_check_prerequisites_missing_cmake() -> None:
    with (
        patch("shutil.which", _which_factory({"git", "ninja", "python3"})),
        pytest.raises(SystemExit),
    ):
        br.check_prerequisites("linux")


def test_check_prerequisites_missing_ninja_linux() -> None:
    with (
        patch("shutil.which", _which_factory({"cmake", "git", "python3"})),
        pytest.raises(SystemExit),
    ):
        br.check_prerequisites("linux")


def test_check_prerequisites_windows_no_cmake_no_ninja() -> None:
    """Windows requires only git (not cmake or ninja)."""
    mock_run = MagicMock(return_value=MagicMock(stdout="C:\\VS\\2022"))
    with (
        patch("shutil.which", _which_factory({"git", "python3", "vswhere"})),
        patch("subprocess.run", mock_run),
    ):
        br.check_prerequisites("windows")


def test_check_prerequisites_windows_vswhere_empty() -> None:
    mock_run = MagicMock(return_value=MagicMock(stdout=""))
    with (
        patch("shutil.which", _which_factory({"cmake", "git", "python3", "vswhere"})),
        patch("subprocess.run", mock_run),
        pytest.raises(SystemExit),
    ):
        br.check_prerequisites("windows")


def test_check_prerequisites_windows_vswhere_missing() -> None:
    with (
        patch("shutil.which", _which_factory({"cmake", "git", "python3"})),
        patch("build_renderdoc.Path.exists", return_value=False),
        pytest.raises(SystemExit),
    ):
        br.check_prerequisites("windows")


# ---------------------------------------------------------------------------
# Clone renderdoc
# ---------------------------------------------------------------------------


def test_clone_renderdoc_fresh(tmp_path: Path) -> None:
    mock_run = MagicMock()
    with patch("subprocess.run", mock_run):
        br.clone_renderdoc(tmp_path)
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "git" in args
    assert "--depth" in args
    assert "1" in args
    assert "--branch" in args
    assert "v1.41" in args


def test_clone_renderdoc_idempotent(tmp_path: Path) -> None:
    (tmp_path / "renderdoc").mkdir()
    mock_run = MagicMock()
    with patch("subprocess.run", mock_run):
        br.clone_renderdoc(tmp_path)
    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# SWIG download
# ---------------------------------------------------------------------------


def _make_zip(tmp_path: Path) -> bytes:
    """Create a minimal zip with the expected SWIG subdir."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{br.SWIG_SUBDIR}/swig.txt", "fake")
    return buf.getvalue()


def test_download_swig_fresh_ok(tmp_path: Path) -> None:
    content = _make_zip(tmp_path)
    sha = hashlib.sha256(content).hexdigest()

    def fake_retrieve(url: str, dest: str) -> tuple[str, None]:
        Path(dest).write_bytes(content)
        return dest, None

    with (
        patch("build_renderdoc.urlretrieve", fake_retrieve),
        patch("build_renderdoc.SWIG_SHA256", sha),
    ):
        br.download_swig(tmp_path)

    assert (tmp_path / "renderdoc-swig").exists()
    assert not (tmp_path / "swig.zip").exists()


def test_download_swig_idempotent(tmp_path: Path) -> None:
    (tmp_path / "renderdoc-swig").mkdir()
    mock_retrieve = MagicMock()
    with patch("build_renderdoc.urlretrieve", mock_retrieve):
        br.download_swig(tmp_path)
    mock_retrieve.assert_not_called()


def test_download_swig_sha256_mismatch(tmp_path: Path) -> None:
    bad_content = b"not the right zip"

    def fake_retrieve(url: str, dest: str) -> tuple[str, None]:
        Path(dest).write_bytes(bad_content)
        return dest, None

    with (
        patch("build_renderdoc.urlretrieve", fake_retrieve),
        pytest.raises(SystemExit),
    ):
        br.download_swig(tmp_path)

    assert not (tmp_path / "swig.zip").exists()


# ---------------------------------------------------------------------------
# _safe_extractall
# ---------------------------------------------------------------------------


def test_safe_extractall_rejects_zipslip(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/evil.txt", "evil")
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf, pytest.raises(SystemExit):
        br._safe_extractall(zf, tmp_path)


def test_safe_extractall_allows_normal_members(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("subdir/file.txt", "hello")
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        br._safe_extractall(zf, tmp_path)
    assert (tmp_path / "subdir" / "file.txt").read_text() == "hello"


# ---------------------------------------------------------------------------
# LTO flag stripping
# ---------------------------------------------------------------------------


def test_strip_lto_removes_flag() -> None:
    env = {
        "CFLAGS": "-O2 -flto=auto -march=native",
        "CXXFLAGS": "-flto=auto",
        "LDFLAGS": "-Wl,-O1 -flto=auto",
    }
    result = br.strip_lto(env)
    assert "-flto=auto" not in result["CFLAGS"]
    assert "-flto=auto" not in result["CXXFLAGS"]
    assert "-flto=auto" not in result["LDFLAGS"]
    assert "-O2" in result["CFLAGS"]


def test_strip_lto_no_flags_present() -> None:
    env = {"CFLAGS": "-O2", "PATH": "/usr/bin"}
    result = br.strip_lto(env)
    assert result["CFLAGS"] == "-O2"
    assert result["PATH"] == "/usr/bin"


def test_strip_lto_does_not_mutate_original() -> None:
    env = {"CFLAGS": "-flto=auto"}
    br.strip_lto(env)
    assert env["CFLAGS"] == "-flto=auto"


# ---------------------------------------------------------------------------
# CMake configuration
# ---------------------------------------------------------------------------


def test_configure_linux_uses_ninja(tmp_path: Path) -> None:
    mock_run = MagicMock()
    (tmp_path / "renderdoc").mkdir()
    with patch("subprocess.run", mock_run):
        br.configure_build(tmp_path, tmp_path / "renderdoc-swig", "linux")
    args = mock_run.call_args[0][0]
    assert "-G" in args
    assert args[args.index("-G") + 1] == "Ninja"


def test_configure_macos_uses_ninja(tmp_path: Path) -> None:
    mock_run = MagicMock()
    (tmp_path / "renderdoc").mkdir()
    with patch("subprocess.run", mock_run):
        br.configure_build(tmp_path, tmp_path / "renderdoc-swig", "macos")
    args = mock_run.call_args[0][0]
    assert args[args.index("-G") + 1] == "Ninja"


def test_configure_common_flags(tmp_path: Path) -> None:
    mock_run = MagicMock()
    (tmp_path / "renderdoc").mkdir()
    with patch("subprocess.run", mock_run):
        br.configure_build(tmp_path, tmp_path / "renderdoc-swig", "linux")
    args = mock_run.call_args[0][0]
    assert "-DENABLE_PYRENDERDOC=ON" in args
    assert "-DENABLE_QRENDERDOC=OFF" in args
    assert "-DENABLE_VULKAN=ON" in args


def test_configure_swig_package_path(tmp_path: Path) -> None:
    mock_run = MagicMock()
    (tmp_path / "renderdoc").mkdir()
    swig_dir = tmp_path / "renderdoc-swig"
    with patch("subprocess.run", mock_run):
        br.configure_build(tmp_path, swig_dir, "linux")
    args = mock_run.call_args[0][0]
    assert f"-DRENDERDOC_SWIG_PACKAGE={swig_dir}" in args


def test_configure_linux_strips_lto(tmp_path: Path) -> None:
    mock_run = MagicMock()
    (tmp_path / "renderdoc").mkdir()
    with (
        patch("subprocess.run", mock_run),
        patch.dict("os.environ", {"CFLAGS": "-flto=auto"}),
    ):
        br.configure_build(tmp_path, tmp_path / "renderdoc-swig", "linux")
    env = mock_run.call_args[1]["env"]
    assert "-flto=auto" not in env.get("CFLAGS", "")


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def test_run_build_parallel_flag_linux(tmp_path: Path) -> None:
    mock_run = MagicMock()
    with patch("subprocess.run", mock_run):
        br.run_build(tmp_path, "linux", jobs=8)
    args = mock_run.call_args[0][0]
    assert "-j" in args
    assert "8" in args


def test_run_build_linux_no_config_flag(tmp_path: Path) -> None:
    mock_run = MagicMock()
    with patch("subprocess.run", mock_run):
        br.run_build(tmp_path, "linux", jobs=4)
    args = mock_run.call_args[0][0]
    assert "--config" not in args


# ---------------------------------------------------------------------------
# Artifact copy
# ---------------------------------------------------------------------------


def test_copy_artifacts_linux(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    src = build_dir / "renderdoc" / "build" / "lib"
    src.mkdir(parents=True)
    (src / "renderdoc.so").write_text("fake")
    (src / "librenderdoc.so").write_text("fake")

    out = tmp_path / "install"
    br.copy_artifacts(build_dir, out, "linux")
    assert (out / "renderdoc.so").exists()
    assert (out / "librenderdoc.so").exists()


def test_copy_artifacts_macos(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    src = build_dir / "renderdoc" / "build" / "lib"
    src.mkdir(parents=True)
    (src / "renderdoc.so").write_text("fake")
    (src / "librenderdoc.so").write_text("fake")

    out = tmp_path / "install"
    br.copy_artifacts(build_dir, out, "macos")
    assert (out / "renderdoc.so").exists()
    assert (out / "librenderdoc.so").exists()


def test_copy_artifacts_macos_dylib_fallback(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    src = build_dir / "renderdoc" / "build" / "lib"
    src.mkdir(parents=True)
    (src / "renderdoc.so").write_text("fake")
    (src / "librenderdoc.dylib").write_text("fake-dylib")

    out = tmp_path / "install"
    br.copy_artifacts(build_dir, out, "macos")
    assert (out / "renderdoc.so").exists()
    assert (out / "librenderdoc.so").exists()
    assert (out / "librenderdoc.dylib").exists()


def test_copy_artifacts_windows(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    release = build_dir / "renderdoc" / "x64" / "Release"
    pymodules = release / "pymodules"
    pymodules.mkdir(parents=True)
    (pymodules / "renderdoc.pyd").write_text("fake")
    (release / "renderdoc.dll").write_text("fake")

    out = tmp_path / "install"
    br.copy_artifacts(build_dir, out, "windows")
    assert (out / "renderdoc.pyd").exists()
    assert (out / "renderdoc.dll").exists()


def test_copy_artifacts_missing_source(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    (build_dir / "renderdoc" / "build" / "lib").mkdir(parents=True)
    out = tmp_path / "install"
    with pytest.raises(SystemExit):
        br.copy_artifacts(build_dir, out, "linux")


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------


def test_main_default_install_dir(tmp_path: Path) -> None:
    with (
        patch("build_renderdoc._artifacts_present", return_value=False),
        patch("build_renderdoc.default_install_dir", return_value=tmp_path / "install"),
        patch("build_renderdoc.check_prerequisites"),
        patch("build_renderdoc.clone_renderdoc"),
        patch("build_renderdoc.download_swig"),
        patch("build_renderdoc.configure_build"),
        patch("build_renderdoc.run_build"),
        patch("build_renderdoc.copy_artifacts") as mock_copy,
    ):
        br.main([])
    assert mock_copy.called
    install_dir = mock_copy.call_args[0][1]
    assert install_dir == tmp_path / "install"


def test_main_custom_install_dir(tmp_path: Path) -> None:
    custom = tmp_path / "custom"
    with (
        patch("build_renderdoc._artifacts_present", return_value=False),
        patch("build_renderdoc.check_prerequisites"),
        patch("build_renderdoc.clone_renderdoc"),
        patch("build_renderdoc.download_swig"),
        patch("build_renderdoc.configure_build"),
        patch("build_renderdoc.run_build"),
        patch("build_renderdoc.copy_artifacts") as mock_copy,
    ):
        br.main([str(custom)])
    install_dir = mock_copy.call_args[0][1]
    assert install_dir == custom


def test_main_custom_build_dir(tmp_path: Path) -> None:
    bd = tmp_path / "mybuild"
    with (
        patch("build_renderdoc._artifacts_present", return_value=False),
        patch("build_renderdoc.check_prerequisites"),
        patch("build_renderdoc.clone_renderdoc") as mock_clone,
        patch("build_renderdoc.download_swig"),
        patch("build_renderdoc.configure_build"),
        patch("build_renderdoc.run_build"),
        patch("build_renderdoc.copy_artifacts"),
    ):
        br.main(["--build-dir", str(bd)])
    build_dir = mock_clone.call_args[0][0]
    assert build_dir == bd


def test_main_idempotent_skip(tmp_path: Path) -> None:
    with (
        patch("build_renderdoc._artifacts_present", return_value=True),
        patch("build_renderdoc.default_install_dir", return_value=tmp_path),
        patch("build_renderdoc.check_prerequisites") as mock_prereq,
    ):
        br.main([])
    mock_prereq.assert_not_called()


def test_main_windows_uses_msbuild(tmp_path: Path) -> None:
    with (
        patch("build_renderdoc._platform", return_value="windows"),
        patch("build_renderdoc._artifacts_present", return_value=False),
        patch("build_renderdoc.default_install_dir", return_value=tmp_path / "install"),
        patch("build_renderdoc.check_prerequisites"),
        patch("build_renderdoc.verify_tool_versions"),
        patch("build_renderdoc.clone_renderdoc"),
        patch("build_renderdoc._prepare_win_python", return_value=Path("C:/prefix")) as mock_prep,
        patch("build_renderdoc._run_msbuild") as mock_msb,
        patch("build_renderdoc.copy_artifacts"),
    ):
        br.main([])
    mock_prep.assert_called_once()
    mock_msb.assert_called_once()


# ---------------------------------------------------------------------------
# MSBuild (Windows)
# ---------------------------------------------------------------------------


def test_find_msbuild_ok(tmp_path: Path) -> None:
    msbuild = tmp_path / "MSBuild" / "Current" / "Bin" / "MSBuild.exe"
    msbuild.parent.mkdir(parents=True)
    msbuild.write_text("fake")
    with patch("build_renderdoc._vs_install_path", return_value=str(tmp_path)):
        result = br._find_msbuild()
    assert result == str(msbuild)


def test_find_msbuild_missing(tmp_path: Path) -> None:
    with (
        patch("build_renderdoc._vs_install_path", return_value=str(tmp_path)),
        pytest.raises(SystemExit),
    ):
        br._find_msbuild()


def test_run_msbuild_args(tmp_path: Path) -> None:
    sln = tmp_path / "renderdoc" / "renderdoc.sln"
    sln.parent.mkdir(parents=True)
    sln.write_text("fake")
    mock_run = MagicMock()
    prefix = Path("C:/python")
    with (
        patch("build_renderdoc._find_msbuild", return_value="MSBuild.exe"),
        patch("subprocess.run", mock_run),
    ):
        br._run_msbuild(tmp_path, prefix, jobs=6)
    args = mock_run.call_args[0][0]
    assert args[0] == "MSBuild.exe"
    assert str(sln) in args
    assert "/p:Configuration=Release" in args
    assert "/p:Platform=x64" in args
    assert "/p:PlatformToolset=v143" in args
    assert "/m:6" in args
    env = mock_run.call_args[1]["env"]
    assert env["RENDERDOC_PYTHON_PREFIX64"] == str(prefix)
    assert env["CL"] == "/wd4996"


def test_run_msbuild_default_jobs(tmp_path: Path) -> None:
    sln = tmp_path / "renderdoc" / "renderdoc.sln"
    sln.parent.mkdir(parents=True)
    sln.write_text("fake")
    mock_run = MagicMock()
    with (
        patch("build_renderdoc._find_msbuild", return_value="MSBuild.exe"),
        patch("subprocess.run", mock_run),
        patch("os.cpu_count", return_value=12),
    ):
        br._run_msbuild(tmp_path, Path("C:/py"))
    args = mock_run.call_args[0][0]
    assert "/m:12" in args


# ---------------------------------------------------------------------------
# _prepare_win_python
# ---------------------------------------------------------------------------


def test_prepare_win_python_creates_dummy_zip(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    (prefix / "include").mkdir(parents=True)
    (prefix / "include" / "Python.h").write_text("fake")
    (prefix / "libs").mkdir()
    (prefix / "libs" / "python314.lib").write_text("fake")

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    with (
        patch("build_renderdoc.sys") as mock_sys,
    ):
        mock_sys.prefix = str(prefix)
        mock_sys.version_info = (3, 14, 3)
        mock_sys.stdout = sys.stdout
        result = br._prepare_win_python(src_dir)

    assert result == prefix
    dummy = prefix / "python314.zip"
    assert dummy.exists()
    with zipfile.ZipFile(dummy) as zf:
        assert "README" in zf.namelist()


def test_prepare_win_python_patches_props(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    (prefix / "include").mkdir(parents=True)
    (prefix / "include" / "Python.h").write_text("fake")
    (prefix / "libs").mkdir()
    (prefix / "libs" / "python314.lib").write_text("fake")

    src_dir = tmp_path / "src"
    props_dir = src_dir / "qrenderdoc" / "Code" / "pyrenderdoc"
    props_dir.mkdir(parents=True)
    props_file = props_dir / "python.props"
    props_file.write_text(
        "<Project>\n"
        "<PropertyGroup><PythonMajorMinorTest>313</PythonMajorMinorTest></PropertyGroup>\n"
        "</Project>\n",
        encoding="utf-8",
    )

    with patch("build_renderdoc.sys") as mock_sys:
        mock_sys.prefix = str(prefix)
        mock_sys.version_info = (3, 14, 3)
        mock_sys.stdout = sys.stdout
        br._prepare_win_python(src_dir)

    content = props_file.read_text(encoding="utf-8")
    assert "314" in content
    assert content.index("314") < content.index("313")


def test_prepare_win_python_missing_lib(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    (prefix / "include").mkdir(parents=True)
    (prefix / "include" / "Python.h").write_text("fake")
    (prefix / "libs").mkdir()

    with (
        patch("build_renderdoc.sys") as mock_sys,
        pytest.raises(SystemExit),
    ):
        mock_sys.prefix = str(prefix)
        mock_sys.version_info = (3, 14, 3)
        mock_sys.stdout = sys.stdout
        br._prepare_win_python(tmp_path / "src")


def test_prepare_win_python_skips_existing_zip(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    (prefix / "include").mkdir(parents=True)
    (prefix / "include" / "Python.h").write_text("fake")
    (prefix / "libs").mkdir()
    (prefix / "libs" / "python314.lib").write_text("fake")
    existing_zip = prefix / "python314.zip"
    existing_zip.write_text("already here")

    with patch("build_renderdoc.sys") as mock_sys:
        mock_sys.prefix = str(prefix)
        mock_sys.version_info = (3, 14, 3)
        mock_sys.stdout = sys.stdout
        br._prepare_win_python(tmp_path / "src")

    assert existing_zip.read_text() == "already here"


def test_prepare_win_python_missing_python_h(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    (prefix / "libs").mkdir(parents=True)
    (prefix / "libs" / "python314.lib").write_text("fake")

    with (
        patch("build_renderdoc.sys") as mock_sys,
        pytest.raises(SystemExit),
    ):
        mock_sys.prefix = str(prefix)
        mock_sys.version_info = (3, 14, 3)
        mock_sys.stdout = sys.stdout
        br._prepare_win_python(tmp_path / "src")


def test_prepare_win_python_props_already_patched(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    (prefix / "include").mkdir(parents=True)
    (prefix / "include" / "Python.h").write_text("fake")
    (prefix / "libs").mkdir()
    (prefix / "libs" / "python314.lib").write_text("fake")

    src_dir = tmp_path / "src"
    props_dir = src_dir / "qrenderdoc" / "Code" / "pyrenderdoc"
    props_dir.mkdir(parents=True)
    props_file = props_dir / "python.props"
    original = (
        "<Project>\n"
        "<PropertyGroup><PythonMajorMinorTest>314</PythonMajorMinorTest></PropertyGroup>\n"
        "</Project>\n"
    )
    props_file.write_text(original, encoding="utf-8")

    with patch("build_renderdoc.sys") as mock_sys:
        mock_sys.prefix = str(prefix)
        mock_sys.version_info = (3, 14, 3)
        mock_sys.stdout = sys.stdout
        br._prepare_win_python(src_dir)

    assert props_file.read_text(encoding="utf-8") == original
