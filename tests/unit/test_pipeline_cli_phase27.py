"""CLI tests for phase2.7: pipeline section routing, shader --target, bindings --set."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from rdc.cli import main


def _setup(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]) -> None:
    import rdc.commands.pipeline as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})


def _capture_calls(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]) -> list[dict]:
    calls: list[dict] = []
    import rdc.commands.pipeline as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def capture(_h: str, _p: int, payload: dict) -> dict:
        calls.append(payload)
        return {"result": response}

    monkeypatch.setattr(mod, "send_request", capture)
    return calls


# ── A: Non-shader sections via pipeline_cmd ───────────────────────────────────


@pytest.mark.parametrize(
    "section,result_key,result_val",
    [
        ("topology", "topology", "TriangleList"),
        ("viewport", "x", 0.0),
        ("blend", "blends", []),
        ("rasterizer", "eid", 1),
        ("depth-stencil", "eid", 1),
        ("msaa", "eid", 1),
        ("scissor", "eid", 1),
        ("stencil", "eid", 1),
        ("vbuffers", "vbuffers", []),
        ("ibuffer", "eid", 1),
        ("samplers", "samplers", []),
        ("push-constants", "push_constants", []),
        ("vinputs", "inputs", []),
    ],
)
def test_pipeline_non_shader_section(
    monkeypatch: pytest.MonkeyPatch, section: str, result_key: str, result_val: Any
) -> None:
    """Non-shader section returns exit 0 with non-empty output."""
    section_data: dict[str, Any] = {"eid": 1, result_key: result_val}
    if section == "topology":
        section_data["topology"] = "TriangleList"
    elif section == "viewport":
        section_data.update({"x": 0.0, "y": 0.0, "width": 800.0, "height": 600.0})

    _setup(monkeypatch, section_data)
    result = CliRunner().invoke(main, ["pipeline", "1", section])
    assert result.exit_code == 0
    assert result.output.strip() != ""


def test_pipeline_non_shader_section_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-shader section with --json outputs valid JSON."""
    import json

    _setup(monkeypatch, {"eid": 1, "x": 0.0, "y": 0.0, "width": 800.0, "height": 600.0})
    result = CliRunner().invoke(main, ["pipeline", "1", "viewport", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, dict)


def test_pipeline_shader_stage_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing shader-stage section behavior is unchanged."""
    _setup(
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


def test_pipeline_non_shader_key_value_tsv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-shader section in TSV mode outputs KEY/VALUE table."""
    _setup(monkeypatch, {"eid": 1, "topology": "TriangleList"})
    result = CliRunner().invoke(main, ["pipeline", "1", "topology"])
    assert result.exit_code == 0
    assert "KEY" in result.output
    assert "VALUE" in result.output
    assert "topology" in result.output
    assert "TriangleList" in result.output


# ── B: Shader --target dispatch ───────────────────────────────────────────────


def test_shader_target_dispatches_to_shader_disasm(monkeypatch: pytest.MonkeyPatch) -> None:
    """--target dispatches to shader_disasm, not shader."""
    calls = _capture_calls(
        monkeypatch,
        {"eid": 1, "stage": "ps", "target": "SPIR-V (RenderDoc)", "disasm": "Capability(Shader);"},
    )
    result = CliRunner().invoke(main, ["shader", "1", "ps", "--target", "SPIR-V (RenderDoc)"])
    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0]["method"] == "shader_disasm"
    assert "Capability" in result.output


def test_shader_target_writes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--target + -o writes disassembly to file."""
    _capture_calls(
        monkeypatch,
        {"eid": 1, "stage": "ps", "target": "SPIR-V", "disasm": "disasm text"},
    )
    out = tmp_path / "out.spv"
    result = CliRunner().invoke(main, ["shader", "1", "ps", "--target", "SPIR-V", "-o", str(out)])
    assert result.exit_code == 0
    assert out.read_text() == "disasm text"
    assert "Written to" in result.output


def test_shader_without_target_uses_shader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without --target, shader_cmd calls 'shader' method."""
    calls = _capture_calls(
        monkeypatch,
        {
            "row": {
                "eid": 1,
                "stage": "ps",
                "shader": 101,
                "entry": "main",
                "ro": 0,
                "rw": 0,
                "cbuffers": 0,
            }
        },
    )
    CliRunner().invoke(main, ["shader", "1", "ps"])
    assert calls[0]["method"] == "shader"


def test_shader_targets_flag_dispatches_to_shader_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--targets flag calls shader_targets (unchanged)."""
    calls = _capture_calls(monkeypatch, {"targets": ["SPIR-V", "GLSL"]})
    result = CliRunner().invoke(main, ["shader", "1", "ps", "--targets"])
    assert result.exit_code == 0
    assert calls[0]["method"] == "shader_targets"


def test_shader_target_no_stage_defaults_to_ps(monkeypatch: pytest.MonkeyPatch) -> None:
    """--target without stage defaults to ps, eid defaults to 0."""
    calls = _capture_calls(
        monkeypatch,
        {"eid": 0, "stage": "ps", "target": "GLSL", "disasm": "glsl code"},
    )
    CliRunner().invoke(main, ["shader", "--target", "GLSL"])
    assert calls[0]["method"] == "shader_disasm"
    assert calls[0]["params"]["stage"] == "ps"
    assert calls[0]["params"]["eid"] == 0


# ── C: Bindings --set ─────────────────────────────────────────────────────────


def test_bindings_set_filter_sends_param(monkeypatch: pytest.MonkeyPatch) -> None:
    """--set passes set param to daemon."""
    calls = _capture_calls(monkeypatch, {"rows": []})
    CliRunner().invoke(main, ["bindings", "1", "--set", "1"])
    assert calls[0]["params"]["set"] == 1


def test_bindings_set_and_binding_combined(monkeypatch: pytest.MonkeyPatch) -> None:
    """--set and --binding both sent to daemon."""
    calls = _capture_calls(monkeypatch, {"rows": []})
    CliRunner().invoke(main, ["bindings", "1", "--set", "0", "--binding", "2"])
    assert calls[0]["params"]["set"] == 0
    assert calls[0]["params"]["binding"] == 2


def test_bindings_tsv_has_set_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """TSV output includes SET column header."""
    _setup(
        monkeypatch,
        {"rows": [{"eid": 1, "stage": "ps", "kind": "ro", "set": 0, "slot": 2, "name": "tex"}]},
    )
    result = CliRunner().invoke(main, ["bindings", "1"])
    assert result.exit_code == 0
    assert "SET" in result.output


def test_bindings_tsv_set_value_in_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """TSV data rows include set value in correct position (before SLOT)."""
    _setup(
        monkeypatch,
        {"rows": [{"eid": 1, "stage": "ps", "kind": "ro", "set": 7, "slot": 3, "name": "albedo"}]},
    )
    result = CliRunner().invoke(main, ["bindings", "1"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert len(lines) >= 2
    header = lines[0]
    data = lines[1]
    set_col_idx = header.split("\t").index("SET")
    slot_col_idx = header.split("\t").index("SLOT")
    assert set_col_idx < slot_col_idx
    assert data.split("\t")[set_col_idx] == "7"


def test_bindings_binding_filter_no_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """--binding without --set sends no 'set' key in params."""
    calls = _capture_calls(monkeypatch, {"rows": []})
    CliRunner().invoke(main, ["bindings", "1", "--binding", "3"])
    assert calls[0]["params"]["binding"] == 3
    assert "set" not in calls[0]["params"]


def test_bindings_header_is_eid_stage_kind_set_slot_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TSV header is exactly EID STAGE KIND SET SLOT NAME."""
    _setup(monkeypatch, {"rows": []})
    result = CliRunner().invoke(main, ["bindings"])
    assert result.exit_code == 0
    header_line = result.output.strip().splitlines()[0]
    assert header_line == "EID\tSTAGE\tKIND\tSET\tSLOT\tNAME"
