"""Tests for `rdc open` capture argument shell completion."""

from __future__ import annotations

from pathlib import Path

from rdc.commands.session import _complete_capture_path, open_cmd


def _capture_param(cmd):
    return next(p for p in cmd.params if p.name == "capture")


def test_open_cmd_capture_has_shell_complete() -> None:
    assert _capture_param(open_cmd).shell_complete is not None


def test_complete_capture_suggests_dirs_and_rdc(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "captures").mkdir()
    (tmp_path / "frame.rdc").touch()
    (tmp_path / "notes.txt").touch()

    values = [item.value for item in _complete_capture_path(None, None, "")]
    assert "captures/" in values
    assert "frame.rdc" in values
    assert "notes.txt" not in values


def test_complete_capture_accepts_uppercase_rdc_suffix(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "FRAME.RDC").touch()

    values = [item.value for item in _complete_capture_path(None, None, "")]
    assert "FRAME.RDC" in values


def test_complete_capture_nested_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "captures").mkdir()
    (tmp_path / "captures" / "a.rdc").touch()
    (tmp_path / "captures" / "ignore.bin").touch()
    (tmp_path / "captures" / "nested").mkdir()

    values = [item.value for item in _complete_capture_path(None, None, "captures/")]
    assert "captures/a.rdc" in values
    assert "captures/nested/" in values
    assert "captures/ignore.bin" not in values


def test_complete_capture_nested_path_with_backslashes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "captures").mkdir()
    (tmp_path / "captures" / "a.rdc").touch()
    (tmp_path / "captures" / "b.rdc").touch()
    (tmp_path / "captures" / "nested").mkdir()

    values = [item.value for item in _complete_capture_path(None, None, "captures\\a")]
    assert "captures/a.rdc" in values
    assert "captures/b.rdc" not in values
    assert "captures/nested/" not in values
