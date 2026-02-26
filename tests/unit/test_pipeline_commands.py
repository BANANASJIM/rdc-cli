"""Tests for rdc pipeline/shader/bindings/shaders CLI commands - extended coverage."""

from __future__ import annotations

from click.testing import CliRunner
from conftest import assert_jsonl_output, patch_cli_session

from rdc.cli import main


def test_pipeline_tsv(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "row": {
                "eid": 10,
                "api": "Vulkan",
                "topology": "TriangleList",
                "graphics_pipeline": "1",
                "compute_pipeline": "0",
            }
        },
    )
    result = CliRunner().invoke(main, ["pipeline"])
    assert result.exit_code == 0
    assert "Vulkan" in result.output
    assert "TriangleList" in result.output


def test_pipeline_with_section(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "row": {
                "eid": 10,
                "api": "Vulkan",
                "topology": "TriangleList",
                "graphics_pipeline": "1",
                "compute_pipeline": "0",
                "section": "ps",
                "section_detail": {
                    "stage": "ps",
                    "shader": 101,
                    "entry": "main",
                    "ro": 1,
                    "rw": 0,
                    "cbuffers": 1,
                },
            }
        },
    )
    result = CliRunner().invoke(main, ["pipeline", "10", "ps"])
    assert result.exit_code == 0
    assert "ps" in result.output


def test_bindings_tsv(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "rows": [
                {"eid": 10, "stage": "ps", "kind": "RO", "slot": 0, "name": "albedo"},
                {"eid": 10, "stage": "ps", "kind": "RW", "slot": 1, "name": "rwbuf"},
            ]
        },
    )
    result = CliRunner().invoke(main, ["bindings"])
    assert result.exit_code == 0
    assert "albedo" in result.output


def test_bindings_json(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {"rows": [{"eid": 10, "stage": "ps", "kind": "RO", "slot": 0, "name": "albedo"}]},
    )
    result = CliRunner().invoke(main, ["bindings", "--json"])
    assert result.exit_code == 0
    assert '"name": "albedo"' in result.output


def test_bindings_with_filters(monkeypatch) -> None:
    calls: list[dict] = []
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def capture(h, p, payload):
        calls.append(payload)
        return {"result": {"rows": []}}

    monkeypatch.setattr(mod, "send_request", capture)
    CliRunner().invoke(main, ["bindings", "10", "--binding", "0"])
    assert calls[0]["params"]["binding"] == 0


def test_shader_targets(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"targets": ["SPIR-V", "GLSL"]})
    result = CliRunner().invoke(main, ["shader", "--targets"])
    assert result.exit_code == 0
    assert "SPIR-V" in result.output


def test_shader_targets_json(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"targets": ["SPIR-V", "GLSL"]})
    result = CliRunner().invoke(main, ["shader", "--targets", "--json"])
    assert result.exit_code == 0
    assert "SPIR-V" in result.output


def test_shader_all(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "eid": 10,
            "stages": [
                {
                    "eid": 10,
                    "stage": "ps",
                    "shader": 101,
                    "entry": "main_ps",
                    "ro": 1,
                    "rw": 1,
                    "cbuffers": 1,
                },
            ],
        },
    )
    result = CliRunner().invoke(main, ["shader", "--all"])
    assert result.exit_code == 0
    assert "main_ps" in result.output


def test_shader_all_json(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "eid": 10,
            "stages": [
                {
                    "eid": 10,
                    "stage": "ps",
                    "shader": 101,
                    "entry": "main_ps",
                    "ro": 1,
                    "rw": 1,
                    "cbuffers": 1,
                },
            ],
        },
    )
    result = CliRunner().invoke(main, ["shader", "--all", "--json"])
    assert result.exit_code == 0
    assert '"shader": 101' in result.output


def test_shader_single_tsv(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "row": {
                "eid": 10,
                "stage": "ps",
                "shader": 101,
                "entry": "main_ps",
                "ro": 1,
                "rw": 0,
                "cbuffers": 1,
            }
        },
    )
    result = CliRunner().invoke(main, ["shader", "10", "ps"])
    assert result.exit_code == 0
    assert "main_ps" in result.output


def test_shader_single_json(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "row": {
                "eid": 10,
                "stage": "ps",
                "shader": 101,
                "entry": "main_ps",
                "ro": 1,
                "rw": 0,
                "cbuffers": 1,
            }
        },
    )
    result = CliRunner().invoke(main, ["shader", "10", "ps", "--json"])
    assert result.exit_code == 0
    assert '"shader": 101' in result.output


def test_shader_stage_only_uses_current_eid(monkeypatch) -> None:
    calls: list[dict] = []
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def capture(_h, _p, payload):
        calls.append(payload)
        return {
            "result": {
                "row": {
                    "eid": 77,
                    "stage": "ps",
                    "shader": 101,
                    "entry": "main_ps",
                    "ro": 1,
                    "rw": 0,
                    "cbuffers": 1,
                }
            }
        }

    monkeypatch.setattr(mod, "send_request", capture)

    result = CliRunner().invoke(main, ["shader", "ps"])

    assert result.exit_code == 0
    assert calls[0]["method"] == "shader"
    assert calls[0]["params"]["stage"] == "ps"
    assert "eid" not in calls[0]["params"]


def test_shader_explicit_eid_stage_form_still_supported(monkeypatch) -> None:
    calls: list[dict] = []
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def capture(_h, _p, payload):
        calls.append(payload)
        return {
            "result": {
                "row": {
                    "eid": 10,
                    "stage": "ps",
                    "shader": 101,
                    "entry": "main_ps",
                    "ro": 1,
                    "rw": 0,
                    "cbuffers": 1,
                }
            }
        }

    monkeypatch.setattr(mod, "send_request", capture)

    result = CliRunner().invoke(main, ["shader", "10", "ps"])

    assert result.exit_code == 0
    assert calls[0]["method"] == "shader"
    assert calls[0]["params"]["eid"] == 10
    assert calls[0]["params"]["stage"] == "ps"


def test_shader_with_source_output(monkeypatch, tmp_path) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "row": {
                "eid": 10,
                "stage": "ps",
                "shader": 101,
                "entry": "main_ps",
                "ro": 1,
                "rw": 0,
                "cbuffers": 1,
                "content": "#version 450\nvoid main() {}",
            }
        },
    )
    out = tmp_path / "shader.glsl"
    result = CliRunner().invoke(main, ["shader", "10", "ps", "--source", "-o", str(out)])
    assert result.exit_code == 0
    assert out.read_text() == "#version 450\nvoid main() {}"


def test_shader_with_reflect(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "row": {
                "eid": 10,
                "stage": "ps",
                "shader": 101,
                "entry": "main_ps",
                "ro": 1,
                "rw": 0,
                "cbuffers": 1,
                "reflection": {
                    "inputs": [{"name": "v_pos", "type": "float4", "location": 0}],
                    "outputs": [{"name": "o_color", "type": "float4", "location": 0}],
                    "cbuffers": [{"name": "Globals", "slot": 0, "vars": 3}],
                },
            }
        },
    )
    result = CliRunner().invoke(main, ["shader", "10", "ps", "--reflect"])
    assert result.exit_code == 0
    assert "INPUTS" in result.output
    assert "v_pos" in result.output
    assert "OUTPUTS" in result.output
    assert "CBUFFERS" in result.output


def test_shader_with_constants(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "row": {
                "eid": 10,
                "stage": "ps",
                "shader": 101,
                "entry": "main_ps",
                "ro": 1,
                "rw": 0,
                "cbuffers": 1,
                "constants": {
                    "cbuffers": [
                        {
                            "name": "Globals",
                            "slot": 0,
                            "vars": [
                                {"name": "time", "type": "float", "value": "1.0"},
                            ],
                        },
                    ],
                },
            }
        },
    )
    result = CliRunner().invoke(main, ["shader", "10", "ps", "--constants"])
    assert result.exit_code == 0
    assert "CONSTANTS" in result.output
    assert "time" in result.output


def test_shaders_list(monkeypatch) -> None:
    patch_cli_session(
        monkeypatch,
        {
            "rows": [
                {"shader": 101, "stages": "ps", "uses": 5},
                {"shader": 202, "stages": "vs", "uses": 3},
            ]
        },
    )
    result = CliRunner().invoke(main, ["shaders"])
    assert result.exit_code == 0
    assert "101" in result.output
    assert "SHADER" in result.output


def test_shaders_json(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"rows": [{"shader": 101, "stages": "ps", "uses": 5}]})
    result = CliRunner().invoke(main, ["shaders", "--json"])
    assert result.exit_code == 0
    assert '"shader": 101' in result.output


def test_shaders_with_filters(monkeypatch) -> None:
    calls: list[dict] = []
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def capture(h, p, payload):
        calls.append(payload)
        return {"result": {"rows": []}}

    monkeypatch.setattr(mod, "send_request", capture)
    CliRunner().invoke(main, ["shaders", "--stage", "ps", "--sort", "uses"])
    assert calls[0]["params"]["stage"] == "ps"
    assert calls[0]["params"]["sort"] == "uses"


# ── bindings output options ────────────────────────────────────────

_BINDINGS_ROWS = {
    "rows": [
        {"eid": 10, "stage": "ps", "kind": "RO", "set": 0, "slot": 0, "name": "albedo"},
        {"eid": 10, "stage": "ps", "kind": "RW", "set": 0, "slot": 1, "name": "rwbuf"},
    ]
}


def test_bindings_default_has_header(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _BINDINGS_ROWS)
    result = CliRunner().invoke(main, ["bindings"])
    assert result.exit_code == 0
    assert "EID\tSTAGE\tKIND" in result.output


def test_bindings_no_header(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _BINDINGS_ROWS)
    result = CliRunner().invoke(main, ["bindings", "--no-header"])
    assert result.exit_code == 0
    assert "EID\tSTAGE\tKIND" not in result.output
    assert "albedo" in result.output


def test_bindings_jsonl(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _BINDINGS_ROWS)
    result = CliRunner().invoke(main, ["bindings", "--jsonl"])
    lines = assert_jsonl_output(result, 2)
    assert lines[0]["eid"] == 10


def test_bindings_quiet(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _BINDINGS_ROWS)
    result = CliRunner().invoke(main, ["bindings", "-q"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["10", "10"]


# ── shaders output options ─────────────────────────────────────────

_SHADERS_ROWS = {
    "rows": [
        {"shader": "abc123", "stages": "ps", "uses": 5},
        {"shader": "def456", "stages": "vs", "uses": 3},
    ]
}


def test_shaders_default_has_header(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _SHADERS_ROWS)
    result = CliRunner().invoke(main, ["shaders"])
    assert result.exit_code == 0
    assert "SHADER\tSTAGES\tUSES" in result.output


def test_shaders_no_header(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _SHADERS_ROWS)
    result = CliRunner().invoke(main, ["shaders", "--no-header"])
    assert result.exit_code == 0
    assert "SHADER\tSTAGES\tUSES" not in result.output
    assert "abc123" in result.output


def test_shaders_jsonl(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _SHADERS_ROWS)
    result = CliRunner().invoke(main, ["shaders", "--jsonl"])
    lines = assert_jsonl_output(result, 2)
    assert lines[0]["shader"] == "abc123"


def test_shaders_quiet(monkeypatch) -> None:
    patch_cli_session(monkeypatch, _SHADERS_ROWS)
    result = CliRunner().invoke(main, ["shaders", "-q"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["abc123", "def456"]
