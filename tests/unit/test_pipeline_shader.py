from __future__ import annotations

import sys
from pathlib import Path

from click.testing import CliRunner

from rdc.cli import main
from rdc.daemon_server import DaemonState, _handle_request
from rdc.services.query_service import bindings_rows, pipeline_row, shader_inventory, shader_row

# Make mock module importable
sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd  # noqa: E402


def _state_with_adapter() -> DaemonState:
    ctrl = rd.MockReplayController()
    # one draw action
    a = rd.ActionDescription(eventId=10, flags=rd.ActionFlags.Drawcall)
    ctrl._actions = [a]
    # one shader + reflection on PS
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._entry_points[rd.ShaderStage.Pixel] = "main_ps"
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        readOnlyResources=[rd.ShaderResource(name="albedo", bindPoint=0)],
        readWriteResources=[rd.ShaderResource(name="rwbuf", bindPoint=1)],
        constantBlocks=[rd.ConstantBlock(name="Globals", bindPoint=0)],
    )

    from rdc.adapter import RenderDocAdapter

    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 33))
    state.api_name = "Vulkan"
    state.event_count = 100
    return state


def test_query_service_rows() -> None:
    ctrl = rd.MockReplayController()
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._entry_points[rd.ShaderStage.Pixel] = "main_ps"
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        readOnlyResources=[rd.ShaderResource(name="albedo", bindPoint=0)],
        readWriteResources=[rd.ShaderResource(name="rwbuf", bindPoint=1)],
        constantBlocks=[rd.ConstantBlock(name="Globals", bindPoint=0)],
    )

    prow = pipeline_row(10, "Vulkan", ctrl.GetPipelineState())
    assert prow["eid"] == 10
    assert prow["api"] == "Vulkan"

    prow_sec = pipeline_row(10, "Vulkan", ctrl.GetPipelineState(), section="ps")
    assert prow_sec["section"] == "ps"
    assert isinstance(prow_sec["section_detail"], dict)

    brows = bindings_rows(10, ctrl.GetPipelineState())
    assert len(brows) == 2

    srow = shader_row(10, ctrl.GetPipelineState(), "ps")
    assert srow["shader"] == 101
    assert srow["entry"] == "main_ps"
    assert srow["ro"] == 1


def test_shader_inventory() -> None:
    ctrl = rd.MockReplayController()
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Vertex] = rd.ResourceId(202)
    rows = shader_inventory({10: ctrl.GetPipelineState(), 11: ctrl.GetPipelineState()})
    assert len(rows) == 2
    assert rows[0]["shader"] == 101


def test_daemon_pipeline_bindings_shader_shaders() -> None:
    state = _state_with_adapter()

    resp, _ = _handle_request(
        {"id": 1, "method": "pipeline", "params": {"_token": "tok", "eid": 10}},
        state,
    )
    assert resp["result"]["row"]["eid"] == 10

    resp, _ = _handle_request(
        {
            "id": 1,
            "method": "pipeline",
            "params": {"_token": "tok", "eid": 10, "section": "ps"},
        },
        state,
    )
    assert resp["result"]["row"]["section"] == "ps"
    assert isinstance(resp["result"]["row"]["section_detail"], dict)

    resp, _ = _handle_request(
        {"id": 1, "method": "bindings", "params": {"_token": "tok", "eid": 10}},
        state,
    )
    assert len(resp["result"]["rows"]) == 2

    resp, _ = _handle_request(
        {
            "id": 1,
            "method": "shader",
            "params": {"_token": "tok", "eid": 10, "stage": "ps"},
        },
        state,
    )
    assert resp["result"]["row"]["shader"] == 101

    resp, _ = _handle_request({"id": 1, "method": "shaders", "params": {"_token": "tok"}}, state)
    assert len(resp["result"]["rows"]) >= 1


def test_daemon_shader_invalid_stage() -> None:
    state = _state_with_adapter()
    resp, _ = _handle_request(
        {
            "id": 1,
            "method": "shader",
            "params": {"_token": "tok", "stage": "bad"},
        },
        state,
    )
    assert resp["error"]["code"] == -32602


def test_daemon_pipeline_invalid_section() -> None:
    state = _state_with_adapter()
    resp, _ = _handle_request(
        {
            "id": 1,
            "method": "pipeline",
            "params": {"_token": "tok", "section": "bad"},
        },
        state,
    )
    assert resp["error"]["code"] == -32602


def test_cli_pipeline_no_session(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import rdc.commands.pipeline as pipeline_mod

    monkeypatch.setattr(pipeline_mod, "load_session", lambda: None)
    runner = CliRunner()
    result = runner.invoke(main, ["pipeline"])
    assert result.exit_code == 1


def test_cli_pipeline_json_output(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import rdc.commands.pipeline as pipeline_mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(pipeline_mod, "load_session", lambda: session)
    monkeypatch.setattr(
        pipeline_mod,
        "send_request",
        lambda _h, _p, _payload: {"result": {"row": {"eid": 10, "api": "Vulkan"}}},
    )
    runner = CliRunner()
    result = runner.invoke(main, ["pipeline", "--json"])
    assert result.exit_code == 0
    assert '"eid": 10' in result.output


def test_cli_shader_invalid_stage(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import rdc.commands.pipeline as pipeline_mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(pipeline_mod, "load_session", lambda: session)
    monkeypatch.setattr(
        pipeline_mod,
        "send_request",
        lambda _h, _p, _payload: {"error": {"message": "invalid stage"}},
    )
    runner = CliRunner()
    result = runner.invoke(main, ["shader", "1", "ps"])
    assert result.exit_code == 1


def test_cli_pipeline_replay_unavailable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import rdc.commands.pipeline as pipeline_mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(pipeline_mod, "load_session", lambda: session)
    monkeypatch.setattr(
        pipeline_mod,
        "send_request",
        lambda _h, _p, _payload: {"error": {"message": "no replay loaded"}},
    )
    runner = CliRunner()
    result = runner.invoke(main, ["pipeline"])
    assert result.exit_code == 1
