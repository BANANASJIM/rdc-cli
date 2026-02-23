"""Tests for CaptureFile CLI commands."""

from __future__ import annotations

import json

from click.testing import CliRunner

from rdc.commands.capturefile import (
    gpus_cmd,
    section_cmd,
    sections_cmd,
    thumbnail_cmd,
)


def _patch(monkeypatch, response):
    """Patch load_session and send_request for CLI command tests."""
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})


# ---------------------------------------------------------------------------
# thumbnail
# ---------------------------------------------------------------------------


def test_thumbnail_cmd(monkeypatch) -> None:
    _patch(monkeypatch, {"data": "AQID", "width": 4, "height": 4})
    result = CliRunner().invoke(thumbnail_cmd, [])
    assert result.exit_code == 0
    assert "4x4" in result.output


def test_thumbnail_cmd_json(monkeypatch) -> None:
    _patch(monkeypatch, {"data": "AQID", "width": 4, "height": 4})
    result = CliRunner().invoke(thumbnail_cmd, ["--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["width"] == 4


# ---------------------------------------------------------------------------
# gpus
# ---------------------------------------------------------------------------


def _gpu_entry() -> dict:
    return {"name": "RTX 4090", "vendor": 0x10DE, "deviceID": 0, "driver": "535"}


def test_gpus_cmd(monkeypatch) -> None:
    _patch(monkeypatch, {"gpus": [_gpu_entry()]})
    result = CliRunner().invoke(gpus_cmd, [])
    assert result.exit_code == 0
    assert "RTX 4090" in result.output


def test_gpus_cmd_json(monkeypatch) -> None:
    _patch(monkeypatch, {"gpus": [_gpu_entry()]})
    result = CliRunner().invoke(gpus_cmd, ["--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert len(parsed["gpus"]) == 1


def test_gpus_cmd_empty(monkeypatch) -> None:
    _patch(monkeypatch, {"gpus": []})
    result = CliRunner().invoke(gpus_cmd, [])
    assert result.exit_code == 0
    assert "no GPUs found" in result.output


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------


def test_sections_cmd(monkeypatch) -> None:
    section = {
        "index": 0,
        "name": "FrameCapture",
        "type": 1,
        "version": "",
        "compressedSize": 0,
        "uncompressedSize": 1024,
    }
    _patch(monkeypatch, {"sections": [section]})
    result = CliRunner().invoke(sections_cmd, [])
    assert result.exit_code == 0
    assert "FrameCapture" in result.output


def test_sections_cmd_empty(monkeypatch) -> None:
    _patch(monkeypatch, {"sections": []})
    result = CliRunner().invoke(sections_cmd, [])
    assert result.exit_code == 0
    assert "no sections" in result.output


# ---------------------------------------------------------------------------
# section
# ---------------------------------------------------------------------------


def test_section_cmd(monkeypatch) -> None:
    _patch(monkeypatch, {"name": "Notes", "contents": "hello world", "encoding": "utf-8"})
    result = CliRunner().invoke(section_cmd, ["Notes"])
    assert result.exit_code == 0
    assert "hello world" in result.output


def test_section_cmd_json(monkeypatch) -> None:
    _patch(monkeypatch, {"name": "Notes", "contents": "hello world", "encoding": "utf-8"})
    result = CliRunner().invoke(section_cmd, ["Notes", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["encoding"] == "utf-8"
