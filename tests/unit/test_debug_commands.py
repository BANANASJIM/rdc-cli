"""Tests for rdc debug CLI commands."""

from __future__ import annotations

import json
from typing import Any

from click.testing import CliRunner

from rdc.cli import main
from rdc.commands import debug as debug_mod

_PIXEL_HAPPY_RESPONSE: dict[str, Any] = {
    "eid": 120,
    "stage": "ps",
    "total_steps": 3,
    "inputs": [
        {
            "name": "fragCoord",
            "type": "float",
            "rows": 1,
            "cols": 4,
            "before": [0.0, 0.0, 0.0, 0.0],
            "after": [512.5, 384.5, 0.95, 1.0],
        },
    ],
    "outputs": [
        {
            "name": "outColor",
            "type": "float",
            "rows": 1,
            "cols": 4,
            "before": [0.0, 0.0, 0.0, 0.0],
            "after": [0.55, 0.78, 0.92, 1.0],
        },
    ],
    "trace": [
        {
            "step": 0,
            "instruction": 0,
            "file": "main.frag",
            "line": 12,
            "changes": [
                {
                    "name": "fragCoord",
                    "type": "float",
                    "rows": 1,
                    "cols": 4,
                    "before": [0.0, 0.0, 0.0, 0.0],
                    "after": [512.5, 384.5, 0.95, 1.0],
                },
            ],
        },
        {
            "step": 1,
            "instruction": 5,
            "file": "main.frag",
            "line": 18,
            "changes": [
                {
                    "name": "uv",
                    "type": "float",
                    "rows": 1,
                    "cols": 2,
                    "before": [0.0, 0.0],
                    "after": [0.45, 0.72],
                },
            ],
        },
        {
            "step": 2,
            "instruction": 12,
            "file": "main.frag",
            "line": 25,
            "changes": [
                {
                    "name": "outColor",
                    "type": "float",
                    "rows": 1,
                    "cols": 4,
                    "before": [0.0, 0.0, 0.0, 0.0],
                    "after": [0.55, 0.78, 0.92, 1.0],
                },
            ],
        },
    ],
}

_VERTEX_HAPPY_RESPONSE: dict[str, Any] = {
    "eid": 120,
    "stage": "vs",
    "total_steps": 2,
    "inputs": [
        {
            "name": "inPosition",
            "type": "float",
            "rows": 1,
            "cols": 3,
            "before": [0.0, 0.0, 0.0],
            "after": [0.0, 0.5, 0.0],
        },
    ],
    "outputs": [
        {
            "name": "gl_Position",
            "type": "float",
            "rows": 1,
            "cols": 4,
            "before": [0.0, 0.0, 0.0, 0.0],
            "after": [0.0, 0.5, 0.0, 1.0],
        },
    ],
    "trace": [
        {
            "step": 0,
            "instruction": 0,
            "file": "main.vert",
            "line": 8,
            "changes": [
                {
                    "name": "inPosition",
                    "type": "float",
                    "rows": 1,
                    "cols": 3,
                    "before": [0.0, 0.0, 0.0],
                    "after": [0.0, 0.5, 0.0],
                },
            ],
        },
        {
            "step": 1,
            "instruction": 3,
            "file": "main.vert",
            "line": 12,
            "changes": [
                {
                    "name": "gl_Position",
                    "type": "float",
                    "rows": 1,
                    "cols": 4,
                    "before": [0.0, 0.0, 0.0, 0.0],
                    "after": [0.0, 0.5, 0.0, 1.0],
                },
            ],
        },
    ],
}

_EMPTY_TRACE_RESPONSE: dict[str, Any] = {
    "eid": 120,
    "stage": "ps",
    "total_steps": 0,
    "inputs": [],
    "outputs": [],
    "trace": [],
}

_MULTI_CHANGE_RESPONSE: dict[str, Any] = {
    "eid": 120,
    "stage": "ps",
    "total_steps": 1,
    "inputs": [],
    "outputs": [],
    "trace": [
        {
            "step": 0,
            "instruction": 0,
            "file": "main.frag",
            "line": 10,
            "changes": [
                {
                    "name": "a",
                    "type": "float",
                    "rows": 1,
                    "cols": 1,
                    "before": [0.0],
                    "after": [1.0],
                },
                {
                    "name": "b",
                    "type": "uint",
                    "rows": 1,
                    "cols": 1,
                    "before": [0],
                    "after": [42],
                },
            ],
        },
    ],
}

_captured_params: dict[str, Any] = {}


def _patch(monkeypatch: Any, response: dict[str, Any]) -> None:
    def fake_daemon_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        _captured_params.clear()
        _captured_params["method"] = method
        _captured_params["params"] = params
        return response

    monkeypatch.setattr(debug_mod, "_daemon_call", fake_daemon_call)


# ---------------------------------------------------------------------------
# debug pixel: default summary
# ---------------------------------------------------------------------------


def test_debug_pixel_default_summary(monkeypatch: Any) -> None:
    _patch(monkeypatch, _PIXEL_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "pixel", "120", "512", "384"])
    assert result.exit_code == 0
    assert "stage:" in result.output
    assert "ps" in result.output
    assert "steps:" in result.output
    assert "inputs:" in result.output
    assert "outputs:" in result.output


# ---------------------------------------------------------------------------
# debug pixel: --trace TSV
# ---------------------------------------------------------------------------


def test_debug_pixel_trace_tsv(monkeypatch: Any) -> None:
    _patch(monkeypatch, _PIXEL_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "pixel", "120", "512", "384", "--trace"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "STEP\tINSTR\tFILE\tLINE\tVAR\tTYPE\tVALUE"
    assert len(lines) == 4  # header + 3 steps (1 change each)
    assert "fragCoord" in lines[1]
    assert "uv" in lines[2]
    assert "outColor" in lines[3]


def test_debug_pixel_trace_empty(monkeypatch: Any) -> None:
    _patch(monkeypatch, _EMPTY_TRACE_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "pixel", "120", "512", "384", "--trace"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "STEP\tINSTR\tFILE\tLINE\tVAR\tTYPE\tVALUE"
    assert len(lines) == 1  # header only


# ---------------------------------------------------------------------------
# debug pixel: --dump-at
# ---------------------------------------------------------------------------


def test_debug_pixel_dump_at(monkeypatch: Any) -> None:
    _patch(monkeypatch, _PIXEL_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "pixel", "120", "512", "384", "--dump-at", "18"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "VAR\tTYPE\tVALUE"
    assert any("fragCoord" in line for line in lines)
    assert any("uv" in line for line in lines)


def test_debug_pixel_dump_at_no_match(monkeypatch: Any) -> None:
    _patch(monkeypatch, _PIXEL_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "pixel", "120", "512", "384", "--dump-at", "999"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    # All variables accumulated (LINE never reached, for-else path)
    assert lines[0] == "VAR\tTYPE\tVALUE"


# ---------------------------------------------------------------------------
# debug pixel: --json
# ---------------------------------------------------------------------------


def test_debug_pixel_json(monkeypatch: Any) -> None:
    _patch(monkeypatch, _PIXEL_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "pixel", "120", "512", "384", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["stage"] == "ps"
    assert data["total_steps"] == 3
    assert "trace" in data
    assert "inputs" in data
    assert "outputs" in data


# ---------------------------------------------------------------------------
# debug pixel: --no-header
# ---------------------------------------------------------------------------


def test_debug_pixel_no_header(monkeypatch: Any) -> None:
    _patch(monkeypatch, _PIXEL_HAPPY_RESPONSE)
    result = CliRunner().invoke(
        main, ["debug", "pixel", "120", "512", "384", "--trace", "--no-header"]
    )
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert not lines[0].startswith("STEP\tINSTR")


# ---------------------------------------------------------------------------
# debug pixel: multiple changes per step
# ---------------------------------------------------------------------------


def test_debug_pixel_multiple_changes(monkeypatch: Any) -> None:
    _patch(monkeypatch, _MULTI_CHANGE_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "pixel", "120", "512", "384", "--trace"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    # header + 2 rows (2 changes in 1 step)
    assert len(lines) == 3
    assert "a" in lines[1]
    assert "b" in lines[2]


# ---------------------------------------------------------------------------
# debug pixel: help
# ---------------------------------------------------------------------------


def test_debug_pixel_help() -> None:
    result = CliRunner().invoke(main, ["debug", "pixel", "--help"])
    assert result.exit_code == 0
    assert "EID" in result.output
    assert "--trace" in result.output


# ---------------------------------------------------------------------------
# debug vertex: default summary
# ---------------------------------------------------------------------------


def test_debug_vertex_default(monkeypatch: Any) -> None:
    _patch(monkeypatch, _VERTEX_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "vertex", "120", "0"])
    assert result.exit_code == 0
    assert "vs" in result.output
    assert "steps:" in result.output


# ---------------------------------------------------------------------------
# debug vertex: --trace
# ---------------------------------------------------------------------------


def test_debug_vertex_trace(monkeypatch: Any) -> None:
    _patch(monkeypatch, _VERTEX_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "vertex", "120", "0", "--trace"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "STEP\tINSTR\tFILE\tLINE\tVAR\tTYPE\tVALUE"
    assert len(lines) == 3  # header + 2 steps


# ---------------------------------------------------------------------------
# debug vertex: --instance forwarded
# ---------------------------------------------------------------------------


def test_debug_vertex_instance_forwarded(monkeypatch: Any) -> None:
    _patch(monkeypatch, _VERTEX_HAPPY_RESPONSE)
    CliRunner().invoke(main, ["debug", "vertex", "120", "0", "--instance", "5"])
    assert _captured_params["params"]["instance"] == 5


# ---------------------------------------------------------------------------
# debug vertex: --json
# ---------------------------------------------------------------------------


def test_debug_vertex_json(monkeypatch: Any) -> None:
    _patch(monkeypatch, _VERTEX_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "vertex", "120", "0", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["stage"] == "vs"
    assert data["total_steps"] == 2


# ---------------------------------------------------------------------------
# debug vertex: help
# ---------------------------------------------------------------------------


def test_debug_vertex_help() -> None:
    result = CliRunner().invoke(main, ["debug", "vertex", "--help"])
    assert result.exit_code == 0
    assert "VTX_ID" in result.output
    assert "--instance" in result.output


# ---------------------------------------------------------------------------
# debug group
# ---------------------------------------------------------------------------


def test_debug_group_help() -> None:
    result = CliRunner().invoke(main, ["debug", "--help"])
    assert result.exit_code == 0
    assert "pixel" in result.output
    assert "vertex" in result.output


def test_debug_no_subcommand() -> None:
    result = CliRunner().invoke(main, ["debug"])
    assert result.exit_code in (0, 2)
    assert "pixel" in result.output or "Usage" in result.output


def test_debug_in_main_help() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert "debug" in result.output


# ---------------------------------------------------------------------------
# debug thread: fixture data
# ---------------------------------------------------------------------------

_THREAD_HAPPY_RESPONSE: dict[str, Any] = {
    "eid": 150,
    "stage": "cs",
    "total_steps": 3,
    "inputs": [
        {
            "name": "gl_GlobalInvocationID",
            "type": "uint",
            "rows": 1,
            "cols": 3,
            "before": [0, 0, 0],
            "after": [0, 0, 0],
        },
    ],
    "outputs": [
        {
            "name": "outBuffer",
            "type": "float",
            "rows": 1,
            "cols": 4,
            "before": [0.0, 0.0, 0.0, 0.0],
            "after": [1.0, 2.0, 3.0, 4.0],
        },
    ],
    "trace": [
        {
            "step": 0,
            "instruction": 0,
            "file": "shader.comp",
            "line": 12,
            "changes": [
                {
                    "name": "gl_GlobalInvocationID",
                    "type": "uint",
                    "rows": 1,
                    "cols": 3,
                    "before": [0, 0, 0],
                    "after": [0, 0, 0],
                },
            ],
        },
        {
            "step": 1,
            "instruction": 1,
            "file": "shader.comp",
            "line": 13,
            "changes": [
                {
                    "name": "temp",
                    "type": "float",
                    "rows": 1,
                    "cols": 1,
                    "before": [0.0],
                    "after": [0.5],
                },
            ],
        },
        {
            "step": 2,
            "instruction": 5,
            "file": "shader.comp",
            "line": 20,
            "changes": [
                {
                    "name": "outBuffer",
                    "type": "float",
                    "rows": 1,
                    "cols": 4,
                    "before": [0.0, 0.0, 0.0, 0.0],
                    "after": [1.0, 2.0, 3.0, 4.0],
                },
            ],
        },
    ],
}

_THREAD_EMPTY_TRACE: dict[str, Any] = {
    "eid": 150,
    "stage": "cs",
    "total_steps": 0,
    "inputs": [],
    "outputs": [],
    "trace": [],
}

_THREAD_MULTI_CHANGE: dict[str, Any] = {
    "eid": 150,
    "stage": "cs",
    "total_steps": 1,
    "inputs": [],
    "outputs": [],
    "trace": [
        {
            "step": 0,
            "instruction": 0,
            "file": "shader.comp",
            "line": 10,
            "changes": [
                {
                    "name": "a",
                    "type": "float",
                    "rows": 1,
                    "cols": 1,
                    "before": [0.0],
                    "after": [1.0],
                },
                {
                    "name": "b",
                    "type": "uint",
                    "rows": 1,
                    "cols": 1,
                    "before": [0],
                    "after": [42],
                },
            ],
        },
    ],
}

_THREAD_ARGS = ["debug", "thread", "150", "0", "0", "0", "0", "0", "0"]


# ---------------------------------------------------------------------------
# debug thread: default summary (DT-01)
# ---------------------------------------------------------------------------


def test_debug_thread_default_summary(monkeypatch: Any) -> None:
    _patch(monkeypatch, _THREAD_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, _THREAD_ARGS)
    assert result.exit_code == 0
    assert "stage:" in result.output
    assert "cs" in result.output
    assert "steps:" in result.output
    assert "inputs:" in result.output
    assert "outputs:" in result.output


# ---------------------------------------------------------------------------
# debug thread: --trace TSV (DT-02)
# ---------------------------------------------------------------------------


def test_debug_thread_trace_tsv(monkeypatch: Any) -> None:
    _patch(monkeypatch, _THREAD_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, [*_THREAD_ARGS, "--trace"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "STEP\tINSTR\tFILE\tLINE\tVAR\tTYPE\tVALUE"
    assert len(lines) == 4  # header + 3 steps (1 change each)
    assert "gl_GlobalInvocationID" in lines[1]
    assert "temp" in lines[2]
    assert "outBuffer" in lines[3]


# ---------------------------------------------------------------------------
# debug thread: --trace empty (DT-03)
# ---------------------------------------------------------------------------


def test_debug_thread_trace_empty(monkeypatch: Any) -> None:
    _patch(monkeypatch, _THREAD_EMPTY_TRACE)
    result = CliRunner().invoke(main, [*_THREAD_ARGS, "--trace"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "STEP\tINSTR\tFILE\tLINE\tVAR\tTYPE\tVALUE"
    assert len(lines) == 1


# ---------------------------------------------------------------------------
# debug thread: --dump-at (DT-04)
# ---------------------------------------------------------------------------


def test_debug_thread_dump_at(monkeypatch: Any) -> None:
    _patch(monkeypatch, _THREAD_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, [*_THREAD_ARGS, "--dump-at", "13"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "VAR\tTYPE\tVALUE"
    assert any("gl_GlobalInvocationID" in line for line in lines)
    assert any("temp" in line for line in lines)


# ---------------------------------------------------------------------------
# debug thread: --dump-at no match (DT-05)
# ---------------------------------------------------------------------------


def test_debug_thread_dump_at_no_match(monkeypatch: Any) -> None:
    _patch(monkeypatch, _THREAD_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, [*_THREAD_ARGS, "--dump-at", "9999"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "VAR\tTYPE\tVALUE"
    # all vars accumulated
    assert any("gl_GlobalInvocationID" in line for line in lines)


# ---------------------------------------------------------------------------
# debug thread: --json (DT-06)
# ---------------------------------------------------------------------------


def test_debug_thread_json(monkeypatch: Any) -> None:
    _patch(monkeypatch, _THREAD_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, [*_THREAD_ARGS, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["stage"] == "cs"
    assert data["total_steps"] == 3
    assert "trace" in data
    assert "inputs" in data
    assert "outputs" in data


# ---------------------------------------------------------------------------
# debug thread: --no-header (DT-07)
# ---------------------------------------------------------------------------


def test_debug_thread_no_header(monkeypatch: Any) -> None:
    _patch(monkeypatch, _THREAD_HAPPY_RESPONSE)
    result = CliRunner().invoke(main, [*_THREAD_ARGS, "--trace", "--no-header"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert not lines[0].startswith("STEP\tINSTR")


# ---------------------------------------------------------------------------
# debug thread: params forwarded (DT-08)
# ---------------------------------------------------------------------------


def test_debug_thread_params_forwarded(monkeypatch: Any) -> None:
    _patch(monkeypatch, _THREAD_HAPPY_RESPONSE)
    CliRunner().invoke(main, ["debug", "thread", "150", "1", "2", "0", "3", "4", "5"])
    p = _captured_params["params"]
    assert p["eid"] == 150
    assert p["gx"] == 1
    assert p["gy"] == 2
    assert p["gz"] == 0
    assert p["tx"] == 3
    assert p["ty"] == 4
    assert p["tz"] == 5


# ---------------------------------------------------------------------------
# debug thread: method name (DT-09)
# ---------------------------------------------------------------------------


def test_debug_thread_method_name(monkeypatch: Any) -> None:
    _patch(monkeypatch, _THREAD_HAPPY_RESPONSE)
    CliRunner().invoke(main, _THREAD_ARGS)
    assert _captured_params["method"] == "debug_thread"


# ---------------------------------------------------------------------------
# debug thread: help (DT-10)
# ---------------------------------------------------------------------------


def test_debug_thread_help() -> None:
    result = CliRunner().invoke(main, ["debug", "thread", "--help"])
    assert result.exit_code == 0
    assert "EID" in result.output
    assert "GX" in result.output
    assert "GY" in result.output
    assert "GZ" in result.output
    assert "TX" in result.output
    assert "TY" in result.output
    assert "TZ" in result.output
    assert "--trace" in result.output


# ---------------------------------------------------------------------------
# debug thread: missing arg exits nonzero (DT-11)
# ---------------------------------------------------------------------------


def test_debug_thread_missing_arg_exits_nonzero() -> None:
    result = CliRunner().invoke(main, ["debug", "thread", "150", "0", "0"])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# debug thread: multiple changes (DT-12)
# ---------------------------------------------------------------------------


def test_debug_thread_multiple_changes(monkeypatch: Any) -> None:
    _patch(monkeypatch, _THREAD_MULTI_CHANGE)
    result = CliRunner().invoke(main, [*_THREAD_ARGS, "--trace"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert len(lines) == 3  # header + 2 changes
    assert "a" in lines[1]
    assert "b" in lines[2]


# ---------------------------------------------------------------------------
# debug thread: group help includes thread (DT-13)
# ---------------------------------------------------------------------------


def test_debug_group_help_includes_thread() -> None:
    result = CliRunner().invoke(main, ["debug", "--help"])
    assert result.exit_code == 0
    assert "thread" in result.output


# ---------------------------------------------------------------------------
# debug pixel: error handling (rc=1 on daemon error)
# ---------------------------------------------------------------------------

_ERROR_RESPONSE: dict[str, Any] = {
    "error": {"message": "no shader bound", "code": -32603},
}


def _patch_helpers(monkeypatch: Any, response: dict[str, Any]) -> None:
    """Patch load_session and send_request on _helpers for full call() path."""
    import rdc.commands._helpers as helpers_mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(helpers_mod, "load_session", lambda: session)
    monkeypatch.setattr(helpers_mod, "send_request", lambda _h, _p, _payload: response)


def test_debug_pixel_error_plain_rc1(monkeypatch: Any) -> None:
    """Daemon error in plain mode exits with rc=1."""
    _patch_helpers(monkeypatch, _ERROR_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "pixel", "100", "320", "240"])
    assert result.exit_code == 1


def test_debug_pixel_error_json_rc1(monkeypatch: Any) -> None:
    """Daemon error in --json mode exits with rc=1."""
    _patch_helpers(monkeypatch, _ERROR_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "pixel", "100", "320", "240", "--json"])
    assert result.exit_code == 1


def test_debug_pixel_error_trace_rc1(monkeypatch: Any) -> None:
    """Daemon error in --trace mode exits with rc=1."""
    _patch_helpers(monkeypatch, _ERROR_RESPONSE)
    result = CliRunner().invoke(main, ["debug", "pixel", "100", "320", "240", "--trace"])
    assert result.exit_code == 1


def test_debug_pixel_success_plain_rc0(monkeypatch: Any) -> None:
    """Successful daemon response exits with rc=0 (regression)."""
    _patch_helpers(monkeypatch, {"result": _PIXEL_HAPPY_RESPONSE})
    result = CliRunner().invoke(main, ["debug", "pixel", "120", "512", "384"])
    assert result.exit_code == 0
