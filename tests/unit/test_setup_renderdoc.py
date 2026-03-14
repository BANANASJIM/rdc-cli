"""Unit tests for rdc setup-renderdoc command."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from click.testing import CliRunner

from rdc.commands.setup_renderdoc import setup_renderdoc_cmd


def test_setup_renderdoc_help() -> None:
    result = CliRunner().invoke(setup_renderdoc_cmd, ["--help"])
    assert result.exit_code == 0
    assert "renderdoc" in result.output.lower()


def test_setup_renderdoc_delegates_no_args() -> None:
    with patch("rdc._build_renderdoc.main") as mock_main:
        CliRunner().invoke(setup_renderdoc_cmd, [])
    mock_main.assert_called_once_with([])


def test_setup_renderdoc_delegates_all_options() -> None:
    with patch("rdc._build_renderdoc.main") as mock_main:
        CliRunner().invoke(
            setup_renderdoc_cmd,
            ["/tmp/install", "--build-dir", "/tmp/build", "--version", "v1.40", "--jobs", "8"],
        )
    mock_main.assert_called_once_with(
        ["/tmp/install", "--build-dir", "/tmp/build", "--version", "v1.40", "--jobs", "8"]
    )


# ---------------------------------------------------------------------------
# --android flag tests
# ---------------------------------------------------------------------------


def _fake_rd_module(tmp_path: Path) -> ModuleType:
    """Create a fake renderdoc module with __file__ and GetVersionString."""
    mod = ModuleType("renderdoc")
    mod.__file__ = str(tmp_path / "lib" / "renderdoc.so")
    mod.GetVersionString = lambda: "v1.41"  # type: ignore[attr-defined]
    return mod


def test_android_flag_happy_path(tmp_path: Path) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    mod = _fake_rd_module(tmp_path)

    with (
        patch("rdc.discover.find_renderdoc", return_value=mod),
        patch("rdc._build_renderdoc.download_android_apks") as mock_dl,
    ):
        result = CliRunner().invoke(setup_renderdoc_cmd, ["--android"])

    assert result.exit_code == 0
    mock_dl.assert_called_once()


def test_android_version_from_module(tmp_path: Path) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    mod = _fake_rd_module(tmp_path)

    with (
        patch("rdc.discover.find_renderdoc", return_value=mod),
        patch("rdc._build_renderdoc.download_android_apks") as mock_dl,
    ):
        CliRunner().invoke(setup_renderdoc_cmd, ["--android"])

    mock_dl.assert_called_once_with("1.41", lib_dir)


def test_android_already_present(tmp_path: Path) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    mod = _fake_rd_module(tmp_path)
    # Create APK dir with an APK
    apk_dir = (lib_dir / ".." / "share" / "renderdoc" / "plugins" / "android").resolve()
    apk_dir.mkdir(parents=True)
    (apk_dir / "test.apk").write_bytes(b"fake")

    with (
        patch("rdc.discover.find_renderdoc", return_value=mod),
        patch("rdc._build_renderdoc.download_android_apks") as mock_dl,
    ):
        result = CliRunner().invoke(setup_renderdoc_cmd, ["--android"])

    assert result.exit_code == 0
    mock_dl.assert_not_called()
    assert "already present" in result.output


def test_android_download_failure(tmp_path: Path) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    mod = _fake_rd_module(tmp_path)

    with (
        patch("rdc.discover.find_renderdoc", return_value=mod),
        patch(
            "rdc._build_renderdoc.download_android_apks",
            side_effect=SystemExit(1),
        ),
    ):
        result = CliRunner().invoke(setup_renderdoc_cmd, ["--android"])

    assert result.exit_code != 0


def test_arm_studio_flag(tmp_path: Path) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    mod = _fake_rd_module(tmp_path)
    arm_dir = tmp_path / "arm-ps"
    arm_dir.mkdir()

    with (
        patch("rdc.discover.find_renderdoc", return_value=mod),
        patch("rdc._build_renderdoc.install_arm_studio") as mock_inst,
    ):
        result = CliRunner().invoke(
            setup_renderdoc_cmd, ["--android", "--arm-studio", str(arm_dir)]
        )

    assert result.exit_code == 0
    mock_inst.assert_called_once_with(arm_dir, lib_dir)


def test_arm_studio_invalid_path(tmp_path: Path) -> None:
    bad = tmp_path / "nonexistent"
    result = CliRunner().invoke(setup_renderdoc_cmd, ["--android", "--arm-studio", str(bad)])
    assert result.exit_code != 0


def test_no_android_flag_skips() -> None:
    with (
        patch("rdc._build_renderdoc.main") as mock_main,
        patch("rdc._build_renderdoc.download_android_apks") as mock_dl,
        patch("rdc._build_renderdoc.install_arm_studio") as mock_inst,
    ):
        CliRunner().invoke(setup_renderdoc_cmd, [])

    mock_dl.assert_not_called()
    mock_inst.assert_not_called()
    mock_main.assert_called_once()


def test_arm_studio_without_android(tmp_path: Path) -> None:
    arm_dir = tmp_path / "arm-ps"
    arm_dir.mkdir()
    result = CliRunner().invoke(setup_renderdoc_cmd, ["--arm-studio", str(arm_dir)])
    assert result.exit_code != 0
