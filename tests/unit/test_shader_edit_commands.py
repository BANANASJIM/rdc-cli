"""Tests for rdc shader edit-replay CLI commands."""

from __future__ import annotations

from typing import Any

from click.testing import CliRunner
from conftest import assert_json_output

from rdc.cli import main
from rdc.commands import shader_edit as shader_edit_mod

_ENCODINGS_RESPONSE: dict[str, Any] = {
    "encodings": [{"value": 2, "name": "GLSL"}, {"value": 3, "name": "SPIRV"}]
}

_BUILD_RESPONSE: dict[str, Any] = {"shader_id": 42, "warnings": ""}

_REPLACE_RESPONSE: dict[str, Any] = {"ok": True, "original_id": 500}

_RESTORE_RESPONSE: dict[str, Any] = {"ok": True}

_RESTORE_ALL_RESPONSE: dict[str, Any] = {"ok": True, "restored": 1, "freed": 2}

_captured_params: dict[str, Any] = {}


def _patch(monkeypatch: Any, response: dict[str, Any]) -> None:
    def fake_daemon_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        _captured_params.clear()
        _captured_params["method"] = method
        _captured_params["params"] = params
        return response

    monkeypatch.setattr(shader_edit_mod, "_daemon_call", fake_daemon_call)


# ---------------------------------------------------------------------------
# shader-encodings
# ---------------------------------------------------------------------------


def test_shader_encodings_default(monkeypatch: Any) -> None:
    _patch(monkeypatch, _ENCODINGS_RESPONSE)
    result = CliRunner().invoke(main, ["shader-encodings"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines == ["GLSL", "SPIRV"]


def test_shader_encodings_json(monkeypatch: Any) -> None:
    _patch(monkeypatch, _ENCODINGS_RESPONSE)
    result = CliRunner().invoke(main, ["shader-encodings", "--json"])
    data = assert_json_output(result)
    assert len(data["encodings"]) == 2
    assert data["encodings"][0]["name"] == "GLSL"


def test_shader_encodings_help() -> None:
    result = CliRunner().invoke(main, ["shader-encodings", "--help"])
    assert result.exit_code == 0
    assert "--json" in result.output


# ---------------------------------------------------------------------------
# shader-build
# ---------------------------------------------------------------------------


def test_shader_build_happy(monkeypatch: Any, tmp_path: Any) -> None:
    _patch(monkeypatch, _BUILD_RESPONSE)
    src = tmp_path / "test.frag"
    src.write_text("#version 450\nvoid main(){}\n")
    result = CliRunner().invoke(main, ["shader-build", str(src), "--stage", "ps"])
    assert result.exit_code == 0
    assert "42" in result.output
    assert "shader_id" in result.output


def test_shader_build_quiet(monkeypatch: Any, tmp_path: Any) -> None:
    _patch(monkeypatch, _BUILD_RESPONSE)
    src = tmp_path / "test.frag"
    src.write_text("#version 450\nvoid main(){}\n")
    result = CliRunner().invoke(main, ["shader-build", str(src), "--stage", "ps", "-q"])
    assert result.exit_code == 0
    assert result.output.strip() == "42"


def test_shader_build_json(monkeypatch: Any, tmp_path: Any) -> None:
    _patch(monkeypatch, _BUILD_RESPONSE)
    src = tmp_path / "test.frag"
    src.write_text("#version 450\nvoid main(){}\n")
    result = CliRunner().invoke(main, ["shader-build", str(src), "--stage", "ps", "--json"])
    data = assert_json_output(result)
    assert data["shader_id"] == 42


def test_shader_build_file_not_found() -> None:
    result = CliRunner().invoke(main, ["shader-build", "/no/such/file.frag", "--stage", "ps"])
    assert result.exit_code == 2


def test_shader_build_help() -> None:
    result = CliRunner().invoke(main, ["shader-build", "--help"])
    assert result.exit_code == 0
    assert "--stage" in result.output
    assert "--entry" in result.output


# ---------------------------------------------------------------------------
# shader-replace
# ---------------------------------------------------------------------------


def test_shader_replace_happy(monkeypatch: Any) -> None:
    _patch(monkeypatch, _REPLACE_RESPONSE)
    result = CliRunner().invoke(main, ["shader-replace", "120", "ps", "--with", "42"])
    assert result.exit_code == 0
    assert "replaced" in result.output
    assert "500" in result.output


def test_shader_replace_help() -> None:
    result = CliRunner().invoke(main, ["shader-replace", "--help"])
    assert result.exit_code == 0
    assert "--with" in result.output
    assert "EID" in result.output


# ---------------------------------------------------------------------------
# shader-restore
# ---------------------------------------------------------------------------


def test_shader_restore_happy(monkeypatch: Any) -> None:
    _patch(monkeypatch, _RESTORE_RESPONSE)
    result = CliRunner().invoke(main, ["shader-restore", "120", "ps"])
    assert result.exit_code == 0
    assert "restored" in result.output
    assert "ps" in result.output


def test_shader_restore_help() -> None:
    result = CliRunner().invoke(main, ["shader-restore", "--help"])
    assert result.exit_code == 0
    assert "EID" in result.output
    assert "STAGE" in result.output


# ---------------------------------------------------------------------------
# shader-restore-all
# ---------------------------------------------------------------------------


def test_shader_restore_all_happy(monkeypatch: Any) -> None:
    _patch(monkeypatch, _RESTORE_ALL_RESPONSE)
    result = CliRunner().invoke(main, ["shader-restore-all"])
    assert result.exit_code == 0
    assert "restored\t1" in result.output
    assert "freed\t2" in result.output


def test_shader_restore_all_help() -> None:
    result = CliRunner().invoke(main, ["shader-restore-all", "--help"])
    assert result.exit_code == 0
    assert "--json" in result.output


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_shader_commands_in_main_help() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    cmds = [
        "shader-encodings",
        "shader-build",
        "shader-replace",
        "shader-restore",
        "shader-restore-all",
    ]
    for cmd in cmds:
        assert cmd in result.output, f"{cmd} not in main --help"


# ---------------------------------------------------------------------------
# Params forwarding
# ---------------------------------------------------------------------------


def test_shader_build_params_forwarded(monkeypatch: Any, tmp_path: Any) -> None:
    _patch(monkeypatch, _BUILD_RESPONSE)
    src = tmp_path / "test.frag"
    src.write_text("#version 450\nvoid main(){}\n")
    CliRunner().invoke(
        main,
        ["shader-build", str(src), "--stage", "ps", "--entry", "myMain", "--encoding", "SPIRV"],
    )
    params = _captured_params["params"]
    assert params["stage"] == "ps"
    assert params["entry"] == "myMain"
    assert params["encoding"] == "SPIRV"
    assert "#version 450" in params["source"]
