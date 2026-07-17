"""Tests for the descriptors CLI command."""

from __future__ import annotations

from typing import Any

from click.testing import CliRunner

from rdc.cli import main


def _result() -> dict[str, Any]:
    return {
        "eid": 16,
        "descriptors": [
            {
                "eid": 16,
                "stage": "Pixel",
                "binding": "g_textures",
                "type": "Image",
                "set": 0,
                "array_element": 46,
                "resource_id": 371,
                "resource_name": "2D Image 371",
                "format": "BC1_SRGB",
                "width": 512,
                "height": 512,
                "depth": 4,
                "dimension": 3,
                "texture_type": "Texture3D",
            }
        ],
    }


def test_descriptors_table(monkeypatch) -> None:
    monkeypatch.setattr("rdc.commands.descriptors.call", lambda m, p: _result())
    res = CliRunner().invoke(main, ["descriptors", "16"])
    assert res.exit_code == 0
    assert "BINDING" in res.output
    assert "g_textures" in res.output
    assert "BC1_SRGB" in res.output
    assert "512" in res.output
    assert "DEPTH" in res.output
    assert "\t4\n" in res.output


def test_descriptors_binding_filter_forwarded(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        captured.update(params)
        return _result()

    monkeypatch.setattr("rdc.commands.descriptors.call", fake_call)
    res = CliRunner().invoke(
        main, ["descriptors", "16", "--binding", "g_textures", "--stage", "ps"]
    )
    assert res.exit_code == 0
    assert captured["binding"] == "g_textures"
    assert captured["stage"] == "ps"
    assert captured["eid"] == 16


def test_descriptors_quiet_emits_resource_ids(monkeypatch) -> None:
    monkeypatch.setattr("rdc.commands.descriptors.call", lambda m, p: _result())
    res = CliRunner().invoke(main, ["descriptors", "16", "-q"])
    assert res.exit_code == 0
    assert res.output.strip() == "371"


def test_descriptors_json(monkeypatch) -> None:
    monkeypatch.setattr("rdc.commands.descriptors.call", lambda m, p: _result())
    res = CliRunner().invoke(main, ["descriptors", "16", "--json"])
    assert res.exit_code == 0
    assert '"binding": "g_textures"' in res.output
