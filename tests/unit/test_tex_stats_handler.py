"""Tests for daemon tex_stats / tex_export / rt_export / rt_depth handlers."""

from __future__ import annotations

import io
import struct
from pathlib import Path

import mock_renderdoc as rd
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


def _make_texture3d_state() -> DaemonState:
    ctrl = rd.MockReplayController()
    tex = rd.TextureDescription(
        resourceId=rd.ResourceId(42),
        type=rd.TextureType.Texture3D,
        dimension=3,
        width=64,
        height=64,
        depth=4,
        mips=7,
        arraysize=1,
    )
    ctrl._textures = [tex]
    ctrl._actions = [
        rd.ActionDescription(eventId=100, flags=rd.ActionFlags.Drawcall, _name="vkCmdDraw"),
    ]
    return make_daemon_state(
        ctrl=ctrl,
        current_eid=100,
        rd=rd,
        tex_map={42: tex},
    )


def test_tex_stats_texture3d_accepts_depth_slices_for_requested_mip() -> None:
    state = _make_texture3d_state()

    for mip, array_slice in ((0, 3), (1, 1), (2, 0)):
        resp, _ = _handle_request(
            rpc_request("tex_stats", {"id": 42, "mip": mip, "slice": array_slice}), state
        )
        assert resp["result"]["mip"] == mip
        assert resp["result"]["slice"] == array_slice


def test_tex_stats_texture3d_rejects_slice_after_mip_depth_reduction() -> None:
    state = _make_texture3d_state()

    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "mip": 1, "slice": 2}), state)
    assert resp["error"]["code"] == -32001
    assert resp["error"]["message"] == "slice 2 out of range (max: 1)"

    resp, _ = _handle_request(rpc_request("tex_stats", {"id": 42, "mip": 2, "slice": 1}), state)
    assert resp["error"]["message"] == "slice 1 out of range (max: 0)"


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
# Remote-mode export through RenderDoc SaveTexture (#236)
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


def test_tex_export_remote_uses_savetexture_for_requested_3d_subresource(tmp_path: object) -> None:
    """Remote PNG export must use RenderDoc's local SaveTexture path, like qrenderdoc."""
    fmt = rd.ResourceFormat(name="ASTC6x6_UNORM", type=99)
    tex = rd.TextureDescription(
        resourceId=rd.ResourceId(196),
        type=rd.TextureType.Texture3D,
        width=64,
        height=64,
        depth=4,
        mips=2,
        format=fmt,
    )
    state = _remote_state(tex, b"", tmp_path)
    controller = state.adapter.controller  # type: ignore[union-attr]
    save_calls: list[tuple[int, int, str]] = []

    def _no_raw_fetch(resource_id: object, sub: object) -> bytes:
        del resource_id, sub
        raise AssertionError("remote PNG export must not call GetTextureData")

    def _save(texsave: object, path: str) -> object:
        save_calls.append((texsave.mip, texsave.slice.sliceIndex, path))
        assert texsave.destType == rd.FileType.PNG
        Path(path).write_bytes(b"renderdoc-png")

        class _Result:
            def OK(self) -> bool:  # noqa: N802
                return True

        return _Result()

    controller.GetTextureData = _no_raw_fetch  # type: ignore[method-assign]
    controller.SaveTexture = _save  # type: ignore[method-assign]

    resp, running = _handle_request(
        rpc_request("tex_export", {"id": 196, "mip": 1, "slice": 1}), state
    )

    assert running
    assert "result" in resp
    assert save_calls == [(1, 1, resp["result"]["path"])]


def test_tex_export_remote_reports_savetexture_failure(tmp_path: object) -> None:
    tex = rd.TextureDescription(resourceId=rd.ResourceId(198), width=2, height=2)
    state = _remote_state(tex, b"", tmp_path)
    controller = state.adapter.controller  # type: ignore[union-attr]

    def _no_raw_fetch(resource_id: object, sub: object) -> bytes:
        del resource_id, sub
        raise AssertionError("remote PNG export must not call GetTextureData")

    class _Failure:
        def OK(self) -> bool:  # noqa: N802
            return False

        def Message(self) -> str:  # noqa: N802
            return "mock encoder rejected texture"

    controller.GetTextureData = _no_raw_fetch  # type: ignore[method-assign]
    controller.SaveTexture = lambda texsave, path: _Failure()  # type: ignore[method-assign]

    resp, running = _handle_request(rpc_request("tex_export", {"id": 198}), state)

    assert running
    assert resp["error"] == {"code": -32002, "message": "mock encoder rejected texture"}


def test_tex_export_remote_requires_savetexture_output_file(tmp_path: object) -> None:
    tex = rd.TextureDescription(resourceId=rd.ResourceId(199), width=2, height=2)
    state = _remote_state(tex, b"", tmp_path)
    controller = state.adapter.controller  # type: ignore[union-attr]
    controller.SaveTexture = lambda texsave, path: True  # type: ignore[method-assign]

    resp, running = _handle_request(rpc_request("tex_export", {"id": 199}), state)

    assert running
    assert resp["error"] == {
        "code": -32002,
        "message": "SaveTexture did not create an output file",
    }


def test_rt_export_remote_uses_savetexture_without_raw_decode(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R16G16B16A16_FLOAT", compByteWidth=2, compCount=4, compType=1)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(197), width=2, height=2, format=fmt)
    state = _remote_state(
        tex,
        b"",
        tmp_path,
        output_targets=[rd.Descriptor(resource=tex.resourceId)],
    )
    controller = state.adapter.controller  # type: ignore[union-attr]
    save_calls: list[tuple[int, int]] = []

    def _no_raw_fetch(resource_id: object, sub: object) -> bytes:
        del resource_id, sub
        raise AssertionError("remote PNG export must not call GetTextureData")

    def _save(texsave: object, path: str) -> bool:
        save_calls.append((texsave.mip, texsave.slice.sliceIndex))
        Path(path).write_bytes(b"renderdoc-png")
        return True

    controller.GetTextureData = _no_raw_fetch  # type: ignore[method-assign]
    controller.SaveTexture = _save  # type: ignore[method-assign]

    resp, running = _handle_request(rpc_request("rt_export", {"eid": 100}), state)

    assert running
    assert "result" in resp
    assert save_calls == [(0, 0)]


# ---------------------------------------------------------------------------
# Local-mode rt_depth: unified GetTextureData decode + SaveTexture fallback
# ---------------------------------------------------------------------------


def _local_depth_state(
    tex: rd.TextureDescription,
    raw: bytes,
    tmp_path: object,
    *,
    save_texture: object = None,
) -> DaemonState:
    ctrl = rd.MockReplayController()
    ctrl._textures = [tex]
    ctrl._texture_data[int(tex.resourceId)] = raw
    ctrl._pipe_state = rd.MockPipeState(depth_target=rd.Descriptor(resource=tex.resourceId))
    if save_texture is not None:
        ctrl.SaveTexture = save_texture  # type: ignore[method-assign]
    return make_daemon_state(
        ctrl=ctrl,
        current_eid=100,
        rd=rd,
        tmp_path=tmp_path,
        tex_map={int(tex.resourceId): tex},
        is_remote=False,
    )


def test_rt_depth_local_calls_gettexturedata(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="D32_FLOAT", compByteWidth=4, compCount=1, compType=8)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(305), width=2, height=2, format=fmt)
    raw = struct.pack("<4f", 0.0, 0.25, 0.75, 1.0)

    def _no_save(texsave: object, path: str) -> bool:
        raise AssertionError("SaveTexture must not be called for decodable depth")

    state = _local_depth_state(tex, raw, tmp_path, save_texture=_no_save)
    resp, _ = _handle_request(rpc_request("rt_depth", {"eid": 100}), state)
    assert "result" in resp
    img = _read_png(resp["result"]["path"])
    assert img.mode == "L"
    assert img.getpixel((0, 0)) == 0
    assert img.getpixel((1, 1)) == 255


def test_rt_depth_local_produces_grayscale_L(tmp_path: object) -> None:  # noqa: N802
    fmt = rd.ResourceFormat(name="D16", compByteWidth=2, compCount=1, compType=8)
    tex = rd.TextureDescription(resourceId=rd.ResourceId(306), width=2, height=2, format=fmt)
    raw = struct.pack("<4H", 0, 16384, 49152, 65535)
    state = _local_depth_state(tex, raw, tmp_path)
    resp, _ = _handle_request(rpc_request("rt_depth", {"eid": 100}), state)
    img = _read_png(resp["result"]["path"])
    assert img.mode == "L"
    assert img.getpixel((0, 0)) == 0
    assert img.getpixel((1, 1)) == 255


def test_rt_depth_local_d24s8_fallback_uses_savetexture(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(
        name="D24S8",
        compByteWidth=4,
        compCount=1,
        compType=8,
        type=int(rd.ResourceFormatType.D24S8),
    )
    tex = rd.TextureDescription(resourceId=rd.ResourceId(307), width=2, height=2, format=fmt)
    save_calls: list[str] = []

    def _spy(texsave: object, path: str) -> bool:
        save_calls.append(path)
        from pathlib import Path

        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        return True

    state = _local_depth_state(tex, b"\x00" * 8, tmp_path, save_texture=_spy)
    resp, _ = _handle_request(rpc_request("rt_depth", {"eid": 100}), state)
    assert "result" in resp
    assert len(save_calls) == 1


def test_tex_export_texture3d_rejects_invalid_slice_for_mip(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R8G8B8A8_UNORM", compByteWidth=1, compCount=4, compType=2)
    tex = rd.TextureDescription(
        resourceId=rd.ResourceId(171),
        type=rd.TextureType.Texture3D,
        width=2,
        height=2,
        depth=4,
        mips=2,
        format=fmt,
    )
    state = _remote_state(tex, bytes(16), tmp_path)
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 171, "mip": 1, "slice": 2}), state)
    assert resp["error"]["code"] == -32001
    assert resp["error"]["message"] == "slice 2 out of range (max: 1)"


def test_rt_overlay_remote_still_rejected() -> None:
    state = make_daemon_state(is_remote=True, rd=rd)
    resp, _ = _handle_request(rpc_request("rt_overlay", {"overlay": "wireframe"}), state)
    assert resp["error"]["code"] == -32002
    assert "remote mode" in resp["error"]["message"]


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


def test_tex_export_local_texture3d_sets_requested_slice(tmp_path: object) -> None:
    fmt = rd.ResourceFormat(name="R8G8B8A8_UNORM", compByteWidth=1, compCount=4, compType=2)
    tex = rd.TextureDescription(
        resourceId=rd.ResourceId(172),
        type=rd.TextureType.Texture3D,
        width=2,
        height=2,
        depth=2,
        format=fmt,
    )
    ctrl = rd.MockReplayController()
    ctrl._textures = [tex]
    ctrl._actions = [
        rd.ActionDescription(eventId=100, flags=rd.ActionFlags.Drawcall, _name="vkCmdDraw"),
    ]
    slice_indices: list[int] = []
    orig_save = ctrl.SaveTexture

    def _spy(texsave: object, path: str) -> bool:
        slice_indices.append(texsave.slice.sliceIndex)
        return orig_save(texsave, path)

    ctrl.SaveTexture = _spy  # type: ignore[method-assign]
    state = make_daemon_state(
        ctrl=ctrl,
        current_eid=100,
        rd=rd,
        tmp_path=tmp_path,
        tex_map={172: tex},
        is_remote=False,
    )
    resp, _ = _handle_request(rpc_request("tex_export", {"id": 172, "slice": 1}), state)
    assert "result" in resp

    resp0, _ = _handle_request(rpc_request("tex_export", {"id": 172, "slice": 0}), state)
    assert "result" in resp0

    assert slice_indices == [1, 0]
