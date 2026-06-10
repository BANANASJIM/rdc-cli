"""Tests for daemon tex_stats / tex_export / rt_export / rt_depth handlers."""

from __future__ import annotations

import io
import struct

import mock_renderdoc as rd
import numpy as np
from conftest import make_daemon_state, rpc_request
from PIL import Image

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


# ---------------------------------------------------------------------------
# Remote-mode export via GetTextureData decode (#236)
# ---------------------------------------------------------------------------


def _remote_state(
    tex: rd.TextureDescription,
    raw: bytes,
    tmp_path: object,
    *,
    output_targets: list[rd.Descriptor] | None = None,
    depth_target: rd.Descriptor | None = None,
) -> DaemonState:
    ctrl = rd.MockReplayController()
    ctrl._textures = [tex]
    ctrl._texture_data[int(tex.resourceId)] = raw
    if output_targets is not None or depth_target is not None:
        ctrl._pipe_state = rd.MockPipeState(
            output_targets=output_targets, depth_target=depth_target
        )
    return make_daemon_state(
        ctrl=ctrl,
        current_eid=100,
        rd=rd,
        tmp_path=tmp_path,
        tex_map={int(tex.resourceId): tex},
        is_remote=True,
    )


def _read_png(path: str) -> Image.Image:
    with open(path, "rb") as fh:
        data = fh.read()
    assert data[:4] == b"\x89PNG"
    return Image.open(io.BytesIO(data))


def test_tex_export_remote_rgba8(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R8G8B8A8_UNORM", compByteWidth=1, compCount=4, compType=2)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(96), width=4, height=2, format=fmt)
    raw = bytes(range(4 * 2 * 4))
    state = _remote_state(tex, raw, tmp_path)
    resp, running = _handle_request(rpc_request("tex_export", {"id": 96}), state)
    assert running
    img = _read_png(resp["result"]["path"])
    assert img.size == (4, 2)
    assert img.mode == "RGBA"
    assert resp["result"]["size"] > 0


def test_tex_export_remote_bgra_swaps_channels(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="B8G8R8A8_UNORM", compByteWidth=1, compCount=4, compType=2)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(96), width=1, height=1, format=fmt)
    raw = bytes([10, 20, 30, 40])  # B,G,R,A
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 96}), state)
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0)) == (30, 20, 10, 40)


def test_tex_export_remote_r8_grayscale(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R8_UNORM", compByteWidth=1, compCount=1, compType=2)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(7), width=2, height=2, format=fmt)
    raw = bytes([10, 20, 30, 40])
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 7}), state)
    img = _read_png(resp["result"]["path"])
    assert img.size == (2, 2)
    assert img.getpixel((0, 0))[:3] == (10, 10, 10)


def test_tex_export_remote_float16_hdr(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R16G16B16A16_FLOAT", compByteWidth=2, compCount=4, compType=1)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(8), width=1, height=1, format=fmt)
    raw = np.array([2.0, 0.5, 0.0, 1.0], dtype=np.float16).tobytes()
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 8}), state)
    img = _read_png(resp["result"]["path"])
    px = img.getpixel((0, 0))
    assert px[0] == 255  # clipped + sRGB encode of 1.0
    assert px[3] == 255


def test_tex_export_remote_length_mismatch_errors(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R8G8B8A8_UNORM", compByteWidth=1, compCount=4, compType=2)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(96), width=4, height=4, format=fmt)
    state = _remote_state(tex, b"\x00\x01\x02\x03", tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 96}), state)
    assert resp["error"]["code"] == -32002


def test_tex_export_remote_special_format_rejected(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="BC1_UNORM", compByteWidth=0, compCount=4, compType=2, type=2)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(96), width=4, height=4, format=fmt)
    state = _remote_state(tex, b"\x00" * 8, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 96}), state)
    assert resp["error"]["code"] == -32002
    assert "not supported" in resp["error"]["message"]


def test_rt_export_remote_decodes_png(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="B8G8R8A8_SRGB", compByteWidth=1, compCount=4, compType=9)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(96), width=2, height=2, format=fmt)
    raw = bytes(range(2 * 2 * 4))
    targets = [rd.Descriptor(resource=rd.ResourceId(96))]
    state = _remote_state(tex, raw, tmp_path, output_targets=targets)
    resp, _ = _handle_request(rpc_request("rt_export", {"eid": 100}), state)
    img = _read_png(resp["result"]["path"])
    assert img.size == (2, 2)
    assert img.mode == "RGBA"


def test_rt_depth_remote_decodes_grayscale(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="D32_FLOAT", compByteWidth=4, compCount=1, compType=8)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(305), width=2, height=2, format=fmt)
    raw = struct.pack("<4f", 0.0, 0.25, 0.75, 1.0)
    depth = rd.Descriptor(resource=rd.ResourceId(305))
    state = _remote_state(tex, raw, tmp_path, depth_target=depth)
    resp, _ = _handle_request(rpc_request("rt_depth", {"eid": 100}), state)
    img = _read_png(resp["result"]["path"])
    assert img.size == (2, 2)
    assert img.mode == "L"
    assert img.getpixel((0, 0)) == 0
    assert img.getpixel((1, 1)) == 255
    # depth=0.25 over [0,1] range -> 0.25*255 = 63.75 -> 64; uint32 reinterpret gives ~251
    assert abs(img.getpixel((1, 0)) - 64) <= 2


def test_rt_depth_remote_d16_decodes_grayscale(tmp_path: object) -> None:
    # compType 8 = Depth; D16 is uint16, not float16
    fmt = rd.ResourceFormat(name="D16", compByteWidth=2, compCount=1, compType=8)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(306), width=2, height=2, format=fmt)
    raw = struct.pack("<4H", 0, 16384, 49152, 65535)  # uint16 depths
    depth = rd.Descriptor(resource=rd.ResourceId(306))
    state = _remote_state(tex, raw, tmp_path, depth_target=depth)
    resp, _ = _handle_request(rpc_request("rt_depth", {"eid": 100}), state)
    img = _read_png(resp["result"]["path"])
    assert img.size == (2, 2)
    assert img.mode == "L"
    assert img.getpixel((0, 0)) == 0
    assert img.getpixel((1, 1)) == 255
    # depth=16384 over [0,65535] -> 16384/65535*255 = 63.75 -> 64
    assert abs(img.getpixel((1, 0)) - 64) <= 2


def test_tex_export_remote_r16_unorm_scales_by_257(tmp_path: object) -> None:
    # R16 UNorm: 16-bit -> 8-bit via /257. 65535/257 = 255, 32896/257 = 128.
    fmt = rd.ResourceFormat(name="R16_UNORM", compByteWidth=2, compCount=1, compType=2)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(50), width=2, height=1, format=fmt)
    raw = struct.pack("<2H", 65535, 32896)
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 50}), state)
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0))[:3] == (255, 255, 255)
    assert img.getpixel((1, 0))[:3] == (128, 128, 128)


def test_tex_export_remote_rgba32f_hdr_clip(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R32G32B32A32_FLOAT", compByteWidth=4, compCount=4, compType=1)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(51), width=1, height=1, format=fmt)
    raw = np.array([5.0, 0.0, 0.0, 1.0], dtype=np.float32).tobytes()
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 51}), state)
    img = _read_png(resp["result"]["path"])
    px = img.getpixel((0, 0))
    assert px[0] == 255  # clipped to 1.0 -> sRGB -> 255
    assert px[1] == 0  # 0.0 -> 0
    assert px[3] == 255


def test_tex_export_remote_float_rgba_alpha_linear(tmp_path: object) -> None:
    # Float RGBA: RGB gets sRGB OETF, alpha stays LINEAR. alpha 0.5 -> ~128, not ~188.
    fmt = rd.ResourceFormat(name="R32G32B32A32_FLOAT", compByteWidth=4, compCount=4, compType=1)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(52), width=1, height=1, format=fmt)
    raw = np.array([1.0, 1.0, 1.0, 0.5], dtype=np.float32).tobytes()
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 52}), state)
    img = _read_png(resp["result"]["path"])
    px = img.getpixel((0, 0))
    assert px[:3] == (255, 255, 255)  # 1.0 -> sRGB -> 255
    assert abs(px[3] - 128) <= 2  # alpha linear 0.5 -> ~128
    assert px[3] < 180  # gamma-encoding would give ~188


def test_tex_export_remote_snorm_remaps_signed(tmp_path: object) -> None:
    # SNorm normal map: -1 -> 0, 0 -> ~128, +1 -> 255. Read as int8, not uint8.
    fmt = rd.ResourceFormat(name="R8G8B8A8_SNORM", compByteWidth=1, compCount=4, compType=3)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(52), width=1, height=1, format=fmt)
    raw = struct.pack("<4b", -127, 0, 127, 127)  # R=-1, G=0, B=+1, A=+1
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 52}), state)
    img = _read_png(resp["result"]["path"])
    px = img.getpixel((0, 0))
    assert px[0] == 0  # -1 -> 0
    assert abs(px[1] - 128) <= 1  # 0 -> ~128
    assert px[2] == 255  # +1 -> 255


def test_tex_export_remote_uint8_passthrough(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R8G8B8A8_UINT", compByteWidth=1, compCount=4, compType=4)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(53), width=1, height=1, format=fmt)
    raw = bytes([10, 20, 30, 40])
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 53}), state)
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0)) == (10, 20, 30, 40)


def test_tex_export_remote_sint_rejected(tmp_path: object) -> None:
    # SInt has no unambiguous display mapping -> clean reject.
    fmt = rd.ResourceFormat(name="R8G8B8A8_SINT", compByteWidth=1, compCount=4, compType=5)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(54), width=1, height=1, format=fmt)
    state = _remote_state(tex, bytes([1, 2, 3, 4]), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 54}), state)
    assert resp["error"]["code"] == -32002
    assert "not supported" in resp["error"]["message"]


def test_tex_export_remote_typeless_rejected(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R8G8B8A8_TYPELESS", compByteWidth=1, compCount=4, compType=0)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(55), width=1, height=1, format=fmt)
    state = _remote_state(tex, bytes([1, 2, 3, 4]), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 55}), state)
    assert resp["error"]["code"] == -32002


def test_tex_export_remote_uscaled_rejected(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R8G8B8A8_USCALED", compByteWidth=1, compCount=4, compType=6)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(56), width=1, height=1, format=fmt)
    state = _remote_state(tex, bytes([1, 2, 3, 4]), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 56}), state)
    assert resp["error"]["code"] == -32002


def test_tex_export_remote_unsupported_packed_format_rejected(tmp_path: object) -> None:
    # R5G6B5 (type=14) is a still-unsupported packed (non-Regular) format -> reject.
    # R11G11B10/R9G9B9E5 now decode, so this preserves rejection coverage for a
    # packed type the change does not handle.
    fmt = rd.ResourceFormat(name="R5G6B5_UNORM", compByteWidth=2, compCount=3, compType=2, type=14)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(57), width=1, height=1, format=fmt)
    state = _remote_state(tex, bytes(4), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 57}), state)
    assert resp["error"]["code"] == -32002
    assert "not supported" in resp["error"]["message"]


def test_tex_export_remote_msaa_rejected(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R8G8B8A8_UNORM", compByteWidth=1, compCount=4, compType=2)
    tex = rd.TextureDescription(
        resourceId=rd.ResourceId(58), width=1, height=1, format=fmt, msSamp=4
    )
    state = _remote_state(tex, bytes(4), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 58}), state)
    assert resp["error"]["code"] == -32002


def test_tex_export_remote_no_data_rejected(tmp_path: object) -> None:
    # GetTextureData returns empty -> clean -32002, no len(None) crash.
    fmt = rd.ResourceFormat(name="R8G8B8A8_UNORM", compByteWidth=1, compCount=4, compType=2)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(59), width=2, height=2, format=fmt)
    state = _remote_state(tex, b"", tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 59}), state)
    assert resp["error"]["code"] == -32002
    assert "no texture data" in resp["error"]["message"]


def test_tex_export_remote_3d_tiles_depth_slices(tmp_path: object) -> None:
    # 3D RGBA8 depth=2: GetTextureData returns the whole w*h*depth mip.
    # Slices are tiled vertically into one (depth*height, width) image.
    fmt = rd.ResourceFormat(name="R8G8B8A8_UNORM", compByteWidth=1, compCount=4, compType=2)
    tex = rd.TextureDescription(
        resourceId=rd.ResourceId(70), width=2, height=2, depth=2, format=fmt
    )
    raw = bytes(range(2 * 2 * 2 * 4))  # depth*height*width*cc
    state = _remote_state(tex, raw, tmp_path)
    resp, running = _handle_request(rpc_request("tex_export", {"id": 70}), state)
    assert running
    img = _read_png(resp["result"]["path"])
    assert img.size == (2, 4)  # width=2, height=depth*height=4
    assert img.mode == "RGBA"
    # First pixel of slice 0 and first pixel of slice 1 differ.
    assert img.getpixel((0, 0)) == (0, 1, 2, 3)
    assert img.getpixel((0, 2)) == (16, 17, 18, 19)


def test_tex_export_remote_float_nan_renders_black(tmp_path: object, recwarn: object) -> None:
    # NaN in a float HDR channel must render as 0 with no numpy RuntimeWarning.
    fmt = rd.ResourceFormat(name="R16G16B16A16_FLOAT", compByteWidth=2, compCount=4, compType=1)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(71), width=1, height=1, format=fmt)
    raw = np.array([np.nan, 0.5, 0.0, 1.0], dtype=np.float16).tobytes()
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 71}), state)
    img = _read_png(resp["result"]["path"])
    px = img.getpixel((0, 0))
    assert px[0] == 0  # NaN -> 0
    assert px[3] == 255
    assert not any(issubclass(w.category, RuntimeWarning) for w in recwarn)  # type: ignore[attr-defined]


def test_tex_export_remote_rg8_two_channel(tmp_path: object) -> None:
    # cc=2 R8G8_UNORM: B forced to 0, alpha forced to 255.
    fmt = rd.ResourceFormat(name="R8G8_UNORM", compByteWidth=1, compCount=2, compType=2)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(72), width=1, height=1, format=fmt)
    raw = bytes([90, 160])
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 72}), state)
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0)) == (90, 160, 0, 255)


def test_tex_export_remote_rgb8_three_channel_appends_alpha(tmp_path: object) -> None:
    # cc=3 R8G8B8_UNORM: opaque alpha appended.
    fmt = rd.ResourceFormat(name="R8G8B8_UNORM", compByteWidth=1, compCount=3, compType=2)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(73), width=1, height=1, format=fmt)
    raw = bytes([11, 22, 33])
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 73}), state)
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0)) == (11, 22, 33, 255)


def test_tex_export_remote_snorm16_remaps_signed(tmp_path: object) -> None:
    # cc=2 R16G16_SNORM: -32767 -> 0, 0 -> ~128, +32767 -> 255.
    fmt = rd.ResourceFormat(name="R16G16_SNORM", compByteWidth=2, compCount=2, compType=3)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(74), width=1, height=1, format=fmt)
    raw = struct.pack("<2h", -32767, 0)
    state = _remote_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 74}), state)
    img = _read_png(resp["result"]["path"])
    px = img.getpixel((0, 0))
    assert px[0] == 0  # -1 -> 0
    assert abs(px[1] - 128) <= 1  # 0 -> ~128
    assert px[2] == 0  # B forced to 0
    assert px[3] == 255


def test_rt_export_remote_srgb_bgra_pixel_values(tmp_path: object) -> None:
    # B8G8R8A8_SRGB (compType 9 = UNormSRGB): input bytes [B,G,R,A] -> RGBA.
    # UNormSRGB is a passthrough (already display-encoded); BGRA order swaps.
    fmt = rd.ResourceFormat(name="B8G8R8A8_SRGB", compByteWidth=1, compCount=4, compType=9)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(75), width=1, height=1, format=fmt)
    raw = bytes([10, 20, 30, 40])  # B=10, G=20, R=30, A=40
    targets = [rd.Descriptor(resource=rd.ResourceId(75))]
    state = _remote_state(tex, raw, tmp_path, output_targets=targets)
    resp, _ = _handle_request(rpc_request("rt_export", {"eid": 100}), state)
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0)) == (30, 20, 10, 40)


def test_rt_overlay_remote_still_rejected() -> None:
    state = make_daemon_state(is_remote=True, rd=rd)
    resp, _ = _handle_request(rpc_request("rt_overlay", {"overlay": "wireframe"}), state)
    assert resp["error"]["code"] == -32002
    assert "remote mode" in resp["error"]["message"]


# ---------------------------------------------------------------------------
# Packed HDR formats: R11G11B10_FLOAT (type=13) and R9G9B9E5_SHAREDEXP (type=16)
# ---------------------------------------------------------------------------


def _r11g11b10_tex(res_id: int, **kw: object) -> rd.TextureDescription:
    fmt = rd.ResourceFormat(
        name="R11G11B10_FLOAT", compByteWidth=4, compCount=3, compType=1, type=13
    )
    return rd.TextureDescription(resourceId=rd.ResourceId(res_id), format=fmt, **kw)  # type: ignore[arg-type]


def _r9g9b9e5_tex(res_id: int, **kw: object) -> rd.TextureDescription:
    fmt = rd.ResourceFormat(
        name="R9G9B9E5_SHAREDEXP", compByteWidth=4, compCount=3, compType=1, type=16
    )
    return rd.TextureDescription(resourceId=rd.ResourceId(res_id), format=fmt, **kw)  # type: ignore[arg-type]


def test_tex_export_remote_r11g11b10_happy_path(tmp_path: object) -> None:
    # (1.0, 0.5, 0.25): R exp=15 mant=0, G exp=14 mant=0, B exp=13 mant=0.
    tex = _r11g11b10_tex(110, width=1, height=1)
    state = _remote_state(tex, struct.pack("<I", 0x681C03C0), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 110}), state)
    img = _read_png(resp["result"]["path"])
    px = img.getpixel((0, 0))
    assert px[0] == 255  # sRGB(1.0)
    assert abs(px[1] - 188) <= 2  # sRGB(0.5)
    assert abs(px[2] - 137) <= 2  # sRGB(0.25)
    assert px[3] == 255


def test_tex_export_remote_r11g11b10_inf_clips_white(tmp_path: object) -> None:
    tex = _r11g11b10_tex(111, width=1, height=1)
    state = _remote_state(tex, struct.pack("<I", 0xF83E07C0), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 111}), state)
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0)) == (255, 255, 255, 255)


def test_tex_export_remote_r11g11b10_nan_renders_black(tmp_path: object) -> None:
    tex = _r11g11b10_tex(112, width=1, height=1)
    state = _remote_state(tex, struct.pack("<I", 0xF87E0FC1), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 112}), state)
    img = _read_png(resp["result"]["path"])
    px = img.getpixel((0, 0))
    assert px[:3] == (0, 0, 0)
    assert px[3] == 255


def test_tex_export_remote_r11g11b10_subnormal_tiny(tmp_path: object) -> None:
    # exp=0 mant=1 for all channels -> ~9.5e-7, sRGB rounds to 0, no error.
    tex = _r11g11b10_tex(113, width=1, height=1)
    state = _remote_state(tex, struct.pack("<I", 0x00400801), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 113}), state)
    assert "result" in resp
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0)) == (0, 0, 0, 255)


def test_tex_export_remote_r11g11b10_wrong_length_rejected(tmp_path: object) -> None:
    tex = _r11g11b10_tex(114, width=2, height=2)
    state = _remote_state(tex, b"\x00" * 4, tmp_path)  # should be 16 bytes
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 114}), state)
    assert resp["error"]["code"] == -32002


def test_tex_export_remote_r11g11b10_msaa_rejected(tmp_path: object) -> None:
    tex = _r11g11b10_tex(115, width=1, height=1, msSamp=4)
    state = _remote_state(tex, struct.pack("<I", 0x681C03C0), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 115}), state)
    assert resp["error"]["code"] == -32002


def test_tex_export_remote_r11g11b10_3d_tiled(tmp_path: object) -> None:
    tex = _r11g11b10_tex(116, width=1, height=1, depth=2)
    state = _remote_state(tex, struct.pack("<2I", 0x681C03C0, 0x00000000), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 116}), state)
    img = _read_png(resp["result"]["path"])
    assert img.size == (1, 2)
    px0 = img.getpixel((0, 0))
    assert px0[0] == 255
    assert abs(px0[1] - 188) <= 2
    assert abs(px0[2] - 137) <= 2
    assert img.getpixel((0, 1)) == (0, 0, 0, 255)


def test_tex_export_remote_r9g9b9e5_white(tmp_path: object) -> None:
    # E=24, mant=1 each -> 1.0 each channel.
    tex = _r9g9b9e5_tex(160, width=1, height=1)
    state = _remote_state(tex, struct.pack("<I", 0xC0040201), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 160}), state)
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0)) == (255, 255, 255, 255)


def test_tex_export_remote_r9g9b9e5_quarter(tmp_path: object) -> None:
    # E=22, rm=4 gm=2 bm=1 -> 1.0, 0.5, 0.25.
    tex = _r9g9b9e5_tex(161, width=1, height=1)
    state = _remote_state(tex, struct.pack("<I", 0xB0040404), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 161}), state)
    img = _read_png(resp["result"]["path"])
    px = img.getpixel((0, 0))
    assert px[0] == 255
    assert abs(px[1] - 188) <= 2
    assert abs(px[2] - 137) <= 2
    assert px[3] == 255


def test_tex_export_remote_r9g9b9e5_zero_black(tmp_path: object) -> None:
    tex = _r9g9b9e5_tex(162, width=1, height=1)
    state = _remote_state(tex, struct.pack("<I", 0x00000000), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 162}), state)
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0)) == (0, 0, 0, 255)


def test_tex_export_remote_r9g9b9e5_wrong_length_rejected(tmp_path: object) -> None:
    tex = _r9g9b9e5_tex(163, width=2, height=2)
    state = _remote_state(tex, b"\x00" * 4, tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 163}), state)
    assert resp["error"]["code"] == -32002


def test_tex_export_remote_r9g9b9e5_3d_tiled(tmp_path: object) -> None:
    tex = _r9g9b9e5_tex(164, width=1, height=1, depth=2)
    state = _remote_state(tex, struct.pack("<2I", 0xC0040201, 0x00000000), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 164}), state)
    img = _read_png(resp["result"]["path"])
    assert img.size == (1, 2)
    assert img.getpixel((0, 0)) == (255, 255, 255, 255)
    assert img.getpixel((0, 1)) == (0, 0, 0, 255)


def test_tex_export_remote_r9g9b9e5_max_exp_clips_white(tmp_path: object) -> None:
    # E=31, all mantissas=511 -> each channel = 65408.0 (finite), clips to white.
    tex = _r9g9b9e5_tex(165, width=1, height=1)
    state = _remote_state(tex, struct.pack("<I", 0xFFFFFFFF), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 165}), state)
    img = _read_png(resp["result"]["path"])
    assert img.getpixel((0, 0)) == (255, 255, 255, 255)


# ---------------------------------------------------------------------------
# Local mode still routes through SaveTexture (regression)
# ---------------------------------------------------------------------------


def test_tex_export_local_uses_savetexture(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R8G8B8A8_UNORM", compByteWidth=1, compCount=4, compType=2)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(42), width=4, height=4, format=fmt)
    ctrl = rd.MockReplayController()
    ctrl._textures = [tex]
    ctrl._actions = [
        rd.ActionDescription(eventId=100, flags=rd.ActionFlags.Drawcall, _name="vkCmdDraw"),
    ]
    save_calls: list[str] = []
    orig_save = ctrl.SaveTexture

    def _spy(texsave: object, path: str) -> bool:
        save_calls.append(path)
        return orig_save(texsave, path)

    ctrl.SaveTexture = _spy  # type: ignore[method-assign]
    state = make_daemon_state(
        ctrl=ctrl,
        current_eid=100,
        rd=rd,
        tmp_path=tmp_path,
        tex_map={42: tex},
        is_remote=False,
    )
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 42}), state)
    assert "result" in resp
    assert len(save_calls) == 1
