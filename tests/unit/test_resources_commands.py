"""Tests for rdc resources/resource/passes/pass CLI commands."""

from __future__ import annotations

from click.testing import CliRunner
from conftest import assert_jsonl_output, patch_cli_session

from rdc.commands.resources import pass_cmd, passes_cmd, resource_cmd, resources_cmd


def test_resources_tsv(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "rows": [
                {"id": 1, "type": "Texture", "name": "Albedo"},
                {"id": 2, "type": "Buffer", "name": "VBO"},
            ]
        },
    )
    result = CliRunner().invoke(resources_cmd, [])
    assert result.exit_code == 0
    assert "Albedo" in result.output
    assert "Texture" in result.output


def test_resources_json(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {"rows": [{"id": 1, "type": "Texture", "name": "Albedo"}]},
    )
    result = CliRunner().invoke(resources_cmd, ["--json"])
    assert result.exit_code == 0
    assert '"id": 1' in result.output


def test_resources_no_session(monkeypatch) -> None:
    patch_cli_session(monkeypatch, None)
    result = CliRunner().invoke(resources_cmd, [])
    assert result.exit_code == 1


def test_resource_detail_tsv(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {"resource": {"id": 1, "type": "Texture", "name": "Albedo"}},
    )
    result = CliRunner().invoke(resource_cmd, ["1"])
    assert result.exit_code == 0
    assert "Albedo" in result.output


def test_resource_detail_json(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"resource": {"id": 1, "type": "Texture2D", "name": "Albedo"}})
    result = CliRunner().invoke(resource_cmd, ["1", "--json"])
    assert result.exit_code == 0
    assert '"id": 1' in result.output


def test_resource_error(monkeypatch) -> None:
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod,
        "send_request",
        lambda _h, _p, _payload, **_kw: {"error": {"message": "resource not found"}},
    )
    result = CliRunner().invoke(resource_cmd, ["999"])
    assert result.exit_code == 1


def test_passes_tsv(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {"tree": {"passes": [{"name": "Shadow", "draws": 3}, {"name": "Main", "draws": 12}]}},
    )
    result = CliRunner().invoke(passes_cmd, [])
    assert result.exit_code == 0
    assert "Shadow" in result.output
    assert "Main" in result.output


def test_passes_json(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {"tree": {"passes": [{"name": "Shadow", "draws": 3}]}},
    )
    result = CliRunner().invoke(passes_cmd, ["--json"])
    assert result.exit_code == 0
    assert '"Shadow"' in result.output


def test_passes_no_session(monkeypatch) -> None:
    patch_cli_session(monkeypatch, None)
    result = CliRunner().invoke(passes_cmd, [])
    assert result.exit_code == 1


def test_pass_detail_tsv(monkeypatch) -> None:
    patch_cli_session(
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
    assert "Color Targets:" in result.output
    assert "Depth Target:" in result.output


def test_pass_detail_by_name(monkeypatch) -> None:
    patch_cli_session(
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
    patch_cli_session(
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
    patch_cli_session(monkeypatch, None)
    result = CliRunner().invoke(pass_cmd, ["0"])
    assert result.exit_code == 1


def test_pass_help_mentions_zero_based_index() -> None:
    result = CliRunner().invoke(pass_cmd, ["--help"])
    assert result.exit_code == 0
    assert "0-based index" in result.output


# ── resources output options ────────────────────────────────────────

_RESOURCES_ROWS = {
    "rows": [
        {"id": 1, "type": "Texture", "name": "Albedo"},
        {"id": 2, "type": "Buffer", "name": "VBO"},
    ]
}


def test_resources_default_has_header(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _RESOURCES_ROWS)
    result = CliRunner().invoke(resources_cmd, [])
    assert result.exit_code == 0
    assert "ID\tTYPE\tNAME" in result.output


def test_resources_no_header(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _RESOURCES_ROWS)
    result = CliRunner().invoke(resources_cmd, ["--no-header"])
    assert result.exit_code == 0
    assert "ID\tTYPE\tNAME" not in result.output
    assert "Albedo" in result.output


def test_resources_jsonl(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _RESOURCES_ROWS)
    result = CliRunner().invoke(resources_cmd, ["--jsonl"])
    lines = assert_jsonl_output(result, 2)
    assert lines[0]["id"] == 1


def test_resources_quiet(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _RESOURCES_ROWS)
    result = CliRunner().invoke(resources_cmd, ["-q"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["1", "2"]


# ── passes output options ──────────────────────────────────────────

_PASSES_TREE = {"tree": {"passes": [{"name": "Shadow", "draws": 3}, {"name": "Main", "draws": 12}]}}


def test_passes_default_has_header(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _PASSES_TREE)
    result = CliRunner().invoke(passes_cmd, [])
    assert result.exit_code == 0
    assert "NAME\tDRAWS" in result.output


def test_passes_no_header(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _PASSES_TREE)
    result = CliRunner().invoke(passes_cmd, ["--no-header"])
    assert result.exit_code == 0
    assert "NAME\tDRAWS" not in result.output
    assert "Shadow" in result.output


def test_passes_jsonl(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _PASSES_TREE)
    result = CliRunner().invoke(passes_cmd, ["--jsonl"])
    lines = assert_jsonl_output(result, 2)
    assert lines[0]["name"] == "Shadow"


def test_passes_quiet(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _PASSES_TREE)
    result = CliRunner().invoke(passes_cmd, ["-q"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["Shadow", "Main"]
