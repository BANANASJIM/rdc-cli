"""Tests for daemon tex_stats handler."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd  # noqa: E402


def _make_state(
    tex_id: int = 42,
    ms_samp: int = 1,
    min_max: tuple[rd.PixelValue, rd.PixelValue] | None = None,
    histogram: dict[tuple[int, int], list[int]] | None = None,
) -> DaemonState:
    ctrl = rd.MockReplayController()
    rid = rd.ResourceId(tex_id)
    ctrl._textures = [
        rd.TextureDescription(resourceId=rid, width=256, height=256, msSamp=ms_samp),
    ]
    ctrl._actions = [
        rd.ActionDescription(eventId=100, flags=rd.ActionFlags.Drawcall, _name="vkCmdDraw"),
    ]
    if min_max is not None:
        ctrl._min_max_map[tex_id] = min_max
    if histogram is not None:
        ctrl._histogram_map.update(histogram)

    state = DaemonState(capture="test.rdc", current_eid=100, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 100
    state.rd = rd
    state.tex_map = {int(t.resourceId): t for t in ctrl._textures}
    return state


def _req(params: dict[str, Any] | None = None) -> dict[str, Any]:
    p: dict[str, Any] = {"_token": "tok"}
    if params:
        p.update(params)
    return {"jsonrpc": "2.0", "id": 1, "method": "tex_stats", "params": p}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_tex_stats_happy_minmax() -> None:
    mn = rd.PixelValue(floatValue=[0.0, 0.1, 0.2, 1.0])
    mx = rd.PixelValue(floatValue=[1.0, 0.9, 0.8, 1.0])
    state = _make_state(min_max=(mn, mx))
    resp, running = _handle_request(_req({"id": 42}), state)
    assert running
    r = resp["result"]
    assert r["id"] == 42
    assert r["min"] == {"r": 0.0, "g": 0.1, "b": 0.2, "a": 1.0}
    assert r["max"] == {"r": 1.0, "g": 0.9, "b": 0.8, "a": 1.0}


def test_tex_stats_minmax_values() -> None:
    mn = rd.PixelValue(floatValue=[0.25, 0.5, 0.75, 0.0])
    mx = rd.PixelValue(floatValue=[0.75, 1.0, 1.0, 1.0])
    state = _make_state(min_max=(mn, mx))
    resp, _ = _handle_request(_req({"id": 42}), state)
    r = resp["result"]
    assert r["min"]["r"] == 0.25
    assert r["max"]["g"] == 1.0


def test_tex_stats_no_histogram_by_default() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req({"id": 42}), state)
    assert "histogram" not in resp["result"]


def test_tex_stats_histogram_present() -> None:
    mn = rd.PixelValue(floatValue=[0.0, 0.0, 0.0, 0.0])
    mx = rd.PixelValue(floatValue=[1.0, 1.0, 1.0, 1.0])
    hist = {(42, i): list(range(256)) for i in range(4)}
    state = _make_state(min_max=(mn, mx), histogram=hist)
    resp, _ = _handle_request(_req({"id": 42, "histogram": True}), state)
    r = resp["result"]
    assert "histogram" in r
    assert len(r["histogram"]) == 256


def test_tex_stats_histogram_values() -> None:
    mn = rd.PixelValue(floatValue=[0.0, 0.0, 0.0, 0.0])
    mx = rd.PixelValue(floatValue=[1.0, 1.0, 1.0, 1.0])
    hist = {(42, i): list(range(256)) for i in range(4)}
    state = _make_state(min_max=(mn, mx), histogram=hist)
    resp, _ = _handle_request(_req({"id": 42, "histogram": True}), state)
    entry = resp["result"]["histogram"][0]
    assert set(entry.keys()) == {"bucket", "r", "g", "b", "a"}
    assert entry["bucket"] == 0


def test_tex_stats_mip_slice_forwarded() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req({"id": 42, "mip": 2, "slice": 3}), state)
    r = resp["result"]
    assert r["mip"] == 2
    assert r["slice"] == 3


def test_tex_stats_eid_navigation() -> None:
    state = _make_state()
    state._eid_cache = -1
    resp, _ = _handle_request(_req({"id": 42, "eid": 100}), state)
    ctrl = state.adapter.controller  # type: ignore[union-attr]
    assert (100, True) in ctrl._set_frame_event_calls
    assert resp["result"]["eid"] == 100


def test_tex_stats_default_eid() -> None:
    state = _make_state()
    state.current_eid = 100
    resp, _ = _handle_request(_req({"id": 42}), state)
    assert resp["result"]["eid"] == 100


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_tex_stats_no_adapter() -> None:
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req({"id": 42}), state)
    assert resp["error"]["code"] == -32002


def test_tex_stats_no_rd() -> None:
    state = _make_state()
    state.rd = None
    resp, _ = _handle_request(_req({"id": 42}), state)
    assert resp["error"]["code"] == -32002


def test_tex_stats_unknown_id() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req({"id": 999}), state)
    assert resp["error"]["code"] == -32001
    assert "999" in resp["error"]["message"]


def test_tex_stats_msaa_rejected() -> None:
    state = _make_state(ms_samp=4)
    resp, _ = _handle_request(_req({"id": 42}), state)
    assert resp["error"]["code"] == -32001
    assert "MSAA" in resp["error"]["message"]


def test_tex_stats_eid_out_of_range() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req({"id": 42, "eid": 9999}), state)
    assert resp["error"]["code"] == -32002


# ---------------------------------------------------------------------------
# Mock GetMinMax / GetHistogram
# ---------------------------------------------------------------------------


def test_mock_get_minmax_default() -> None:
    ctrl = rd.MockReplayController()
    mn, mx = ctrl.GetMinMax(rd.ResourceId(999), rd.Subresource(), rd.CompType.Typeless)
    assert mn.floatValue == [0.0, 0.0, 0.0, 0.0]
    assert mx.floatValue == [0.0, 0.0, 0.0, 0.0]


def test_mock_get_minmax_configured() -> None:
    ctrl = rd.MockReplayController()
    expected_min = rd.PixelValue(floatValue=[0.1, 0.2, 0.3, 0.4])
    expected_max = rd.PixelValue(floatValue=[0.5, 0.6, 0.7, 0.8])
    ctrl._min_max_map[42] = (expected_min, expected_max)
    mn, mx = ctrl.GetMinMax(rd.ResourceId(42), rd.Subresource(), rd.CompType.Typeless)
    assert mn.floatValue == [0.1, 0.2, 0.3, 0.4]
    assert mx.floatValue == [0.5, 0.6, 0.7, 0.8]


def test_mock_get_histogram_default() -> None:
    ctrl = rd.MockReplayController()
    ch_mask = [True, False, False, False]
    result = ctrl.GetHistogram(
        rd.ResourceId(999), rd.Subresource(), rd.CompType.Typeless, 0.0, 1.0, ch_mask
    )
    assert len(result) == 256
    assert all(v == 0 for v in result)


def test_mock_get_histogram_configured() -> None:
    ctrl = rd.MockReplayController()
    expected = list(range(256))
    ctrl._histogram_map[(42, 0)] = expected
    ch_mask = [True, False, False, False]
    result = ctrl.GetHistogram(
        rd.ResourceId(42), rd.Subresource(), rd.CompType.Typeless, 0.0, 1.0, ch_mask
    )
    assert result == expected
