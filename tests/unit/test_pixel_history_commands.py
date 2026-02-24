"""Tests for rdc pixel CLI command."""

from __future__ import annotations

from typing import Any

from click.testing import CliRunner
from conftest import assert_json_output, assert_jsonl_output

from rdc.cli import main
from rdc.commands import pixel as pixel_mod

_HAPPY_RESPONSE = {
    "x": 512,
    "y": 384,
    "eid": 120,
    "target": {"index": 0, "id": 42},
    "modifications": [
        {
            "eid": 88,
            "fragment": 0,
            "primitive": 0,
            "shader_out": {"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0},
            "post_mod": {"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0},
            "depth": 0.95,
            "passed": True,
            "flags": [],
        },
        {
            "eid": 102,
            "fragment": 0,
            "primitive": 1,
            "shader_out": {"r": 0.2, "g": 0.4, "b": 0.6, "a": 1.0},
            "post_mod": {"r": 0.2, "g": 0.4, "b": 0.6, "a": 1.0},
            "depth": 0.82,
            "passed": False,
            "flags": ["depthTestFailed"],
        },
    ],
}

_EMPTY_RESPONSE = {
    "x": 512,
    "y": 384,
    "eid": 120,
    "target": {"index": 0, "id": 42},
    "modifications": [],
}

_NULL_DEPTH_RESPONSE = {
    "x": 0,
    "y": 0,
    "eid": 120,
    "target": {"index": 0, "id": 42},
    "modifications": [
        {
            "eid": 88,
            "fragment": 0,
            "primitive": 0,
            "shader_out": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0},
            "post_mod": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0},
            "depth": None,
            "passed": True,
            "flags": [],
        },
    ],
}

_captured_params: dict[str, Any] = {}


def _patch(monkeypatch: Any, response: dict) -> None:
    def fake_daemon_call(method: str, params: dict | None = None) -> dict:
        _captured_params.clear()
        _captured_params["method"] = method
        _captured_params["params"] = params
        return response

    monkeypatch.setattr(pixel_mod, "call", fake_daemon_call)


# ---------------------------------------------------------------------------
# TSV output
# ---------------------------------------------------------------------------


def test_tsv_output(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["pixel", "512", "384"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "EID\tFRAG\tDEPTH\tPASSED\tFLAGS"
    assert lines[1] == "88\t0\t0.9500\tyes\t-"
    assert lines[2] == "102\t0\t0.8200\tno\tdepthTestFailed"


def test_tsv_no_modifications(monkeypatch: Any) -> None:
    _patch(monkeypatch, _EMPTY_RESPONSE)
    result = CliRunner().invoke(main, ["pixel", "512", "384"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert len(lines) == 1
    assert lines[0] == "EID\tFRAG\tDEPTH\tPASSED\tFLAGS"


def test_null_depth_shows_dash(monkeypatch: Any) -> None:
    _patch(monkeypatch, _NULL_DEPTH_RESPONSE)
    result = CliRunner().invoke(main, ["pixel", "0", "0"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert "88\t0\t-\tyes\t-" in lines[1]


# ---------------------------------------------------------------------------
# EID and options forwarded
# ---------------------------------------------------------------------------


def test_eid_forwarded(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    CliRunner().invoke(main, ["pixel", "512", "384", "120"])
    assert _captured_params["params"]["eid"] == 120


def test_target_forwarded(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    CliRunner().invoke(main, ["pixel", "512", "384", "--target", "1"])
    assert _captured_params["params"]["target"] == 1


def test_sample_forwarded(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    CliRunner().invoke(main, ["pixel", "512", "384", "--sample", "2"])
    assert _captured_params["params"]["sample"] == 2


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def test_json_output(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["pixel", "512", "384", "--json"])
    data = assert_json_output(result)
    assert data["x"] == 512
    assert "modifications" in data


# ---------------------------------------------------------------------------
# --no-header
# ---------------------------------------------------------------------------


def test_no_header(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["pixel", "512", "384", "--no-header"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert not lines[0].startswith("EID\tFRAG")


def test_no_header_empty(monkeypatch: Any) -> None:
    _patch(monkeypatch, _EMPTY_RESPONSE)
    result = CliRunner().invoke(main, ["pixel", "512", "384", "--no-header"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_missing_session(monkeypatch: Any) -> None:
    monkeypatch.setattr("rdc.commands._helpers.load_session", lambda: None)
    result = CliRunner().invoke(main, ["pixel", "512", "384"])
    assert result.exit_code == 1


def test_daemon_error(monkeypatch: Any) -> None:
    def fake_call(method: str, params: dict | None = None) -> dict:
        import click

        click.echo("error: no color targets at eid 120", err=True)
        raise SystemExit(1)

    monkeypatch.setattr(pixel_mod, "call", fake_call)
    result = CliRunner().invoke(main, ["pixel", "512", "384"])
    assert result.exit_code == 1


def test_non_integer_x() -> None:
    result = CliRunner().invoke(main, ["pixel", "abc", "384"])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# CLI registration
# ---------------------------------------------------------------------------


def test_help_shows_pixel() -> None:
    assert "pixel" in CliRunner().invoke(main, ["--help"]).output


# ── pixel output options ───────────────────────────────────────────


def test_pixel_default_has_header(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["pixel", "512", "384"])
    assert result.exit_code == 0
    assert "EID\tFRAG\tDEPTH\tPASSED\tFLAGS" in result.output


def test_pixel_no_header_regression(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["pixel", "512", "384", "--no-header"])
    assert result.exit_code == 0
    assert "EID\tFRAG\tDEPTH\tPASSED\tFLAGS" not in result.output
    assert "88" in result.output


def test_pixel_jsonl(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["pixel", "512", "384", "--jsonl"])
    lines = assert_jsonl_output(result, 2)
    assert lines[0]["eid"] == 88


def test_pixel_quiet(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["pixel", "512", "384", "-q"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines == ["88", "102"]
