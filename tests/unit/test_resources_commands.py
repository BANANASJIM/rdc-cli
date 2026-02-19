"""Tests for rdc resources/resource/passes/pass CLI commands."""

from __future__ import annotations

from click.testing import CliRunner

from rdc.commands.resources import pass_cmd, passes_cmd, resource_cmd, resources_cmd


def _patch_resources(monkeypatch, response):
    import rdc.commands.resources as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})


def test_resources_tsv(monkeypatch) -> None:
    _patch_resources(
        monkeypatch,
        {
            "rows": [
                {
                    "id": 1,
                    "type": "Texture2D",
                    "name": "Albedo",
                    "width": 1024,
                    "height": 1024,
                    "depth": 1,
                    "format": "R8G8B8A8_UNORM",
                },
                {
                    "id": 2,
                    "type": "Buffer",
                    "name": "VBO",
                    "width": 0,
                    "height": 0,
                    "depth": 0,
                    "format": "",
                },
            ]
        },
    )
    result = CliRunner().invoke(resources_cmd, [])
    assert result.exit_code == 0
    assert "Albedo" in result.output
    assert "1024" in result.output


def test_resources_json(monkeypatch) -> None:
    _patch_resources(
        monkeypatch,
        {
            "rows": [
                {
                    "id": 1,
                    "type": "Texture2D",
                    "name": "Albedo",
                    "width": 1024,
                    "height": 1024,
                    "depth": 1,
                    "format": "R8G8B8A8_UNORM",
                }
            ]
        },
    )
    result = CliRunner().invoke(resources_cmd, ["--json"])
    assert result.exit_code == 0
    assert '"id": 1' in result.output


def test_resources_no_session(monkeypatch) -> None:
    import rdc.commands.resources as mod

    monkeypatch.setattr(mod, "load_session", lambda: None)
    result = CliRunner().invoke(resources_cmd, [])
    assert result.exit_code == 1


def test_resource_detail_tsv(monkeypatch) -> None:
    _patch_resources(
        monkeypatch,
        {
            "resource": {
                "id": 1,
                "type": "Texture2D",
                "name": "Albedo",
                "width": 1024,
                "height": 1024,
            }
        },
    )
    result = CliRunner().invoke(resource_cmd, ["1"])
    assert result.exit_code == 0
    assert "Albedo" in result.output


def test_resource_detail_json(monkeypatch) -> None:
    _patch_resources(monkeypatch, {"resource": {"id": 1, "type": "Texture2D", "name": "Albedo"}})
    result = CliRunner().invoke(resource_cmd, ["1", "--json"])
    assert result.exit_code == 0
    assert '"id": 1' in result.output


def test_resource_error(monkeypatch) -> None:
    import rdc.commands.resources as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod, "send_request", lambda _h, _p, _payload: {"error": {"message": "resource not found"}}
    )
    result = CliRunner().invoke(resource_cmd, ["999"])
    assert result.exit_code == 1


def test_passes_tsv(monkeypatch) -> None:
    _patch_resources(
        monkeypatch,
        {"tree": {"passes": [{"name": "Shadow", "draws": 3}, {"name": "Main", "draws": 12}]}},
    )
    result = CliRunner().invoke(passes_cmd, [])
    assert result.exit_code == 0
    assert "Shadow" in result.output
    assert "Main" in result.output


def test_passes_json(monkeypatch) -> None:
    _patch_resources(
        monkeypatch,
        {"tree": {"passes": [{"name": "Shadow", "draws": 3}]}},
    )
    result = CliRunner().invoke(passes_cmd, ["--json"])
    assert result.exit_code == 0
    assert '"Shadow"' in result.output


def test_passes_no_session(monkeypatch) -> None:
    import rdc.commands.resources as mod

    monkeypatch.setattr(mod, "load_session", lambda: None)
    result = CliRunner().invoke(passes_cmd, [])
    assert result.exit_code == 1


def test_pass_detail_tsv(monkeypatch) -> None:
    _patch_resources(
        monkeypatch,
        {
            "name": "Shadow",
            "begin_eid": 10,
            "end_eid": 50,
            "draws": 3,
            "dispatches": 0,
            "triangles": 12000,
            "color_targets": [{"id": 10}],
            "depth_target": 20,
        },
    )
    result = CliRunner().invoke(pass_cmd, ["0"])
    assert result.exit_code == 0
    assert "Shadow" in result.output
    assert "10" in result.output
    assert "12000" in result.output


def test_pass_detail_by_name(monkeypatch) -> None:
    _patch_resources(
        monkeypatch,
        {
            "name": "GBuffer",
            "begin_eid": 90,
            "end_eid": 450,
            "draws": 450,
            "dispatches": 0,
            "triangles": 4800000,
        },
    )
    result = CliRunner().invoke(pass_cmd, ["GBuffer"])
    assert result.exit_code == 0
    assert "GBuffer" in result.output


def test_pass_detail_json(monkeypatch) -> None:
    _patch_resources(
        monkeypatch,
        {
            "name": "Shadow",
            "begin_eid": 10,
            "end_eid": 50,
            "draws": 3,
            "dispatches": 0,
            "triangles": 12000,
        },
    )
    result = CliRunner().invoke(pass_cmd, ["0", "--json"])
    assert result.exit_code == 0
    assert '"name": "Shadow"' in result.output


def test_pass_no_session(monkeypatch) -> None:
    import rdc.commands.resources as mod

    monkeypatch.setattr(mod, "load_session", lambda: None)
    result = CliRunner().invoke(pass_cmd, ["0"])
    assert result.exit_code == 1
