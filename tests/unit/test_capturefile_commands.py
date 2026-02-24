"""Tests for CaptureFile CLI commands."""

from __future__ import annotations

from click.testing import CliRunner
from conftest import assert_json_output, patch_cli_session

from rdc.commands.capturefile import (
    gpus_cmd,
    section_cmd,
    sections_cmd,
    thumbnail_cmd,
)

# ---------------------------------------------------------------------------
# thumbnail
# ---------------------------------------------------------------------------


def test_thumbnail_cmd(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"data": "AQID", "width": 4, "height": 4})
    result = CliRunner().invoke(thumbnail_cmd, [])
    assert result.exit_code == 0
    assert "4x4" in result.output


def test_thumbnail_cmd_output(monkeypatch, tmp_path) -> None:
    patch_cli_session(monkeypatch, {"data": "AQID", "width": 4, "height": 4})
    out = tmp_path / "thumb.png"
    result = CliRunner().invoke(thumbnail_cmd, ["-o", str(out)])
    assert result.exit_code == 0
    assert out.read_bytes() == b"\x01\x02\x03"
    assert "thumbnail saved:" in result.output


def test_thumbnail_cmd_json(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"data": "AQID", "width": 4, "height": 4})
    result = CliRunner().invoke(thumbnail_cmd, ["--json"])
    data = assert_json_output(result)
    assert data["width"] == 4


# ---------------------------------------------------------------------------
# gpus
# ---------------------------------------------------------------------------


def _gpu_entry() -> dict:
    return {"name": "RTX 4090", "vendor": 0x10DE, "deviceID": 0, "driver": "535"}


def test_gpus_cmd(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"gpus": [_gpu_entry()]})
    result = CliRunner().invoke(gpus_cmd, [])
    assert result.exit_code == 0
    assert "RTX 4090" in result.output


def test_gpus_cmd_json(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"gpus": [_gpu_entry()]})
    result = CliRunner().invoke(gpus_cmd, ["--json"])
    data = assert_json_output(result)
    assert len(data["gpus"]) == 1


def test_gpus_cmd_empty(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"gpus": []})
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
    patch_cli_session(monkeypatch, {"sections": [section]})
    result = CliRunner().invoke(sections_cmd, [])
    assert result.exit_code == 0
    assert "FrameCapture" in result.output


def test_sections_cmd_empty(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"sections": []})
    result = CliRunner().invoke(sections_cmd, [])
    assert result.exit_code == 0
    assert "no sections" in result.output


# ---------------------------------------------------------------------------
# section
# ---------------------------------------------------------------------------


def test_section_cmd(monkeypatch) -> None:
    resp = {"name": "Notes", "contents": "hello world", "encoding": "utf-8"}
    patch_cli_session(monkeypatch, resp)
    result = CliRunner().invoke(section_cmd, ["Notes"])
    assert result.exit_code == 0
    assert "hello world" in result.output


def test_section_cmd_json(monkeypatch) -> None:
    resp = {"name": "Notes", "contents": "hello world", "encoding": "utf-8"}
    patch_cli_session(monkeypatch, resp)
    result = CliRunner().invoke(section_cmd, ["Notes", "--json"])
    data = assert_json_output(result)
    assert data["encoding"] == "utf-8"
