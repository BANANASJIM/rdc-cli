"""Tests for daemon JSON-RPC handlers: info, stats, events, draws, event, draw, pass."""

from __future__ import annotations

from types import SimpleNamespace

from conftest import make_daemon_state, rpc_request
from mock_renderdoc import (
    ActionDescription,
    ActionFlags,
    APIEvent,
    SDBasic,
    SDChunk,
    SDData,
    SDObject,
    StructuredFile,
)

from rdc.daemon_server import DaemonState, _handle_request


def _build_actions():
    shadow_begin = ActionDescription(
        eventId=10,
        flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
        _name="Shadow",
    )
    draw1 = ActionDescription(
        eventId=42,
        flags=ActionFlags.Drawcall | ActionFlags.Indexed,
        numIndices=3600,
        numInstances=1,
        _name="vkCmdDrawIndexed",
        events=[APIEvent(eventId=42, chunkIndex=0)],
    )
    shadow_marker = ActionDescription(
        eventId=41,
        flags=ActionFlags.NoFlags,
        _name="Shadow/Terrain",
        children=[draw1],
    )
    shadow_end = ActionDescription(
        eventId=50,
        flags=ActionFlags.EndPass | ActionFlags.PassBoundary,
        _name="EndPass",
    )
    dispatch = ActionDescription(eventId=300, flags=ActionFlags.Dispatch, _name="vkCmdDispatch")
    return [shadow_begin, shadow_marker, shadow_end, dispatch]


def _build_sf():
    return StructuredFile(
        chunks=[
            SDChunk(
                name="vkCmdDrawIndexed",
                children=[
                    SDObject(name="indexCount", data=SDData(basic=SDBasic(value=3600))),
                    SDObject(name="instanceCount", data=SDData(basic=SDBasic(value=1))),
                ],
            ),
        ]
    )


def _make_state():
    actions = _build_actions()
    sf = _build_sf()
    ctrl = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: [],
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        GetPipelineState=lambda: SimpleNamespace(),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: sf,
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
    )
    state = make_daemon_state(ctrl=ctrl, version=(1, 33), max_eid=300, structured_file=sf)
    from rdc.vfs.tree_cache import build_vfs_skeleton

    state.vfs_tree = build_vfs_skeleton(actions, [], sf=sf)
    return state


class TestInfoHandler:
    def test_info_metadata(self):
        resp, _ = _handle_request(rpc_request("info"), _make_state())
        assert resp["result"]["Capture"] == "test.rdc"
        assert resp["result"]["API"] == "Vulkan"

    def test_info_no_adapter(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(rpc_request("info"), state)
        assert resp["error"]["code"] == -32002


class TestStatsHandler:
    def test_stats_per_pass(self):
        resp, _ = _handle_request(rpc_request("stats"), _make_state())
        assert len(resp["result"]["per_pass"]) > 0

    def test_stats_top_draws(self):
        resp, _ = _handle_request(rpc_request("stats"), _make_state())
        assert len(resp["result"]["top_draws"]) >= 1

    def test_stats_no_adapter(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(rpc_request("stats"), state)
        assert resp["error"]["code"] == -32002


class TestEventsHandler:
    def test_events_list(self):
        resp, _ = _handle_request(rpc_request("events"), _make_state())
        assert len(resp["result"]["events"]) > 0

    def test_events_filter_type(self):
        resp, _ = _handle_request(rpc_request("events", {"type": "draw"}), _make_state())
        assert all(e["type"] in ("Draw", "DrawIndexed") for e in resp["result"]["events"])

    def test_events_filter_name(self):
        resp, _ = _handle_request(rpc_request("events", {"filter": "Shadow*"}), _make_state())
        assert any("Shadow" in e["name"] for e in resp["result"]["events"])

    def test_events_limit(self):
        resp, _ = _handle_request(rpc_request("events", {"limit": 2}), _make_state())
        assert len(resp["result"]["events"]) <= 2

    def test_events_range(self):
        resp, _ = _handle_request(rpc_request("events", {"range": "40:50"}), _make_state())
        assert all(40 <= e["eid"] <= 50 for e in resp["result"]["events"])

    def test_events_no_adapter(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(rpc_request("events"), state)
        assert resp["error"]["code"] == -32002


class TestDrawsHandler:
    def test_draws_list(self):
        resp, _ = _handle_request(rpc_request("draws"), _make_state())
        assert len(resp["result"]["draws"]) >= 1
        assert "summary" in resp["result"]

    def test_draws_filter_pass(self):
        state = _make_state()
        passes_resp, _ = _handle_request(rpc_request("passes"), state)
        friendly = passes_resp["result"]["tree"]["passes"][0]["name"]
        resp, _ = _handle_request(rpc_request("draws", {"pass": friendly}), state)
        assert len(resp["result"]["draws"]) > 0
        assert all(d["pass"] == friendly for d in resp["result"]["draws"])

    def test_draws_sort_triangles(self):
        resp, _ = _handle_request(rpc_request("draws", {"sort": "triangles"}), _make_state())
        tris = [d["triangles"] for d in resp["result"]["draws"]]
        assert tris == sorted(tris, reverse=True)

    def test_draws_limit(self):
        resp, _ = _handle_request(rpc_request("draws", {"limit": 1}), _make_state())
        assert len(resp["result"]["draws"]) <= 1

    def test_draws_empty_pass(self):
        resp, _ = _handle_request(rpc_request("draws", {"pass": "NonExistent"}), _make_state())
        assert len(resp["result"]["draws"]) == 0


class TestEventHandler:
    def test_event_detail(self):
        resp, _ = _handle_request(rpc_request("event", {"eid": 42}), _make_state())
        assert resp["result"]["EID"] == 42
        assert resp["result"]["API Call"] == "vkCmdDrawIndexed"

    def test_event_params(self):
        resp, _ = _handle_request(rpc_request("event", {"eid": 42}), _make_state())
        assert "indexCount" in str(resp["result"]["Parameters"])

    def test_event_not_found(self):
        resp, _ = _handle_request(rpc_request("event", {"eid": 99999}), _make_state())
        assert resp["error"]["code"] == -32002

    def test_event_missing_eid(self):
        resp, _ = _handle_request(rpc_request("event"), _make_state())
        assert resp["error"]["code"] == -32602


class TestDrawHandler:
    def test_draw_detail(self):
        resp, _ = _handle_request(rpc_request("draw", {"eid": 42}), _make_state())
        assert resp["result"]["Event"] == 42
        assert resp["result"]["Triangles"] == 1200
        assert resp["result"]["Instances"] == 1

    def test_draw_current_eid(self):
        state = _make_state()
        state.current_eid = 42
        resp, _ = _handle_request(rpc_request("draw"), state)
        assert resp["result"]["Event"] == 42

    def test_draw_not_found(self):
        resp, _ = _handle_request(rpc_request("draw", {"eid": 99999}), _make_state())
        assert resp["error"]["code"] == -32002


class _IntLike:
    """Helper that supports int() conversion for resource IDs."""

    def __init__(self, val: int) -> None:
        self._val = val

    def __int__(self) -> int:
        return self._val


def _build_pass_actions() -> list[ActionDescription]:
    """Hierarchical pass tree for pass handler tests."""
    shadow_begin = ActionDescription(
        eventId=10, flags=ActionFlags.BeginPass | ActionFlags.PassBoundary, _name="Shadow"
    )
    draw1 = ActionDescription(
        eventId=42,
        flags=ActionFlags.Drawcall | ActionFlags.Indexed,
        numIndices=3600,
        numInstances=1,
        _name="vkCmdDrawIndexed",
        events=[APIEvent(eventId=42, chunkIndex=0)],
    )
    shadow_begin.children = [draw1]
    shadow_end = ActionDescription(
        eventId=50, flags=ActionFlags.EndPass | ActionFlags.PassBoundary, _name="EndPass"
    )
    return [shadow_begin, shadow_end]


def _make_pass_state():
    """State with output targets on pipeline for pass detail tests."""
    actions = _build_pass_actions()
    sf = _build_sf()
    pipe = SimpleNamespace(
        GetOutputTargets=lambda: [SimpleNamespace(resource=_IntLike(10))],
        GetDepthTarget=lambda: SimpleNamespace(resource=_IntLike(20)),
    )
    ctrl = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: [],
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        GetPipelineState=lambda: pipe,
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: sf,
        Shutdown=lambda: None,
    )
    return make_daemon_state(ctrl=ctrl, version=(1, 33), max_eid=300, structured_file=sf)


def _make_log_state(messages=None):
    """State with debug messages for log handler tests."""
    actions = _build_actions()
    sf = _build_sf()
    msgs = messages or []
    ctrl = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: [],
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        GetPipelineState=lambda: SimpleNamespace(),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: sf,
        GetDebugMessages=lambda: msgs,
        Shutdown=lambda: None,
    )
    return make_daemon_state(ctrl=ctrl, version=(1, 33), max_eid=300, structured_file=sf)


class TestPassHandler:
    def test_pass_by_index(self):
        resp, _ = _handle_request(rpc_request("pass", {"index": 0}), _make_pass_state())
        result = resp["result"]
        assert result["name"] == "Shadow"
        assert result["begin_eid"] == 10
        assert result["draws"] == 1
        assert result["triangles"] == 1200

    def test_pass_by_name(self):
        resp, _ = _handle_request(rpc_request("pass", {"name": "Shadow"}), _make_pass_state())
        assert resp["result"]["name"] == "Shadow"

    def test_pass_by_name_case_insensitive(self):
        resp, _ = _handle_request(rpc_request("pass", {"name": "shadow"}), _make_pass_state())
        assert resp["result"]["name"] == "Shadow"

    def test_pass_not_found_index(self):
        resp, _ = _handle_request(rpc_request("pass", {"index": 999}), _make_pass_state())
        assert resp["error"]["code"] == -32001

    def test_pass_not_found_name(self):
        resp, _ = _handle_request(rpc_request("pass", {"name": "NoSuch"}), _make_pass_state())
        assert resp["error"]["code"] == -32001

    def test_pass_no_adapter(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(rpc_request("pass", {"index": 0}), state)
        assert resp["error"]["code"] == -32002

    def test_pass_missing_params(self):
        resp, _ = _handle_request(rpc_request("pass"), _make_pass_state())
        assert resp["error"]["code"] == -32602

    def test_pass_invalid_index(self):
        resp, _ = _handle_request(rpc_request("pass", {"index": "abc"}), _make_pass_state())
        assert resp["error"]["code"] == -32602

    def test_pass_color_targets(self):
        resp, _ = _handle_request(rpc_request("pass", {"index": 0}), _make_pass_state())
        result = resp["result"]
        assert len(result["color_targets"]) == 1
        assert result["color_targets"][0]["id"] == 10
        assert result["depth_target"] == 20


class TestLogHandler:
    def test_log_messages(self):
        msgs = [
            SimpleNamespace(severity=0, eventId=0, description="validation error"),
            SimpleNamespace(severity=3, eventId=42, description="info message"),
        ]
        resp, _ = _handle_request(rpc_request("log"), _make_log_state(msgs))
        result = resp["result"]["messages"]
        assert len(result) == 2
        assert result[0]["level"] == "HIGH"
        assert result[0]["eid"] == 0
        assert result[1]["level"] == "INFO"
        assert result[1]["eid"] == 42

    def test_log_filter_level(self):
        msgs = [
            SimpleNamespace(severity=0, eventId=0, description="error"),
            SimpleNamespace(severity=3, eventId=10, description="info"),
        ]
        resp, _ = _handle_request(rpc_request("log", {"level": "HIGH"}), _make_log_state(msgs))
        result = resp["result"]["messages"]
        assert len(result) == 1
        assert result[0]["level"] == "HIGH"

    def test_log_filter_eid(self):
        msgs = [
            SimpleNamespace(severity=0, eventId=0, description="global"),
            SimpleNamespace(severity=1, eventId=42, description="at eid 42"),
        ]
        resp, _ = _handle_request(rpc_request("log", {"eid": 42}), _make_log_state(msgs))
        result = resp["result"]["messages"]
        assert len(result) == 1
        assert result[0]["eid"] == 42

    def test_log_filter_eid_zero(self):
        msgs = [
            SimpleNamespace(severity=0, eventId=0, description="global"),
            SimpleNamespace(severity=1, eventId=42, description="at eid 42"),
        ]
        resp, _ = _handle_request(rpc_request("log", {"eid": 0}), _make_log_state(msgs))
        result = resp["result"]["messages"]
        assert len(result) == 1
        assert result[0]["message"] == "global"

    def test_log_empty(self):
        resp, _ = _handle_request(rpc_request("log"), _make_log_state([]))
        assert resp["result"]["messages"] == []

    def test_log_no_adapter(self):
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(rpc_request("log"), state)
        assert resp["error"]["code"] == -32002

    def test_log_invalid_level(self):
        resp, _ = _handle_request(rpc_request("log", {"level": "HIHG"}), _make_log_state([]))
        assert resp["error"]["code"] == -32602

    def test_log_invalid_eid(self):
        resp, _ = _handle_request(rpc_request("log", {"eid": "abc"}), _make_log_state([]))
        assert resp["error"]["code"] == -32602


class TestEventMultiChunk:
    def _make_multi_chunk_state(self):
        sf = StructuredFile(
            chunks=[
                SDChunk(
                    name="vkCmdSetViewport",
                    children=[
                        SDObject(name="viewportCount", data=SDData(basic=SDBasic(value=1))),
                    ],
                ),
                SDChunk(
                    name="vkCmdDrawIndexed",
                    children=[
                        SDObject(name="indexCount", data=SDData(basic=SDBasic(value=3600))),
                        SDObject(name="instanceCount", data=SDData(basic=SDBasic(value=1))),
                    ],
                ),
            ]
        )
        action = ActionDescription(
            eventId=42,
            flags=ActionFlags.Drawcall | ActionFlags.Indexed,
            numIndices=3600,
            numInstances=1,
            _name="vkCmdDrawIndexed",
            events=[
                APIEvent(eventId=42, chunkIndex=0),
                APIEvent(eventId=42, chunkIndex=1),
            ],
        )
        ctrl = SimpleNamespace(
            GetRootActions=lambda: [action],
            GetResources=lambda: [],
            GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
            GetPipelineState=lambda: SimpleNamespace(),
            SetFrameEvent=lambda eid, force: None,
            GetStructuredFile=lambda: sf,
            GetDebugMessages=lambda: [],
            Shutdown=lambda: None,
        )
        state = make_daemon_state(ctrl=ctrl, version=(1, 33), max_eid=42, structured_file=sf)
        from rdc.vfs.tree_cache import build_vfs_skeleton

        state.vfs_tree = build_vfs_skeleton([action], [], sf=sf)
        return state

    def test_all_chunk_params_present(self):
        resp, _ = _handle_request(rpc_request("event", {"eid": 42}), self._make_multi_chunk_state())
        params_str = resp["result"]["Parameters"]
        assert "viewportCount" in params_str
        assert "indexCount" in params_str
        assert "instanceCount" in params_str

    def test_last_chunk_wins_api_call(self):
        resp, _ = _handle_request(rpc_request("event", {"eid": 42}), self._make_multi_chunk_state())
        assert resp["result"]["API Call"] == "vkCmdDrawIndexed"


# ---------------------------------------------------------------------------
# Tests: B16 — mesh dispatch (MeshDispatch = 0x0008) classified as draw
# ---------------------------------------------------------------------------


def _build_mesh_actions():
    """Action tree with a single mesh dispatch action."""
    mesh_draw = ActionDescription(
        eventId=10,
        flags=ActionFlags.MeshDispatch,
        numIndices=0,
        numInstances=1,
        _name="vkCmdDrawMeshTasksEXT",
    )
    return [mesh_draw]


def _make_mesh_state():
    actions = _build_mesh_actions()
    sf = StructuredFile()
    ctrl = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: [],
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        GetPipelineState=lambda: SimpleNamespace(),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: sf,
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
    )
    state = make_daemon_state(ctrl=ctrl, version=(1, 33), max_eid=10, structured_file=sf)
    from rdc.vfs.tree_cache import build_vfs_skeleton

    state.vfs_tree = build_vfs_skeleton(actions, [], sf=sf)
    return state


class TestMeshDispatchClassification:
    def test_mesh_dispatch_action_type_str(self):
        from rdc.handlers._helpers import _action_type_str

        assert _action_type_str(0x0008) == "Draw"
        assert _action_type_str(0x0008) != "Other"

    def test_mesh_dispatch_classified_as_draw_in_events(self):
        resp, _ = _handle_request(rpc_request("events"), _make_mesh_state())
        events = resp["result"]["events"]
        mesh_ev = [e for e in events if e["eid"] == 10]
        assert len(mesh_ev) == 1
        assert mesh_ev[0]["type"] != "Other"
        assert mesh_ev[0]["type"] == "Draw"

    def test_mesh_dispatch_included_in_draws_list(self):
        resp, _ = _handle_request(rpc_request("draws"), _make_mesh_state())
        draws = resp["result"]["draws"]
        mesh_draws = [d for d in draws if d["eid"] == 10]
        assert len(mesh_draws) == 1

    def test_mesh_dispatch_counted_as_draw(self):
        resp, _ = _handle_request(rpc_request("count", {"what": "draws"}), _make_mesh_state())
        assert resp["result"]["value"] == 1

    def test_mesh_dispatch_in_info_draw_calls(self):
        resp, _ = _handle_request(rpc_request("info"), _make_mesh_state())
        draw_calls = resp["result"]["Draw Calls"]
        assert "1 " in draw_calls

    def test_mesh_dispatch_not_classified_as_dispatch(self):
        resp, _ = _handle_request(rpc_request("count", {"what": "dispatches"}), _make_mesh_state())
        assert resp["result"]["value"] == 0
