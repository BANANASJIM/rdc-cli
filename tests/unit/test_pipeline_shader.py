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
        readOnlyResources=[rd.ShaderResource(name="albedo", fixedBindNumber=0)],
        readWriteResources=[rd.ShaderResource(name="rwbuf", fixedBindNumber=1)],
        constantBlocks=[rd.ConstantBlock(name="Globals", fixedBindNumber=0)],
    )

    from rdc.adapter import RenderDocAdapter

    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 33))
    state.api_name = "Vulkan"
    state.max_eid = 100
    return state


def test_query_service_rows() -> None:
    ctrl = rd.MockReplayController()
    ps_id = rd.ResourceId(101)
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = ps_id
    ctrl._pipe_state._entry_points[rd.ShaderStage.Pixel] = "main_ps"
    ctrl._pipe_state._reflections[rd.ShaderStage.Pixel] = rd.ShaderReflection(
        resourceId=ps_id,
        readOnlyResources=[rd.ShaderResource(name="albedo", fixedBindNumber=0)],
        readWriteResources=[rd.ShaderResource(name="rwbuf", fixedBindNumber=1)],
        constantBlocks=[rd.ConstantBlock(name="Globals", fixedBindNumber=0)],
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


def test_query_service_resources() -> None:
    """Test get_resources and get_resource_detail."""
    from rdc.services.query_service import get_resource_detail, get_resources

    ctrl = rd.MockReplayController()
    # Add some resources
    res1 = rd.ResourceDescription(
        resourceId=rd.ResourceId(1), name="Texture0", type=rd.ResourceType.Texture
    )
    res2 = rd.ResourceDescription(
        resourceId=rd.ResourceId(2), name="Buffer0", type=rd.ResourceType.Buffer
    )
    ctrl._resources = [res1, res2]

    from rdc.adapter import RenderDocAdapter

    adapter = RenderDocAdapter(controller=ctrl, version=(1, 33))

    rows = get_resources(adapter)
    assert len(rows) == 2
    assert rows[0]["id"] == 1
    assert rows[0]["name"] == "Texture0"
    assert rows[1]["id"] == 2

    # Test get_resource_detail
    detail = get_resource_detail(adapter, 1)
    assert detail is not None
    assert detail["id"] == 1
    assert detail["name"] == "Texture0"

    # Test non-existent resource
    detail = get_resource_detail(adapter, 999)
    assert detail is None


def test_query_service_pass_hierarchy() -> None:
    """Test get_pass_hierarchy with flat sibling structure matching real RenderDoc API."""
    from rdc.services.query_service import get_pass_hierarchy

    # Real API: BeginPass has no children; draws appear as siblings before EndPass.
    begin_pass = rd.ActionDescription(eventId=10, flags=rd.ActionFlags.BeginPass)
    begin_pass._name = "Pass1"
    draw = rd.ActionDescription(eventId=11, flags=rd.ActionFlags.Drawcall)
    end_pass = rd.ActionDescription(eventId=12, flags=rd.ActionFlags.EndPass)

    actions = [begin_pass, draw, end_pass]
    tree = get_pass_hierarchy(actions)

    assert "passes" in tree
    assert len(tree["passes"]) == 1
    assert tree["passes"][0]["name"] == "Pass1"
    assert tree["passes"][0]["draws"] == 1


def test_daemon_resources_handler() -> None:
    """Test daemon handler for resources method."""
    state = _state_with_adapter()
    # Add resources to mock
    res1 = rd.ResourceDescription(
        resourceId=rd.ResourceId(1), name="Tex", type=rd.ResourceType.Texture
    )
    state.adapter.controller._resources = [res1]

    request = {"jsonrpc": "2.0", "id": 1, "method": "resources", "params": {"_token": "tok"}}
    resp, _ = _handle_request(request, state)

    assert "result" in resp
    assert "rows" in resp["result"]
    assert len(resp["result"]["rows"]) == 1


def test_daemon_resource_handler() -> None:
    """Test daemon handler for resource method."""
    state = _state_with_adapter()
    res1 = rd.ResourceDescription(
        resourceId=rd.ResourceId(1), name="Tex", type=rd.ResourceType.Texture
    )
    state.adapter.controller._resources = [res1]

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "resource",
        "params": {"_token": "tok", "id": 1},
    }
    resp, _ = _handle_request(request, state)

    assert "result" in resp
    assert "resource" in resp["result"]
    assert resp["result"]["resource"]["id"] == 1

    # Test resource not found
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "resource",
        "params": {"_token": "tok", "id": 999},
    }
    resp, _ = _handle_request(request, state)
    assert "error" in resp


def test_daemon_passes_handler() -> None:
    """Test daemon handler for passes method."""
    state = _state_with_adapter()
    # Real API: BeginPass has no children; draws appear as siblings before EndPass.
    begin_pass = rd.ActionDescription(eventId=10, flags=rd.ActionFlags.BeginPass)
    begin_pass._name = "Pass1"
    draw = rd.ActionDescription(eventId=11, flags=rd.ActionFlags.Drawcall)
    end_pass = rd.ActionDescription(eventId=12, flags=rd.ActionFlags.EndPass)
    state.adapter.controller._actions = [begin_pass, draw, end_pass]

    request = {"jsonrpc": "2.0", "id": 1, "method": "passes", "params": {"_token": "tok"}}
    resp, _ = _handle_request(request, state)

    assert "result" in resp
    assert "tree" in resp["result"]
    assert len(resp["result"]["tree"]["passes"]) == 1
    assert resp["result"]["tree"]["passes"][0]["draws"] == 1
