"""Tests for daemon tex_stats handler."""

from __future__ import annotations

import mock_renderdoc as rd
from conftest import make_daemon_state, rpc_request

from rdc.daemon_server import DaemonState, _handle_request


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

    state = make_daemon_state(
        ctrl=ctrl,
        current_eid=100,
        rd=rd,
        tex_map={int(t.resourceId): t for t in ctrl._textures},
    )
    return state


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_tex_stats_happy_minmax() -> None:
    mn = rd.PixelValue(floatValue=[0.0, 0.1, 0.2, 1.0])
    mx = rd.PixelValue(floatValue=[1.0, 0.9, 0.8, 1.0])
    state = _make_state(min_max=(mn, mx))
    resp, running = _handle_request(rpc_request("tex_stats", {"id": 42}), state)
    assert running
    r = resp["result"]
    assert r["id"] == 42
    assert r["min"] == {"r": 0.0, "g": 0.1, "b": 0.2, "a": 1.0}
    assert r["max"] == {"r": 1.0, "g": 0.9, "b": 0.8, "a": 1.0}


def test_tex_stats_minmax_values() -> None:
    mn = rd.PixelValue(floatValue=[0.25, 0.5, 0.75, 0.0])
    mx = rd.PixelValue(floatValue=[0.75, 1.0, 1.0, 1.0])
    state = _make_state(min_max=(mn, mx))
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42}), state)
    r = resp["result"]
    assert r["min"]["r"] == 0.25
    assert r["max"]["g"] == 1.0


def test_tex_stats_no_histogram_by_default() -> None:
    state = _make_state()
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42}), state)
    assert "histogram" not in resp["result"]


def test_tex_stats_histogram_present() -> None:
    mn = rd.PixelValue(floatValue=[0.0, 0.0, 0.0, 0.0])
    mx = rd.PixelValue(floatValue=[1.0, 1.0, 1.0, 1.0])
    hist = {(42, i): list(range(256)) for i in range(4)}
    state = _make_state(min_max=(mn, mx), histogram=hist)
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "histogram": True}), state)
    r = resp["result"]
    assert "histogram" in r
    assert len(r["histogram"]) == 256


def test_tex_stats_histogram_values() -> None:
    mn = rd.PixelValue(floatValue=[0.0, 0.0, 0.0, 0.0])
    mx = rd.PixelValue(floatValue=[1.0, 1.0, 1.0, 1.0])
    hist = {(42, i): list(range(256)) for i in range(4)}
    state = _make_state(min_max=(mn, mx), histogram=hist)
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "histogram": True}), state)
    entry = resp["result"]["histogram"][0]
    assert set(entry.keys()) == {"bucket", "r", "g", "b", "a"}
    assert entry["bucket"] == 0


def test_tex_stats_mip_slice_forwarded() -> None:
    ctrl = rd.MockReplayController()
    rid = rd.ResourceId(42)
    ctrl._textures = [
        rd.TextureDescription(resourceId=rid, width=256, height=256, mips=4, arraysize=4),
    ]
    ctrl._actions = [
        rd.ActionDescription(eventId=100, flags=rd.ActionFlags.Drawcall, _name="vkCmdDraw"),
    ]
    state = make_daemon_state(
        ctrl=ctrl,
        current_eid=100,
        rd=rd,
        tex_map={int(t.resourceId): t for t in ctrl._textures},
    )
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "mip": 2, "slice": 3}), state)
    r = resp["result"]
    assert r["mip"] == 2
    assert r["slice"] == 3


def test_tex_stats_eid_navigation() -> None:
    state = _make_state()
    state._eid_cache = -1
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "eid": 100}), state)
    ctrl = state.adapter.controller  # type: ignore[union-attr]
    assert (100, True) in ctrl._set_frame_event_calls
    assert resp["result"]["eid"] == 100


def test_tex_stats_default_eid() -> None:
    state = _make_state()
    state.current_eid = 100
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42}), state)
    assert resp["result"]["eid"] == 100


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_tex_stats_no_adapter() -> None:
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42}), state)
    assert resp["error"]["code"] == -32002


def test_tex_stats_no_rd() -> None:
    state = _make_state()
    state.rd = None
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42}), state)
    assert resp["error"]["code"] == -32002


def test_tex_stats_unknown_id() -> None:
    state = _make_state()
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 999}), state)
    assert resp["error"]["code"] == -32001
    assert "999" in resp["error"]["message"]


def test_tex_stats_msaa_rejected() -> None:
    state = _make_state(ms_samp=4)
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42}), state)
    assert resp["error"]["code"] == -32001
    assert "MSAA" in resp["error"]["message"]


def test_tex_stats_eid_out_of_range() -> None:
    state = _make_state()
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "eid": 9999}), state)
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


# ---------------------------------------------------------------------------
# Mip/slice bounds validation
# ---------------------------------------------------------------------------


def test_tex_stats_mip_out_of_range() -> None:
    state = _make_state()
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "mip": 5}), state)
    assert resp["error"]["code"] == -32001
    assert "out of range" in resp["error"]["message"]


def test_tex_stats_mip_upper_boundary() -> None:
    ctrl = rd.MockReplayController()
    rid = rd.ResourceId(42)
    ctrl._textures = [
        rd.TextureDescription(resourceId=rid, width=256, height=256, mips=4),
    ]
    ctrl._actions = [
        rd.ActionDescription(eventId=100, flags=rd.ActionFlags.Drawcall, _name="vkCmdDraw"),
    ]
    state = make_daemon_state(
        ctrl=ctrl,
        current_eid=100,
        rd=rd,
        tex_map={int(t.resourceId): t for t in ctrl._textures},
    )
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "mip": 3}), state)
    assert "result" in resp
    assert resp["result"]["mip"] == 3


def test_tex_stats_slice_out_of_range() -> None:
    state = _make_state()
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "slice": 5}), state)
    assert resp["error"]["code"] == -32001
    assert "out of range" in resp["error"]["message"]


def test_tex_stats_negative_mip() -> None:
    state = _make_state()
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "mip": -1}), state)
    assert resp["error"]["code"] == -32001
    assert "out of range" in resp["error"]["message"]


def test_tex_stats_valid_mip0_slice0() -> None:
    state = _make_state()
    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "mip": 0, "slice": 0}), state)
    assert "result" in resp
    assert resp["result"]["mip"] == 0
    assert resp["result"]["slice"] == 0


# ---------------------------------------------------------------------------
# B54: histogram channel length mismatch guard
# ---------------------------------------------------------------------------


def test_tex_stats_histogram_channel_length_mismatch() -> None:
    """B54: extra buckets in later channels must not cause IndexError."""
    mn = rd.PixelValue(floatValue=[0.0, 0.0, 0.0, 0.0])
    mx = rd.PixelValue(floatValue=[1.0, 1.0, 1.0, 1.0])
    # ch0 returns 4 buckets (histogram list will have 4 entries),
    # ch1 returns 8 buckets (would overflow without the guard).
    hist = {
        (42, 0): [10, 20, 30, 40],
        (42, 1): [1, 2, 3, 4, 5, 6, 7, 8],
        (42, 2): [0] * 4,
        (42, 3): [0] * 4,
    }
    state = _make_state(min_max=(mn, mx), histogram=hist)
    resp, running = _handle_request(rpc_request("tex_stats", {"id": 42, "histogram": True}), state)
    assert running
    h = resp["result"]["histogram"]
    assert len(h) == 4
    # First 4 buckets should have ch1 data
    assert h[0]["g"] == 1
    assert h[3]["g"] == 4
