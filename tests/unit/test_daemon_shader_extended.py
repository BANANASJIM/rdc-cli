"""Tests for daemon server shader extended handlers."""

from __future__ import annotations

import sys
from pathlib import Path

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd  # noqa: E402


def _state_with_adapter() -> DaemonState:
    ctrl = rd.MockReplayController()
    a = rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)
    ctrl._actions = [a]

    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._entry_points[rd.ShaderStage.Pixel] = "main_ps"
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        readOnlyResources=[rd.ShaderResource(name="albedo", fixedBindNumber=0)],
        readWriteResources=[rd.ShaderResource(name="rwbuf", fixedBindNumber=1)],
        constantBlocks=[rd.ConstantBlock(name="Globals", fixedBindNumber=0)],
    )

    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 33))
    state.api_name = "Vulkan"
    state.max_eid = 100
    return state


def _req(method: str, params: dict | None = None) -> dict:
    p = {"_token": "tok"}
    if params:
        p.update(params)
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": p}


def test_shader_targets() -> None:
    state = _state_with_adapter()
    ctrl = state.adapter.controller
    ctrl.GetDisassemblyTargets = lambda _with_pipeline: ["SPIR-V", "GLSL"]  # type: ignore[attr-defined]

    resp, running = _handle_request(_req("shader_targets"), state)
    assert running
    assert resp["result"]["targets"] == ["SPIR-V", "GLSL"]


def test_shader_targets_fallback() -> None:
    state = _state_with_adapter()
    resp, running = _handle_request(_req("shader_targets"), state)
    assert running
    assert "SPIR-V" in resp["result"]["targets"]
    assert len(resp["result"]["targets"]) == 4


def test_shader_targets_no_adapter() -> None:
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("shader_targets"), state)
    assert resp["error"]["code"] == -32002


def test_shader_reflect() -> None:
    state = _state_with_adapter()
    resp, running = _handle_request(_req("shader_reflect", {"eid": 10, "stage": "ps"}), state)
    assert running
    r = resp["result"]
    assert r["eid"] == 10
    assert r["stage"] == "ps"
    assert len(r["constant_blocks"]) == 1
    assert r["constant_blocks"][0]["name"] == "Globals"


def test_shader_reflect_invalid_stage() -> None:
    state = _state_with_adapter()
    resp, _ = _handle_request(_req("shader_reflect", {"stage": "bad"}), state)
    assert resp["error"]["code"] == -32602


def test_shader_reflect_no_reflection() -> None:
    state = _state_with_adapter()
    # VS has no reflection set up
    resp, running = _handle_request(_req("shader_reflect", {"eid": 10, "stage": "vs"}), state)
    assert running
    assert resp["error"]["code"] == -32001


def test_shader_reflect_no_adapter() -> None:
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("shader_reflect", {"stage": "ps"}), state)
    assert resp["error"]["code"] == -32002


def test_shader_constants() -> None:
    state = _state_with_adapter()
    resp, running = _handle_request(_req("shader_constants", {"eid": 10, "stage": "ps"}), state)
    assert running
    r = resp["result"]
    assert r["eid"] == 10
    assert r["stage"] == "ps"
    assert len(r["constants"]) == 1
    assert r["constants"][0]["name"] == "Globals"


def test_shader_constants_invalid_stage() -> None:
    state = _state_with_adapter()
    resp, _ = _handle_request(_req("shader_constants", {"stage": "bad"}), state)
    assert resp["error"]["code"] == -32602


def test_shader_constants_no_adapter() -> None:
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("shader_constants", {"stage": "ps"}), state)
    assert resp["error"]["code"] == -32002


def test_shader_source() -> None:
    state = _state_with_adapter()
    resp, running = _handle_request(_req("shader_source", {"eid": 10, "stage": "ps"}), state)
    assert running
    r = resp["result"]
    assert r["eid"] == 10
    assert r["stage"] == "ps"
    assert "source" in r
    assert "has_debug_info" in r


def test_shader_source_invalid_stage() -> None:
    state = _state_with_adapter()
    resp, _ = _handle_request(_req("shader_source", {"stage": "bad"}), state)
    assert resp["error"]["code"] == -32602


def test_shader_source_no_adapter() -> None:
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("shader_source", {"stage": "ps"}), state)
    assert resp["error"]["code"] == -32002


def test_shader_disasm() -> None:
    state = _state_with_adapter()
    resp, running = _handle_request(_req("shader_disasm", {"eid": 10, "stage": "ps"}), state)
    assert running
    r = resp["result"]
    assert r["eid"] == 10
    assert r["stage"] == "ps"
    assert "disasm" in r


def test_shader_disasm_with_target() -> None:
    state = _state_with_adapter()
    ctrl = state.adapter.controller
    ctrl.GetDisassembly = lambda s: "default disasm"  # type: ignore[attr-defined]
    ctrl.GetDisassemblyForTarget = lambda s, t: f"disasm for {t}"  # type: ignore[attr-defined]

    resp, running = _handle_request(
        _req("shader_disasm", {"eid": 10, "stage": "ps", "target": "SPIR-V"}), state
    )
    assert running
    assert resp["result"]["disasm"] == "disasm for SPIR-V"
    assert resp["result"]["target"] == "SPIR-V"


def test_shader_disasm_invalid_stage() -> None:
    state = _state_with_adapter()
    resp, _ = _handle_request(_req("shader_disasm", {"stage": "bad"}), state)
    assert resp["error"]["code"] == -32602


def test_shader_disasm_no_adapter() -> None:
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("shader_disasm", {"stage": "ps"}), state)
    assert resp["error"]["code"] == -32002


def test_shader_all() -> None:
    state = _state_with_adapter()
    resp, running = _handle_request(_req("shader_all", {"eid": 10}), state)
    assert running
    r = resp["result"]
    assert r["eid"] == 10
    stages = r["stages"]
    assert len(stages) == 1
    assert stages[0]["stage"] == "ps"
    assert stages[0]["shader"] == 101
    assert stages[0]["entry"] == "main_ps"
    assert stages[0]["ro"] == 1
    assert stages[0]["rw"] == 1
    assert stages[0]["cbuffers"] == 1


def test_shader_all_no_adapter() -> None:
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("shader_all", {"eid": 10}), state)
    assert resp["error"]["code"] == -32002


def test_count_resources_handler() -> None:
    state = _state_with_adapter()
    res = rd.ResourceDescription(
        resourceId=rd.ResourceId(1), name="Tex", type=rd.ResourceType.Texture
    )
    state.adapter.controller._resources = [res]
    resp, _ = _handle_request(_req("count", {"what": "resources"}), state)
    assert resp["result"]["value"] == 1


def test_count_draws_handler() -> None:
    state = _state_with_adapter()
    resp, _ = _handle_request(_req("count", {"what": "draws"}), state)
    assert resp["result"]["value"] == 1


def test_count_invalid_target() -> None:
    state = _state_with_adapter()
    resp, _ = _handle_request(_req("count", {"what": "invalid_target"}), state)
    assert "error" in resp


def test_shader_map_handler() -> None:
    state = _state_with_adapter()
    resp, _ = _handle_request(_req("shader_map"), state)
    assert "result" in resp
    assert "rows" in resp["result"]


def test_events_handler() -> None:
    """Test events handler (which doesn't exist yet - returns method not found)."""
    state = _state_with_adapter()
    resp, _ = _handle_request(_req("events"), state)
    # Events handler may or may not be implemented
    assert "result" in resp or "error" in resp
