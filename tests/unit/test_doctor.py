from __future__ import annotations

from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from rdc.commands.doctor import doctor_cmd


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


def test_doctor_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: _fake_renderdoc())
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/renderdoccmd")

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 0
    assert "✅" in result.output
    assert "platform" in result.output
    assert "replay-support" in result.output


def test_doctor_failure_when_missing_renderdoccmd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "rdc.commands.doctor.find_renderdoc", lambda: _fake_renderdoc(with_replay=False)
    )
    monkeypatch.setattr("shutil.which", lambda _: None)

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 1
    assert "renderdoccmd" in result.output


def test_doctor_shows_build_hint_when_renderdoc_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rdc.commands.doctor.find_renderdoc", lambda: None)
    monkeypatch.setattr("shutil.which", lambda _: None)

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 1
    assert "not found" in result.output
    assert "cmake -B build -DENABLE_PYRENDERDOC=ON" in result.output
