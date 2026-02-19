"""Tests for rdc pipeline/shader/bindings/shaders CLI commands - extended coverage."""

from __future__ import annotations

from click.testing import CliRunner

from rdc.cli import main


def _patch_pipeline(monkeypatch, response):
    import rdc.commands.pipeline as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})


def test_pipeline_tsv(monkeypatch) -> None:
    _patch_pipeline(
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
    _patch_pipeline(
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
    _patch_pipeline(
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
    _patch_pipeline(
        monkeypatch,
        {"rows": [{"eid": 10, "stage": "ps", "kind": "RO", "slot": 0, "name": "albedo"}]},
    )
    result = CliRunner().invoke(main, ["bindings", "--json"])
    assert result.exit_code == 0
    assert '"name": "albedo"' in result.output


def test_bindings_with_filters(monkeypatch) -> None:
    calls: list[dict] = []
    import rdc.commands.pipeline as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def capture(h, p, payload):
        calls.append(payload)
        return {"result": {"rows": []}}

    monkeypatch.setattr(mod, "send_request", capture)
    CliRunner().invoke(main, ["bindings", "10", "--binding", "0"])
    assert calls[0]["params"]["binding"] == 0


def test_shader_targets(monkeypatch) -> None:
    _patch_pipeline(monkeypatch, {"targets": ["SPIR-V", "GLSL"]})
    result = CliRunner().invoke(main, ["shader", "--targets"])
    assert result.exit_code == 0
    assert "SPIR-V" in result.output


def test_shader_targets_json(monkeypatch) -> None:
    _patch_pipeline(monkeypatch, {"targets": ["SPIR-V", "GLSL"]})
    result = CliRunner().invoke(main, ["shader", "--targets", "--json"])
    assert result.exit_code == 0
    assert "SPIR-V" in result.output


def test_shader_all(monkeypatch) -> None:
    _patch_pipeline(
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
    _patch_pipeline(
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
    _patch_pipeline(
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
    _patch_pipeline(
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


def test_shader_with_source_output(monkeypatch, tmp_path) -> None:
    _patch_pipeline(
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
    _patch_pipeline(
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
    _patch_pipeline(
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
    _patch_pipeline(
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
    _patch_pipeline(monkeypatch, {"rows": [{"shader": 101, "stages": "ps", "uses": 5}]})
    result = CliRunner().invoke(main, ["shaders", "--json"])
    assert result.exit_code == 0
    assert '"shader": 101' in result.output


def test_shaders_with_filters(monkeypatch) -> None:
    calls: list[dict] = []
    import rdc.commands.pipeline as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def capture(h, p, payload):
        calls.append(payload)
        return {"result": {"rows": []}}

    monkeypatch.setattr(mod, "send_request", capture)
    CliRunner().invoke(main, ["shaders", "--stage", "ps", "--sort", "uses"])
    assert calls[0]["params"]["stage"] == "ps"
    assert calls[0]["params"]["sort"] == "uses"
