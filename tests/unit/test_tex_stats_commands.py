"""Tests for rdc tex-stats CLI command."""

from __future__ import annotations

from typing import Any

from click.testing import CliRunner
from conftest import assert_json_output

from rdc.cli import main
from rdc.commands import tex_stats as tex_stats_mod

_HAPPY_RESPONSE: dict[str, Any] = {
    "id": 42,
    "eid": 100,
    "mip": 0,
    "slice": 0,
    "min": {"r": 0.0, "g": 0.0, "b": 0.01, "a": 1.0},
    "max": {"r": 1.0, "g": 0.85, "b": 0.92, "a": 1.0},
}

_HISTOGRAM_RESPONSE: dict[str, Any] = {
    **_HAPPY_RESPONSE,
    "histogram": [{"bucket": i, "r": i, "g": i * 2, "b": i * 3, "a": 0} for i in range(256)],
}

_captured_params: dict[str, Any] = {}


def _patch(monkeypatch: Any, response: dict[str, Any]) -> None:
    def fake_daemon_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        _captured_params.clear()
        _captured_params["method"] = method
        _captured_params["params"] = params
        return response

    monkeypatch.setattr(tex_stats_mod, "call", fake_daemon_call)


# ---------------------------------------------------------------------------
# Table output
# ---------------------------------------------------------------------------


def test_tex_stats_table_output(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["tex-stats", "42"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert lines[0] == "CHANNEL\tMIN\tMAX"
    assert len(lines) == 5  # header + 4 rows
    assert lines[1].startswith("R\t")
    assert lines[4].startswith("A\t")


def test_tex_stats_float_format(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["tex-stats", "42"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert "0.0000" in lines[1]
    assert "1.0000" in lines[1]
    assert "0.0100" in lines[3]


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def test_tex_stats_json(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    result = CliRunner().invoke(main, ["tex-stats", "42", "--json"])
    data = assert_json_output(result)
    assert "min" in data
    assert "max" in data
    assert data["min"]["r"] == 0.0


# ---------------------------------------------------------------------------
# Histogram
# ---------------------------------------------------------------------------


def test_tex_stats_histogram_table(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HISTOGRAM_RESPONSE)
    result = CliRunner().invoke(main, ["tex-stats", "42", "--histogram"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    # 5 lines for min/max table, then 257 lines for histogram (header + 256 rows)
    assert "CHANNEL\tMIN\tMAX" in lines[0]
    assert "BUCKET\tR\tG\tB\tA" in result.output


def test_tex_stats_histogram_json(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HISTOGRAM_RESPONSE)
    result = CliRunner().invoke(main, ["tex-stats", "42", "--histogram", "--json"])
    data = assert_json_output(result)
    assert "histogram" in data
    assert len(data["histogram"]) == 256


# ---------------------------------------------------------------------------
# Argument forwarding
# ---------------------------------------------------------------------------


def test_tex_stats_eid_arg(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    CliRunner().invoke(main, ["tex-stats", "42", "200"])
    assert _captured_params["params"]["eid"] == 200


def test_tex_stats_eid_omitted(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    CliRunner().invoke(main, ["tex-stats", "42"])
    assert "eid" not in _captured_params["params"]


def test_tex_stats_mip_slice(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    CliRunner().invoke(main, ["tex-stats", "42", "--mip", "2", "--slice", "1"])
    assert _captured_params["params"]["mip"] == 2
    assert _captured_params["params"]["slice"] == 1


def test_tex_stats_histogram_flag(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    CliRunner().invoke(main, ["tex-stats", "42", "--histogram"])
    assert _captured_params["params"]["histogram"] is True


def test_tex_stats_no_histogram_flag(monkeypatch: Any) -> None:
    _patch(monkeypatch, _HAPPY_RESPONSE)
    CliRunner().invoke(main, ["tex-stats", "42"])
    assert "histogram" not in _captured_params["params"]


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


def test_tex_stats_help() -> None:
    result = CliRunner().invoke(main, ["tex-stats", "--help"])
    assert result.exit_code == 0
    assert "min/max" in result.output.lower() or "histogram" in result.output.lower()


def test_tex_stats_registered() -> None:
    assert "tex-stats" in CliRunner().invoke(main, ["--help"]).output
