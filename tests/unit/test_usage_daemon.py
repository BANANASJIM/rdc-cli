"""Tests for daemon server usage handlers."""

from __future__ import annotations

import sys
from pathlib import Path

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd  # noqa: E402


def _state_with_usage() -> DaemonState:
    ctrl = rd.MockReplayController()
    ctrl._resources = [
        rd.ResourceDescription(
            resourceId=rd.ResourceId(97), name="2D Image 97", type=rd.ResourceType.Texture
        ),
        rd.ResourceDescription(
            resourceId=rd.ResourceId(105), name="Buffer 105", type=rd.ResourceType.Buffer
        ),
        rd.ResourceDescription(
            resourceId=rd.ResourceId(200), name="Empty Res", type=rd.ResourceType.Texture
        ),
    ]
    ctrl._usage_map = {
        97: [
            rd.EventUsage(eventId=6, usage=rd.ResourceUsage.Clear),
            rd.EventUsage(eventId=11, usage=rd.ResourceUsage.ColorTarget),
            rd.EventUsage(eventId=12, usage=rd.ResourceUsage.CopySrc),
        ],
        105: [
            rd.EventUsage(eventId=11, usage=rd.ResourceUsage.VS_Constants),
        ],
        200: [],
    }
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 33))
    state.res_names = {97: "2D Image 97", 105: "Buffer 105", 200: "Empty Res"}
    state.res_types = {97: "Texture", 105: "Buffer", 200: "Texture"}
    return state


def _req(method: str, params: dict | None = None) -> dict:
    p = {"_token": "tok"}
    if params:
        p.update(params)
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": p}


# ---------------------------------------------------------------------------
# usage (single resource)
# ---------------------------------------------------------------------------


def test_usage_happy_path() -> None:
    state = _state_with_usage()
    resp, running = _handle_request(_req("usage", {"id": 97}), state)
    assert running
    r = resp["result"]
    assert r["id"] == 97
    assert r["name"] == "2D Image 97"
    entries = r["entries"]
    assert len(entries) == 3
    assert entries[0] == {"eid": 6, "usage": "Clear"}
    assert entries[1] == {"eid": 11, "usage": "ColorTarget"}
    assert entries[2] == {"eid": 12, "usage": "CopySrc"}


def test_usage_empty_entries() -> None:
    state = _state_with_usage()
    resp, running = _handle_request(_req("usage", {"id": 200}), state)
    assert running
    r = resp["result"]
    assert r["id"] == 200
    assert r["entries"] == []


def test_usage_not_found() -> None:
    state = _state_with_usage()
    resp, _ = _handle_request(_req("usage", {"id": 999}), state)
    assert resp["error"]["code"] == -32001
    assert "999" in resp["error"]["message"]


def test_usage_no_adapter() -> None:
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("usage", {"id": 97}), state)
    assert resp["error"]["code"] == -32002


# ---------------------------------------------------------------------------
# usage_all (cross-resource matrix)
# ---------------------------------------------------------------------------


def test_usage_all_no_filters() -> None:
    state = _state_with_usage()
    resp, running = _handle_request(_req("usage_all"), state)
    assert running
    r = resp["result"]
    # 3 rows for rid 97, 1 row for rid 105, 0 for rid 200 (empty)
    assert r["total"] == 4
    assert len(r["rows"]) == 4


def test_usage_all_type_filter() -> None:
    state = _state_with_usage()
    resp, _ = _handle_request(_req("usage_all", {"type": "Texture"}), state)
    r = resp["result"]
    # Only rid 97 (Texture) has entries; rid 200 (Texture) has none
    assert r["total"] == 3
    for row in r["rows"]:
        assert row["id"] == 97


def test_usage_all_usage_filter() -> None:
    state = _state_with_usage()
    resp, _ = _handle_request(_req("usage_all", {"usage": "ColorTarget"}), state)
    r = resp["result"]
    assert r["total"] == 1
    assert r["rows"][0]["usage"] == "ColorTarget"
    assert r["rows"][0]["eid"] == 11


def test_usage_all_both_filters() -> None:
    state = _state_with_usage()
    resp, _ = _handle_request(_req("usage_all", {"type": "Texture", "usage": "Clear"}), state)
    r = resp["result"]
    assert r["total"] == 1
    row = r["rows"][0]
    assert row["id"] == 97
    assert row["usage"] == "Clear"


def test_usage_all_no_adapter() -> None:
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("usage_all"), state)
    assert resp["error"]["code"] == -32002
