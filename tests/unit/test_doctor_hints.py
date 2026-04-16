"""Unit tests for doctor HINT_MAP integration."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from rdc.commands.doctor import HINT_MAP, doctor_cmd

_ALL_CHECK_NAMES = {
    "python",
    "platform",
    "renderdoc-module",
    "replay-support",
    "renderdoccmd",
    "win-python-version",
    "win-vs-build-tools",
    "win-renderdoc-install",
    "win-vulkan-layer",
    "mac-xcode-cli",
    "mac-homebrew",
    "mac-renderdoc-dylib",
    "adb",
    "android-apk",
    "renderdoc-variant",
}


def test_all_hint_map_keys_are_valid_check_names() -> None:
    """Every key in HINT_MAP must be a known check name."""
    for key in HINT_MAP:
        assert key in _ALL_CHECK_NAMES, f"HINT_MAP key '{key}' is not a known check name"


def test_renderdoc_module_failure_emits_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: None)
    monkeypatch.setattr("rdc.commands.doctor._get_diagnostic", lambda: None)
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoccmd", lambda: None)

    result = CliRunner().invoke(doctor_cmd, [])
    assert "hint:" in result.output
    assert "renderdoc" in result.output.lower()


def _fake_rd() -> SimpleNamespace:
    return SimpleNamespace(
        GetVersionString=lambda: "1.33",
        __file__="/fake/renderdoc.so",
        InitialiseReplay=lambda *a, **kw: 0,
        ShutdownReplay=lambda: None,
        GlobalEnvironment=lambda: object(),
    )


def test_renderdoccmd_failure_emits_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: _fake_rd())
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoccmd", lambda: None)

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 1
    assert "hint:" in result.output
    assert "renderdoccmd" in result.output


def test_passing_check_emits_no_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: _fake_rd())
    monkeypatch.setattr(
        "rdc.commands.doctor.find_renderdoccmd", lambda: Path("/usr/bin/renderdoccmd")
    )
    monkeypatch.setattr(
        "rdc.commands.doctor.subprocess.run",
        lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=0, stdout="v1.33"),
    )

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 0
    assert "hint:" not in result.output


def test_exit_code_preserved_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: None)
    monkeypatch.setattr("rdc.commands.doctor._get_diagnostic", lambda: None)
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoccmd", lambda: None)

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 1


def test_output_order_check_then_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hints appear after the check line, not before."""
    monkeypatch.setattr("rdc.commands.doctor.sys.platform", "linux")
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: None)
    monkeypatch.setattr("rdc.commands.doctor._get_diagnostic", lambda: None)
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoccmd", lambda: None)

    result = CliRunner().invoke(doctor_cmd, [])
    output = result.output
    fail_pos = output.find("[FAIL] renderdoc-module")
    hint_pos = output.find("hint:")
    assert fail_pos != -1
    assert hint_pos != -1
    assert fail_pos < hint_pos, "hint must appear after [FAIL] line"
