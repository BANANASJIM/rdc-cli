"""Tests for CI assertion commands."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from rdc.cli import main
from rdc.commands import assert_ci as mod

# ---------------------------------------------------------------------------
# _assert_call helper tests
# ---------------------------------------------------------------------------

_ERR_RESP: dict[str, Any] = {
    "error": {"message": "no capture loaded"},
}


def test_assert_call_no_session(monkeypatch: Any) -> None:
    monkeypatch.setattr(mod, "load_session", lambda: None)
    with pytest.raises(SystemExit, match="2"):
        mod._assert_call("count")


def test_assert_call_rpc_error(monkeypatch: Any) -> None:
    session = MagicMock(host="localhost", port=9876, token="tok")
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod,
        "send_request",
        lambda *a, **kw: _ERR_RESP,
    )
    with pytest.raises(SystemExit, match="2"):
        mod._assert_call("count")


def test_assert_call_unexpected_exception_propagates(monkeypatch: Any) -> None:
    """Unexpected exceptions (e.g. AttributeError) must not be caught by _assert_call."""
    session = MagicMock(host="localhost", port=9876, token="tok")
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod,
        "send_request",
        MagicMock(side_effect=AttributeError("unexpected")),
    )
    with pytest.raises(AttributeError, match="unexpected"):
        mod._assert_call("count")


def test_assert_call_success(monkeypatch: Any) -> None:
    session = MagicMock(host="localhost", port=9876, token="tok")
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod,
        "send_request",
        lambda *a, **kw: {"result": {"value": 42}},
    )
    assert mod._assert_call("count") == {"value": 42}


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

_captured: dict[str, Any] = {}


def _patch(monkeypatch: Any, response: dict[str, Any]) -> None:
    def fake(
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _captured.clear()
        _captured["method"] = method
        _captured["params"] = params
        return response

    monkeypatch.setattr(mod, "_assert_call", fake)


def _run(*args: str) -> Any:
    return CliRunner().invoke(main, list(args))


# ---------------------------------------------------------------------------
# assert-pixel
# ---------------------------------------------------------------------------

_EXPECT = "0.5 0.3 0.1 1.0"
_PX = ["assert-pixel", "88", "512", "384"]


def _pixel_resp(
    mods: list[tuple[int, bool, dict[str, float]]],
) -> dict[str, Any]:
    return {
        "modifications": [
            {"eid": eid, "passed": passed, "post_mod": pm} for eid, passed, pm in mods
        ],
    }


_RGBA_A = {"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0}
_RGBA_B = {"r": 0.8, "g": 0.6, "b": 0.4, "a": 1.0}


def test_assert_pixel_exact_match(monkeypatch: Any) -> None:
    _patch(monkeypatch, _pixel_resp([(88, True, _RGBA_A)]))
    r = _run(*_PX, "--expect", _EXPECT, "--tolerance", "0")
    assert r.exit_code == 0
    assert r.output.startswith("pass:")


def test_assert_pixel_within_tolerance(monkeypatch: Any) -> None:
    pm = {"r": 0.505, "g": 0.305, "b": 0.105, "a": 1.005}
    _patch(monkeypatch, _pixel_resp([(88, True, pm)]))
    r = _run(*_PX, "--expect", _EXPECT, "--tolerance", "0.01")
    assert r.exit_code == 0


def test_assert_pixel_outside_tolerance(monkeypatch: Any) -> None:
    pm = {"r": 0.52, "g": 0.3, "b": 0.1, "a": 1.0}
    _patch(monkeypatch, _pixel_resp([(88, True, pm)]))
    r = _run(*_PX, "--expect", _EXPECT, "--tolerance", "0.01")
    assert r.exit_code == 1
    assert r.output.startswith("fail:")


def test_assert_pixel_tolerance_boundary(monkeypatch: Any) -> None:
    pm = {"r": 0.51, "g": 0.3, "b": 0.1, "a": 1.0}
    _patch(monkeypatch, _pixel_resp([(88, True, pm)]))
    r = _run(*_PX, "--expect", _EXPECT, "--tolerance", "0.01")
    assert r.exit_code == 0


def test_assert_pixel_no_passing_mod(monkeypatch: Any) -> None:
    _patch(monkeypatch, _pixel_resp([(88, False, _RGBA_A)]))
    r = _run(*_PX, "--expect", _EXPECT)
    assert r.exit_code == 2
    assert "no passing modification" in r.output


def test_assert_pixel_empty_modifications(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"modifications": []})
    r = _run(*_PX, "--expect", _EXPECT)
    assert r.exit_code == 2
    assert "no passing modification" in r.output


def test_assert_pixel_last_passing_used(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        _pixel_resp(
            [
                (80, True, _RGBA_A),
                (90, False, _RGBA_A),
                (100, True, _RGBA_B),
            ]
        ),
    )
    r = _run(
        "assert-pixel",
        "100",
        "512",
        "384",
        "--expect",
        "0.8 0.6 0.4 1.0",
        "--tolerance",
        "0",
    )
    assert r.exit_code == 0


def test_assert_pixel_json_pass(monkeypatch: Any) -> None:
    _patch(monkeypatch, _pixel_resp([(88, True, _RGBA_A)]))
    r = _run(*_PX, "--expect", _EXPECT, "--tolerance", "0", "--json")
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert data["pass"] is True
    assert "expected" in data
    assert "actual" in data
    assert "tolerance" in data


def test_assert_pixel_json_fail(monkeypatch: Any) -> None:
    pm = {"r": 0.9, "g": 0.3, "b": 0.1, "a": 1.0}
    _patch(monkeypatch, _pixel_resp([(88, True, pm)]))
    r = _run(
        *_PX,
        "--expect",
        _EXPECT,
        "--tolerance",
        "0",
        "--json",
    )
    assert r.exit_code == 1
    data = json.loads(r.output)
    assert data["pass"] is False


def test_assert_pixel_target_forwarded(monkeypatch: Any) -> None:
    _patch(monkeypatch, _pixel_resp([(88, True, _RGBA_A)]))
    _run(*_PX, "--expect", _EXPECT, "--target", "1")
    assert _captured["params"]["target"] == 1


def test_assert_pixel_bad_expect_nonnumeric(monkeypatch: Any) -> None:
    _patch(monkeypatch, _pixel_resp([(88, True, _RGBA_A)]))
    r = _run(*_PX, "--expect", "red green blue alpha")
    assert r.exit_code == 2
    assert "numeric" in r.output


# ---------------------------------------------------------------------------
# assert-clean
# ---------------------------------------------------------------------------


def test_assert_clean_no_messages(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"messages": []})
    r = _run("assert-clean")
    assert r.exit_code == 0
    assert r.output.startswith("pass:")


def test_assert_clean_below_threshold(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        {
            "messages": [
                {"level": "INFO", "eid": 1, "message": "info msg"},
                {"level": "INFO", "eid": 2, "message": "info msg 2"},
            ]
        },
    )
    r = _run("assert-clean", "--min-severity", "HIGH")
    assert r.exit_code == 0


def test_assert_clean_at_threshold(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        {
            "messages": [
                {"level": "HIGH", "eid": 1, "message": "high msg"},
            ]
        },
    )
    r = _run("assert-clean", "--min-severity", "HIGH")
    assert r.exit_code == 1
    assert r.output.startswith("fail:")


def test_assert_clean_above_threshold(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        {
            "messages": [
                {"level": "HIGH", "eid": 1, "message": "high msg"},
            ]
        },
    )
    r = _run("assert-clean", "--min-severity", "MEDIUM")
    assert r.exit_code == 1


def test_assert_clean_mixed_severities(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        {
            "messages": [
                {"level": "HIGH", "eid": 1, "message": "high msg"},
                {"level": "INFO", "eid": 2, "message": "info msg"},
            ]
        },
    )
    r = _run("assert-clean", "--min-severity", "MEDIUM")
    assert r.exit_code == 1
    assert "1 message(s)" in r.output


def test_assert_clean_default_severity_high(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        {
            "messages": [
                {"level": "INFO", "eid": 1, "message": "info msg"},
            ]
        },
    )
    r = _run("assert-clean")
    assert r.exit_code == 0


def test_assert_clean_json_pass(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"messages": []})
    r = _run("assert-clean", "--json")
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert data["pass"] is True
    assert data["count"] == 0
    assert data["messages"] == []


def test_assert_clean_json_fail(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        {
            "messages": [
                {"level": "HIGH", "eid": 1, "message": "msg1"},
                {"level": "HIGH", "eid": 2, "message": "msg2"},
            ]
        },
    )
    r = _run("assert-clean", "--json")
    assert r.exit_code == 1
    data = json.loads(r.output)
    assert data["pass"] is False
    assert data["count"] == 2
    assert len(data["messages"]) == 2


# ---------------------------------------------------------------------------
# assert-count
# ---------------------------------------------------------------------------


def test_assert_count_eq_pass(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"value": 42})
    r = _run("assert-count", "draws", "--expect", "42", "--op", "eq")
    assert r.exit_code == 0


def test_assert_count_eq_fail(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"value": 42})
    r = _run("assert-count", "draws", "--expect", "43", "--op", "eq")
    assert r.exit_code == 1


def test_assert_count_gt_pass(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"value": 10})
    r = _run("assert-count", "draws", "--expect", "5", "--op", "gt")
    assert r.exit_code == 0


def test_assert_count_gt_fail_boundary(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"value": 5})
    r = _run("assert-count", "draws", "--expect", "5", "--op", "gt")
    assert r.exit_code == 1


def test_assert_count_lt_pass(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"value": 3})
    r = _run("assert-count", "draws", "--expect", "5", "--op", "lt")
    assert r.exit_code == 0


def test_assert_count_ge_pass_boundary(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"value": 5})
    r = _run("assert-count", "draws", "--expect", "5", "--op", "ge")
    assert r.exit_code == 0


def test_assert_count_le_fail(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"value": 6})
    r = _run("assert-count", "draws", "--expect", "5", "--op", "le")
    assert r.exit_code == 1


def test_assert_count_default_op_eq(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"value": 42})
    r = _run("assert-count", "draws", "--expect", "42")
    assert r.exit_code == 0


def test_assert_count_pass_forwarded(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"value": 42})
    _run(
        "assert-count",
        "draws",
        "--expect",
        "42",
        "--pass",
        "GBuffer",
    )
    assert _captured["params"]["pass"] == "GBuffer"


def test_assert_count_json(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"value": 42})
    r = _run("assert-count", "draws", "--expect", "42", "--json")
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert data["pass"] is True
    assert data["what"] == "draws"
    assert data["actual"] == 42
    assert data["expected"] == 42
    assert data["op"] == "eq"


# ---------------------------------------------------------------------------
# assert-state
# ---------------------------------------------------------------------------

_ST = ["assert-state", "120"]


def test_assert_state_simple_match(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "topology": "TriangleList"})
    r = _run(
        *_ST,
        "topology.topology",
        "--expect",
        "TriangleList",
    )
    assert r.exit_code == 0


def test_assert_state_simple_mismatch(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "topology": "TriangleList"})
    r = _run(*_ST, "topology.topology", "--expect", "LineList")
    assert r.exit_code == 1


def test_assert_state_nested_path(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "blends": [{"enabled": True}]})
    r = _run(
        *_ST,
        "blend.blends.0.enabled",
        "--expect",
        "true",
    )
    assert r.exit_code == 0


def test_assert_state_array_index(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        {
            "eid": 120,
            "blends": [
                {"colorBlend": {"source": "One"}},
                {"colorBlend": {"source": "Zero"}},
            ],
        },
    )
    r = _run(
        *_ST,
        "blend.blends.1.colorBlend.source",
        "--expect",
        "Zero",
    )
    assert r.exit_code == 0


def test_assert_state_bool_case_insensitive(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "blends": [{"enabled": True}]})
    for val in ["True", "true", "TRUE"]:
        r = _run(
            *_ST,
            "blend.blends.0.enabled",
            "--expect",
            val,
        )
        assert r.exit_code == 0, f"Failed for --expect {val}"


def test_assert_state_numeric_value(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "width": 1920})
    r = _run(*_ST, "viewport.width", "--expect", "1920")
    assert r.exit_code == 0


def test_assert_state_invalid_section(monkeypatch: Any) -> None:
    r = _run(*_ST, "nosuch.field", "--expect", "x")
    assert r.exit_code == 2
    assert "invalid section" in r.output


def test_assert_state_key_not_found(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "blends": [{"enabled": True}]})
    r = _run(*_ST, "blend.nosuchkey", "--expect", "x")
    assert r.exit_code == 2
    assert "not found" in r.output


def test_assert_state_index_out_of_range(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "blends": [{"enabled": True}]})
    r = _run(
        *_ST,
        "blend.blends.99.enabled",
        "--expect",
        "true",
    )
    assert r.exit_code == 2


def test_assert_state_hyphenated_section(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "depthEnable": True})
    r = _run(
        *_ST,
        "depth-stencil.depthEnable",
        "--expect",
        "true",
    )
    assert r.exit_code == 0
    assert _captured["params"]["section"] == "depth-stencil"


def test_assert_state_json_pass(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "topology": "TriangleList"})
    r = _run(
        *_ST,
        "topology.topology",
        "--expect",
        "TriangleList",
        "--json",
    )
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert data["pass"] is True
    assert data["key_path"] == "topology.topology"
    assert data["eid"] == 120


def test_assert_state_json_fail(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "topology": "TriangleList"})
    r = _run(
        *_ST,
        "topology.topology",
        "--expect",
        "LineList",
        "--json",
    )
    assert r.exit_code == 1
    data = json.loads(r.output)
    assert data["pass"] is False


def test_assert_state_topology_single_segment_pass(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "topology": "TriangleList"})
    r = _run(*_ST, "topology", "--expect", "TriangleList")
    assert r.exit_code == 0


def test_assert_state_topology_single_segment_fail(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "topology": "TriangleList"})
    r = _run(*_ST, "topology", "--expect", "PointList")
    assert r.exit_code == 1


def test_assert_state_vs_shader_unwrap(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        {
            "row": {
                "eid": 120,
                "section": "vs",
                "section_detail": {
                    "eid": 120,
                    "stage": "vs",
                    "shader": 42,
                    "entry": "main",
                    "ro": 0,
                    "rw": 0,
                    "cbuffers": 1,
                },
            },
        },
    )
    r = _run(*_ST, "vs.shader", "--expect", "42")
    assert r.exit_code == 0


def test_assert_state_vs_entry_unwrap(monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        {
            "row": {
                "eid": 120,
                "section": "vs",
                "section_detail": {
                    "eid": 120,
                    "stage": "vs",
                    "shader": 42,
                    "entry": "main",
                    "ro": 0,
                    "rw": 0,
                    "cbuffers": 1,
                },
            },
        },
    )
    r = _run(*_ST, "vs.entry", "--expect", "main")
    assert r.exit_code == 0


def test_assert_state_topology_two_segment_regression(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "topology": "TriangleList"})
    r = _run(*_ST, "topology.topology", "--expect", "TriangleList")
    assert r.exit_code == 0


def test_assert_state_key_not_found_error(monkeypatch: Any) -> None:
    _patch(monkeypatch, {"eid": 120, "topology": "TriangleList"})
    r = _run(*_ST, "topology.nosuchkey", "--expect", "x")
    assert r.exit_code == 2
    assert "not found" in r.output


# ---------------------------------------------------------------------------
# CLI registration
# ---------------------------------------------------------------------------

_ASSERT_CMDS = [
    "assert-pixel",
    "assert-clean",
    "assert-count",
    "assert-state",
]


def test_assert_commands_in_help() -> None:
    r = _run("--help")
    for cmd in _ASSERT_CMDS:
        assert cmd in r.output, f"{cmd} not in --help"


def test_assert_commands_help_exits_0() -> None:
    for cmd in _ASSERT_CMDS:
        r = _run(cmd, "--help")
        assert r.exit_code == 0, f"{cmd} --help failed"


# ---------------------------------------------------------------------------
# PR#84: JSON-aware error formatting in assert_ci
# ---------------------------------------------------------------------------


def test_assert_pixel_bad_expect_json_error(monkeypatch: Any) -> None:
    """--json with bad --expect format outputs JSON error on stderr."""
    _patch(monkeypatch, _pixel_resp([(88, True, _RGBA_A)]))
    r = CliRunner().invoke(
        main, ["assert-pixel", "88", "0", "0", "--expect", "red green blue alpha", "--json"]
    )
    assert r.exit_code == 2
    data = json.loads(r.stderr.strip())
    assert "error" in data
    assert "numeric" in data["error"]["message"]


def test_assert_pixel_bad_expect_count_json_error(monkeypatch: Any) -> None:
    """--json with wrong number of floats outputs JSON error."""
    _patch(monkeypatch, _pixel_resp([(88, True, _RGBA_A)]))
    r = CliRunner().invoke(
        main, ["assert-pixel", "88", "0", "0", "--expect", "1.0 2.0 3.0", "--json"]
    )
    assert r.exit_code == 2
    data = json.loads(r.stderr.strip())
    assert "error" in data
    assert "4 floats" in data["error"]["message"]


def test_assert_pixel_no_passing_json_error(monkeypatch: Any) -> None:
    """--json with no passing modification outputs JSON error."""
    _patch(monkeypatch, _pixel_resp([(88, False, _RGBA_A)]))
    r = CliRunner().invoke(main, ["assert-pixel", "88", "0", "0", "--expect", _EXPECT, "--json"])
    assert r.exit_code == 2
    data = json.loads(r.stderr.strip())
    assert "error" in data
    assert "no passing" in data["error"]["message"]


def test_assert_state_invalid_section_json_error(monkeypatch: Any) -> None:
    """--json with invalid section outputs JSON error."""
    r = CliRunner().invoke(main, ["assert-state", "120", "nosuch.field", "--expect", "x", "--json"])
    assert r.exit_code == 2
    data = json.loads(r.stderr.strip())
    assert "error" in data
    assert "invalid section" in data["error"]["message"]


def test_assert_state_key_not_found_json_error(monkeypatch: Any) -> None:
    """--json with key not found outputs JSON error."""
    _patch(monkeypatch, {"eid": 120, "topology": "TriangleList"})
    r = CliRunner().invoke(
        main, ["assert-state", "120", "topology.nosuchkey", "--expect", "x", "--json"]
    )
    assert r.exit_code == 2
    data = json.loads(r.stderr.strip())
    assert "error" in data
    assert "not found" in data["error"]["message"]
