"""Tests for rdc counters CLI command."""

from __future__ import annotations

import json
from typing import Any

from click.testing import CliRunner

from rdc.cli import main
from rdc.commands import counters as counters_mod

_LIST_RESPONSE = {
    "counters": [
        {
            "id": 1,
            "name": "EventGPUDuration",
            "unit": "Seconds",
            "type": "Float",
            "category": "Vulkan Built-in",
            "description": "GPU time for this event",
            "byte_width": 8,
        },
        {
            "id": 8,
            "name": "VSInvocations",
            "unit": "Absolute",
            "type": "UInt",
            "category": "Vulkan Built-in",
            "description": "Vertex shader invocations",
            "byte_width": 8,
        },
    ],
    "total": 2,
}

_FETCH_RESPONSE = {
    "rows": [
        {"eid": 10, "counter": "EventGPUDuration", "value": 0.00123, "unit": "Seconds"},
        {"eid": 10, "counter": "VSInvocations", "value": 4096, "unit": "Absolute"},
        {"eid": 20, "counter": "EventGPUDuration", "value": 0.00456, "unit": "Seconds"},
    ],
    "total": 3,
}


def _patch(monkeypatch: Any, response: dict) -> None:
    monkeypatch.setattr(counters_mod, "_daemon_call", lambda method, params=None: response)


def test_counters_list_tsv(monkeypatch: Any) -> None:
    _patch(monkeypatch, _LIST_RESPONSE)
    result = CliRunner().invoke(main, ["counters", "--list"])
    assert result.exit_code == 0
    assert "ID\tNAME\tUNIT\tTYPE\tCATEGORY" in result.output
    assert "1\tEventGPUDuration\tSeconds\tFloat\tVulkan Built-in" in result.output
    assert "8\tVSInvocations\tAbsolute\tUInt\tVulkan Built-in" in result.output


def test_counters_list_json(monkeypatch: Any) -> None:
    _patch(monkeypatch, _LIST_RESPONSE)
    result = CliRunner().invoke(main, ["counters", "--list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total"] == 2
    assert len(data["counters"]) == 2


def test_counters_fetch_default_tsv(monkeypatch: Any) -> None:
    _patch(monkeypatch, _FETCH_RESPONSE)
    result = CliRunner().invoke(main, ["counters"])
    assert result.exit_code == 0
    assert "EID\tCOUNTER\tVALUE\tUNIT" in result.output
    assert "10\tEventGPUDuration\t0.00123\tSeconds" in result.output
    assert "10\tVSInvocations\t4096\tAbsolute" in result.output


def test_counters_eid_filter_tsv(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def _capture(method: str, params: dict | None = None) -> dict:
        captured["method"] = method
        captured["params"] = params or {}
        return {
            "rows": [{"eid": 10, "counter": "EventGPUDuration", "value": 0.001, "unit": "Seconds"}],
            "total": 1,
        }

    monkeypatch.setattr(counters_mod, "_daemon_call", _capture)
    result = CliRunner().invoke(main, ["counters", "--eid", "10"])
    assert result.exit_code == 0
    assert captured["params"].get("eid") == 10
    assert "EID\tCOUNTER\tVALUE\tUNIT" in result.output


def test_counters_name_filter_tsv(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def _capture(method: str, params: dict | None = None) -> dict:
        captured["method"] = method
        captured["params"] = params or {}
        return {
            "rows": [{"eid": 10, "counter": "EventGPUDuration", "value": 0.001, "unit": "Seconds"}],
            "total": 1,
        }

    monkeypatch.setattr(counters_mod, "_daemon_call", _capture)
    result = CliRunner().invoke(main, ["counters", "--name", "Duration"])
    assert result.exit_code == 0
    assert captured["params"].get("name") == "Duration"


def test_counters_fetch_json(monkeypatch: Any) -> None:
    _patch(monkeypatch, _FETCH_RESPONSE)
    result = CliRunner().invoke(main, ["counters", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total"] == 3
    assert len(data["rows"]) == 3
