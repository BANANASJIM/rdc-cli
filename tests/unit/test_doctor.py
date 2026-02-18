from __future__ import annotations

import importlib
from types import SimpleNamespace

from click.testing import CliRunner

from rdc.commands.doctor import doctor_cmd


def test_doctor_success(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_import_module(name: str):
        assert name == "renderdoc"
        return SimpleNamespace(GetVersionString=lambda: "1.33")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/renderdoccmd")

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 0
    assert "✅" in result.output


def test_doctor_failure_when_missing_renderdoccmd(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_import_module(name: str):
        assert name == "renderdoc"
        return SimpleNamespace(GetVersionString=lambda: "1.33")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    monkeypatch.setattr("shutil.which", lambda _: None)

    result = CliRunner().invoke(doctor_cmd, [])
    assert result.exit_code == 1
    assert "renderdoccmd" in result.output
