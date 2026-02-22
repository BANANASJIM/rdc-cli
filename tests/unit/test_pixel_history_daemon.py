"""Tests for daemon pixel_history handler."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd  # noqa: E402


def _make_pixel_value(r: float, g: float, b: float, a: float) -> rd.PixelValue:
    return rd.PixelValue(floatValue=[r, g, b, a])


def _make_mod_val(
    r: float = 0.0, g: float = 0.0, b: float = 0.0, a: float = 1.0, depth: float = 0.5
) -> rd.ModificationValue:
    return rd.ModificationValue(col=_make_pixel_value(r, g, b, a), depth=depth)


def _make_state(
    pixel_history: dict[tuple[int, int], list[rd.PixelModification]] | None = None,
    output_targets: list[rd.Descriptor] | None = None,
    ms_samp: int = 1,
) -> DaemonState:
    ctrl = rd.MockReplayController()
    rt_rid = rd.ResourceId(42)
    rt_rid2 = rd.ResourceId(43)
    targets = output_targets or [rd.Descriptor(resource=rt_rid)]
    ctrl._pipe_state = rd.MockPipeState(output_targets=targets)
    ctrl._pixel_history_map = pixel_history or {}
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


def test_happy_path_mixed_pass_fail() -> None:
    mods = [
        rd.PixelModification(
            eventId=88,
            fragIndex=0,
            primitiveID=0,
            shaderOut=_make_mod_val(0.5, 0.3, 0.1, 1.0, depth=0.95),
            postMod=_make_mod_val(0.5, 0.3, 0.1, 1.0, depth=0.95),
        ),
        rd.PixelModification(
            eventId=102,
            fragIndex=0,
            primitiveID=1,
            shaderOut=_make_mod_val(0.2, 0.4, 0.6, 1.0, depth=0.82),
            postMod=_make_mod_val(0.2, 0.4, 0.6, 1.0, depth=0.82),
            depthTestFailed=True,
        ),
    ]
    state = _make_state(pixel_history={(512, 384): mods})
    resp, running = _handle_request(_req("pixel_history", {"x": 512, "y": 384}), state)
    assert running
    r = resp["result"]
    assert r["x"] == 512
    assert r["y"] == 384
    assert r["target"]["index"] == 0
    assert r["target"]["id"] == 42
    modifications = r["modifications"]
    assert len(modifications) == 2
    assert modifications[0]["eid"] == 88
    assert modifications[0]["passed"] is True
    assert modifications[0]["flags"] == []
    assert modifications[0]["shader_out"] == {"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0}
    assert modifications[0]["post_mod"] == {"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0}
    assert modifications[0]["depth"] == 0.95
    assert modifications[1]["eid"] == 102
    assert modifications[1]["passed"] is False
    assert "depthTestFailed" in modifications[1]["flags"]


def test_no_modifications() -> None:
    state = _make_state(pixel_history={(512, 384): []})
    resp, running = _handle_request(_req("pixel_history", {"x": 512, "y": 384}), state)
    assert running
    assert resp["result"]["modifications"] == []


def test_target_index_1() -> None:
    rt0 = rd.Descriptor(resource=rd.ResourceId(42))
    rt1 = rd.Descriptor(resource=rd.ResourceId(43))
    mods = [rd.PixelModification(eventId=88, postMod=_make_mod_val(depth=0.5))]
    state = _make_state(
        pixel_history={(100, 200): mods},
        output_targets=[rt0, rt1],
    )
    resp, running = _handle_request(_req("pixel_history", {"x": 100, "y": 200, "target": 1}), state)
    assert running
    r = resp["result"]
    assert r["target"]["index"] == 1
    assert r["target"]["id"] == 43


def test_eid_defaults_to_current() -> None:
    state = _make_state(pixel_history={(10, 20): []})
    state.current_eid = 120
    resp, running = _handle_request(_req("pixel_history", {"x": 10, "y": 20}), state)
    assert running
    assert resp["result"]["eid"] == 120


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_eid_out_of_range() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pixel_history", {"x": 0, "y": 0, "eid": 9999}), state)
    assert resp["error"]["code"] == -32002


def test_no_color_targets() -> None:
    state = _make_state(output_targets=[rd.Descriptor(resource=rd.ResourceId(0))])
    resp, _ = _handle_request(_req("pixel_history", {"x": 0, "y": 0}), state)
    assert resp["error"]["code"] == -32001
    assert "no color targets" in resp["error"]["message"]


def test_target_index_out_of_range() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("pixel_history", {"x": 0, "y": 0, "target": 5}), state)
    assert resp["error"]["code"] == -32001


def test_msaa_texture() -> None:
    state = _make_state(ms_samp=4)
    resp, _ = _handle_request(_req("pixel_history", {"x": 0, "y": 0}), state)
    assert resp["error"]["code"] == -32001
    assert "MSAA" in resp["error"]["message"]


def test_no_adapter() -> None:
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("pixel_history", {"x": 0, "y": 0}), state)
    assert resp["error"]["code"] == -32002


# ---------------------------------------------------------------------------
# Depth serialization
# ---------------------------------------------------------------------------


def test_depth_negative_one_is_null() -> None:
    mods = [rd.PixelModification(eventId=88, postMod=_make_mod_val(depth=-1.0))]
    state = _make_state(pixel_history={(0, 0): mods})
    resp, _ = _handle_request(_req("pixel_history", {"x": 0, "y": 0}), state)
    assert resp["result"]["modifications"][0]["depth"] is None


def test_depth_inf_is_null() -> None:
    mods = [rd.PixelModification(eventId=88, postMod=_make_mod_val(depth=math.inf))]
    state = _make_state(pixel_history={(0, 0): mods})
    resp, _ = _handle_request(_req("pixel_history", {"x": 0, "y": 0}), state)
    assert resp["result"]["modifications"][0]["depth"] is None


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------


def test_single_flag() -> None:
    mods = [
        rd.PixelModification(eventId=88, depthTestFailed=True, postMod=_make_mod_val(depth=0.5)),
    ]
    state = _make_state(pixel_history={(0, 0): mods})
    resp, _ = _handle_request(_req("pixel_history", {"x": 0, "y": 0}), state)
    m = resp["result"]["modifications"][0]
    assert m["flags"] == ["depthTestFailed"]
    assert m["passed"] is False


def test_multiple_flags() -> None:
    mods = [
        rd.PixelModification(
            eventId=88,
            scissorClipped=True,
            stencilTestFailed=True,
            postMod=_make_mod_val(depth=0.5),
        ),
    ]
    state = _make_state(pixel_history={(0, 0): mods})
    resp, _ = _handle_request(_req("pixel_history", {"x": 0, "y": 0}), state)
    flags = resp["result"]["modifications"][0]["flags"]
    assert "scissorClipped" in flags
    assert "stencilTestFailed" in flags


# ---------------------------------------------------------------------------
# SetFrameEvent called with force=True
# ---------------------------------------------------------------------------


def test_set_frame_event_called_with_force() -> None:
    state = _make_state(pixel_history={(0, 0): []})
    state._eid_cache = -1
    _handle_request(_req("pixel_history", {"x": 0, "y": 0, "eid": 120}), state)
    ctrl = state.adapter.controller  # type: ignore[union-attr]
    assert (120, True) in ctrl._set_frame_event_calls
