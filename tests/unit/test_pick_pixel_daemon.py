"""Tests for daemon pick_pixel handler."""

from __future__ import annotations

import sys
from pathlib import Path

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd  # noqa: E402


def _make_state(
    pick_pixel: dict[tuple[int, int], rd.PixelValue] | None = None,
    output_targets: list[rd.Descriptor] | None = None,
    ms_samp: int = 1,
) -> DaemonState:
    ctrl = rd.MockReplayController()
    rt_rid = rd.ResourceId(42)
    rt_rid2 = rd.ResourceId(43)
    targets = output_targets or [rd.Descriptor(resource=rt_rid)]
    ctrl._pipe_state = rd.MockPipeState(output_targets=targets)
    ctrl._pick_pixel_map = pick_pixel or {}
    ctrl._textures = [
        rd.TextureDescription(resourceId=rt_rid, width=1024, height=768, msSamp=ms_samp),
        rd.TextureDescription(resourceId=rt_rid2, width=1024, height=768, msSamp=1),
    ]
    ctrl._actions = [
        rd.ActionDescription(eventId=120, flags=rd.ActionFlags.Drawcall, _name="vkCmdDraw"),
    ]

    state = DaemonState(capture="test.rdc", current_eid=120, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 120
    state.rd = rd
    state.tex_map = {int(t.resourceId): t for t in ctrl._textures}
    return state


def _req(method: str, params: dict | None = None) -> dict:
    p = {"_token": "tok"}
    if params:
        p.update(params)
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": p}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_pick_pixel_happy() -> None:
    pv = rd.PixelValue(floatValue=[0.5, 0.3, 0.1, 1.0])
    state = _make_state(pick_pixel={(512, 384): pv})
    resp, running = _handle_request(_req("pick_pixel", {"x": 512, "y": 384}), state)
    assert running
    r = resp["result"]
    assert r["color"] == {"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0}


def test_pick_pixel_result_schema() -> None:
    pv = rd.PixelValue(floatValue=[0.5, 0.3, 0.1, 1.0])
    state = _make_state(pick_pixel={(512, 384): pv})
    resp, _ = _handle_request(_req("pick_pixel", {"x": 512, "y": 384}), state)
    r = resp["result"]
    assert r["x"] == 512
    assert r["y"] == 384
    assert r["eid"] == 120
    assert r["target"] == {"index": 0, "id": 42}


def test_pick_pixel_target_index_1() -> None:
    rt0 = rd.Descriptor(resource=rd.ResourceId(42))
    rt1 = rd.Descriptor(resource=rd.ResourceId(43))
    pv = rd.PixelValue(floatValue=[1.0, 0.0, 0.0, 1.0])
    state = _make_state(pick_pixel={(100, 200): pv}, output_targets=[rt0, rt1])
    resp, _ = _handle_request(_req("pick_pixel", {"x": 100, "y": 200, "target": 1}), state)
    r = resp["result"]
    assert r["target"]["index"] == 1
    assert r["target"]["id"] == 43


def test_pick_pixel_eid_defaults_to_current() -> None:
    state = _make_state(pick_pixel={(10, 20): rd.PixelValue()})
    state.current_eid = 120
    resp, _ = _handle_request(_req("pick_pixel", {"x": 10, "y": 20}), state)
    assert resp["result"]["eid"] == 120


def test_pick_pixel_eid_override() -> None:
    state = _make_state(pick_pixel={(10, 20): rd.PixelValue()})
    state._eid_cache = -1
    resp, _ = _handle_request(_req("pick_pixel", {"x": 10, "y": 20, "eid": 120}), state)
    ctrl = state.adapter.controller  # type: ignore[union-attr]
    assert (120, True) in ctrl._set_frame_event_calls


def test_pick_pixel_unknown_pixel_returns_zero() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pick_pixel", {"x": 999, "y": 999}), state)
    assert resp["error"]["code"] == -32001
    assert "out of bounds" in resp["error"]["message"]


def test_pick_pixel_keep_running_true() -> None:
    state = _make_state()
    _, running = _handle_request(_req("pick_pixel", {"x": 0, "y": 0}), state)
    assert running is True


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_pick_pixel_no_adapter() -> None:
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("pick_pixel", {"x": 0, "y": 0}), state)
    assert resp["error"]["code"] == -32002


def test_pick_pixel_missing_x() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pick_pixel", {"y": 0}), state)
    assert resp["error"]["code"] == -32602
    assert "x" in resp["error"]["message"]


def test_pick_pixel_missing_y() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pick_pixel", {"x": 0}), state)
    assert resp["error"]["code"] == -32602
    assert "y" in resp["error"]["message"]


def test_pick_pixel_no_targets() -> None:
    state = _make_state(output_targets=[rd.Descriptor(resource=rd.ResourceId(0))])
    resp, _ = _handle_request(_req("pick_pixel", {"x": 0, "y": 0}), state)
    assert resp["error"]["code"] == -32001
    assert "no color targets" in resp["error"]["message"]


def test_pick_pixel_target_out_of_range() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pick_pixel", {"x": 0, "y": 0, "target": 5}), state)
    assert resp["error"]["code"] == -32001


def test_pick_pixel_eid_out_of_range() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pick_pixel", {"x": 0, "y": 0, "eid": 9999}), state)
    assert resp["error"]["code"] == -32002


def test_pick_pixel_msaa_rejected() -> None:
    state = _make_state(ms_samp=4)
    resp, _ = _handle_request(_req("pick_pixel", {"x": 0, "y": 0}), state)
    assert resp["error"]["code"] == -32001
    assert "MSAA" in resp["error"]["message"]


# ---------------------------------------------------------------------------
# Bounds checking
# ---------------------------------------------------------------------------


def test_pick_pixel_out_of_bounds_x() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pick_pixel", {"x": 1024, "y": 0}), state)
    assert resp["error"]["code"] == -32001
    assert "out of bounds" in resp["error"]["message"]


def test_pick_pixel_out_of_bounds_y() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pick_pixel", {"x": 0, "y": 768}), state)
    assert resp["error"]["code"] == -32001
    assert "out of bounds" in resp["error"]["message"]


def test_pick_pixel_at_boundary() -> None:
    pv = rd.PixelValue(floatValue=[0.1, 0.2, 0.3, 1.0])
    state = _make_state(pick_pixel={(1023, 767): pv})
    resp, _ = _handle_request(_req("pick_pixel", {"x": 1023, "y": 767}), state)
    assert "result" in resp
    assert resp["result"]["color"] == {"r": 0.1, "g": 0.2, "b": 0.3, "a": 1.0}


def test_pixel_history_out_of_bounds() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pixel_history", {"x": 1024, "y": 0}), state)
    assert resp["error"]["code"] == -32001
    assert "out of bounds" in resp["error"]["message"]


def test_pick_pixel_negative_coords() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pick_pixel", {"x": -1, "y": 0}), state)
    assert resp["error"]["code"] == -32001
    assert "out of bounds" in resp["error"]["message"]


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def test_pick_pixel_handler_registered() -> None:
    from rdc.handlers.pixel import HANDLERS

    assert "pick_pixel" in HANDLERS
