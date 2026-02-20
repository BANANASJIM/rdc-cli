"""Tests for daemon server counter_list and counter_fetch handlers."""

from __future__ import annotations

import sys
from pathlib import Path

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd  # noqa: E402


def _make_ctrl() -> rd.MockReplayController:
    ctrl = rd.MockReplayController()
    ctrl._counter_descriptions = {
        1: rd.CounterDescription(
            name="EventGPUDuration",
            category="Vulkan Built-in",
            description="GPU time for this event",
            counter=rd.GPUCounter.EventGPUDuration,
            resultByteWidth=8,
            resultType=rd.CompType.Float,
            unit=rd.CounterUnit.Seconds,
        ),
        8: rd.CounterDescription(
            name="VSInvocations",
            category="Vulkan Built-in",
            description="Vertex shader invocations",
            counter=rd.GPUCounter.VSInvocations,
            resultByteWidth=8,
            resultType=rd.CompType.UInt,
            unit=rd.CounterUnit.Absolute,
        ),
        12: rd.CounterDescription(
            name="PSInvocations",
            category="Vulkan Built-in",
            description="Pixel shader invocations",
            counter=rd.GPUCounter.PSInvocations,
            resultByteWidth=8,
            resultType=rd.CompType.UInt,
            unit=rd.CounterUnit.Absolute,
        ),
    }
    ctrl._counter_results = [
        rd.CounterResult(
            eventId=10,
            counter=rd.GPUCounter.EventGPUDuration,
            value=rd.CounterValue(d=0.00123),
        ),
        rd.CounterResult(
            eventId=10,
            counter=rd.GPUCounter.VSInvocations,
            value=rd.CounterValue(u64=4096),
        ),
        rd.CounterResult(
            eventId=10,
            counter=rd.GPUCounter.PSInvocations,
            value=rd.CounterValue(u64=8192),
        ),
        rd.CounterResult(
            eventId=20,
            counter=rd.GPUCounter.EventGPUDuration,
            value=rd.CounterValue(d=0.00456),
        ),
        rd.CounterResult(
            eventId=20,
            counter=rd.GPUCounter.VSInvocations,
            value=rd.CounterValue(u64=512),
        ),
        rd.CounterResult(
            eventId=20,
            counter=rd.GPUCounter.PSInvocations,
            value=rd.CounterValue(u64=1024),
        ),
    ]
    return ctrl


def _state_with_counters() -> DaemonState:
    ctrl = _make_ctrl()
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    return state


def _req(method: str, params: dict | None = None) -> dict:
    p = {"_token": "tok"}
    if params:
        p.update(params)
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": p}


# ---------------------------------------------------------------------------
# counter_list
# ---------------------------------------------------------------------------


def test_counter_list_happy_path() -> None:
    state = _state_with_counters()
    resp, running = _handle_request(_req("counter_list"), state)
    assert running
    r = resp["result"]
    assert r["total"] == 3
    counters = r["counters"]
    assert len(counters) == 3
    names = {c["name"] for c in counters}
    assert names == {"EventGPUDuration", "VSInvocations", "PSInvocations"}


def test_counter_list_fields() -> None:
    state = _state_with_counters()
    resp, _ = _handle_request(_req("counter_list"), state)
    counters = resp["result"]["counters"]
    gpu_dur = next(c for c in counters if c["name"] == "EventGPUDuration")
    assert gpu_dur["id"] == 1
    assert gpu_dur["unit"] == "Seconds"
    assert gpu_dur["type"] == "Float"
    assert gpu_dur["category"] == "Vulkan Built-in"
    assert gpu_dur["byte_width"] == 8


def test_counter_list_no_adapter() -> None:
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("counter_list"), state)
    assert resp["error"]["code"] == -32002


def test_counter_list_skips_error_counters() -> None:
    ctrl = _make_ctrl()
    ctrl._counter_descriptions[3000000] = rd.CounterDescription(
        name="ERROR: Could not find Nsight Perf SDK library",
        category="",
    )
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    resp, _ = _handle_request(_req("counter_list"), state)
    counters = resp["result"]["counters"]
    assert all(not c["name"].startswith("ERROR") for c in counters)
    assert resp["result"]["total"] == 3


def test_counter_list_skips_empty_name_counters() -> None:
    ctrl = _make_ctrl()
    ctrl._counter_descriptions[999] = rd.CounterDescription(name="", category="")
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    resp, _ = _handle_request(_req("counter_list"), state)
    assert resp["result"]["total"] == 3


# ---------------------------------------------------------------------------
# counter_fetch
# ---------------------------------------------------------------------------


def test_counter_fetch_happy_path() -> None:
    state = _state_with_counters()
    resp, running = _handle_request(_req("counter_fetch"), state)
    assert running
    r = resp["result"]
    assert r["total"] == 6
    rows = r["rows"]
    assert len(rows) == 6


def test_counter_fetch_sorted_by_eid_then_name() -> None:
    state = _state_with_counters()
    resp, _ = _handle_request(_req("counter_fetch"), state)
    rows = resp["result"]["rows"]
    keys = [(row["eid"], row["counter"]) for row in rows]
    assert keys == sorted(keys)


def test_counter_fetch_eid_filter() -> None:
    state = _state_with_counters()
    resp, _ = _handle_request(_req("counter_fetch", {"eid": 10}), state)
    rows = resp["result"]["rows"]
    assert resp["result"]["total"] == 3
    assert all(r["eid"] == 10 for r in rows)


def test_counter_fetch_name_filter() -> None:
    state = _state_with_counters()
    resp, _ = _handle_request(_req("counter_fetch", {"name": "Duration"}), state)
    rows = resp["result"]["rows"]
    assert all(r["counter"] == "EventGPUDuration" for r in rows)
    assert len(rows) == 2


def test_counter_fetch_combined_filters() -> None:
    state = _state_with_counters()
    resp, _ = _handle_request(_req("counter_fetch", {"eid": 20, "name": "PS"}), state)
    rows = resp["result"]["rows"]
    assert len(rows) == 1
    assert rows[0]["eid"] == 20
    assert rows[0]["counter"] == "PSInvocations"


def test_counter_fetch_no_adapter() -> None:
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("counter_fetch"), state)
    assert resp["error"]["code"] == -32002


def test_counter_fetch_float_value() -> None:
    state = _state_with_counters()
    resp, _ = _handle_request(_req("counter_fetch", {"name": "EventGPUDuration", "eid": 10}), state)
    rows = resp["result"]["rows"]
    assert len(rows) == 1
    assert abs(rows[0]["value"] - 0.00123) < 1e-9
    assert rows[0]["unit"] == "Seconds"


def test_counter_fetch_uint_value() -> None:
    state = _state_with_counters()
    resp, _ = _handle_request(_req("counter_fetch", {"name": "VSInvocations", "eid": 10}), state)
    rows = resp["result"]["rows"]
    assert len(rows) == 1
    assert rows[0]["value"] == 4096


def test_counter_fetch_no_match_name_filter() -> None:
    state = _state_with_counters()
    resp, _ = _handle_request(_req("counter_fetch", {"name": "NonExistent"}), state)
    assert resp["result"]["total"] == 0
    assert resp["result"]["rows"] == []


def test_counter_list_empty() -> None:
    ctrl = rd.MockReplayController()
    ctrl._counter_descriptions = {}
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    resp, _ = _handle_request(_req("counter_list"), state)
    assert resp["result"]["counters"] == []
    assert resp["result"]["total"] == 0


def test_counter_fetch_empty() -> None:
    ctrl = rd.MockReplayController()
    ctrl._counter_descriptions = {}
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    resp, _ = _handle_request(_req("counter_fetch"), state)
    assert resp["result"]["rows"] == []
    assert resp["result"]["total"] == 0


def test_counter_fetch_invalid_eid() -> None:
    state = _state_with_counters()
    resp, _ = _handle_request(_req("counter_fetch", {"eid": "abc"}), state)
    assert resp["error"]["code"] == -32602


def test_counter_list_has_uuid() -> None:
    state = _state_with_counters()
    resp, _ = _handle_request(_req("counter_list"), state)
    for c in resp["result"]["counters"]:
        assert "uuid" in c
