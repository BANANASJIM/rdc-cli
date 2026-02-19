"""Tests for rdc count and rdc shader-map commands."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as mrd  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers: build mock action trees
# ---------------------------------------------------------------------------


def _indexed_draw(
    eid: int, name: str, indices: int = 300, instances: int = 1
) -> mrd.ActionDescription:
    return mrd.ActionDescription(
        eventId=eid,
        flags=mrd.ActionFlags.Drawcall | mrd.ActionFlags.Indexed,
        numIndices=indices,
        numInstances=instances,
        _name=name,
    )


def _dispatch(eid: int, name: str) -> mrd.ActionDescription:
    return mrd.ActionDescription(
        eventId=eid,
        flags=mrd.ActionFlags.Dispatch,
        _name=name,
    )


def _clear(eid: int, name: str) -> mrd.ActionDescription:
    return mrd.ActionDescription(
        eventId=eid,
        flags=mrd.ActionFlags.Clear,
        _name=name,
    )


def _pass_begin(eid: int, name: str) -> mrd.ActionDescription:
    return mrd.ActionDescription(
        eventId=eid,
        flags=mrd.ActionFlags.PassBoundary | mrd.ActionFlags.BeginPass,
        _name=name,
    )


def _pass_end(eid: int, name: str) -> mrd.ActionDescription:
    return mrd.ActionDescription(
        eventId=eid,
        flags=mrd.ActionFlags.PassBoundary | mrd.ActionFlags.EndPass,
        _name=name,
    )


def _build_action_tree() -> list[mrd.ActionDescription]:
    """Build a representative action tree with 2 passes."""
    shadow_pass = _pass_begin(10, "Shadow")
    shadow_pass.children = [
        _indexed_draw(11, "vkCmdDrawIndexed", indices=900, instances=1),
        _indexed_draw(12, "vkCmdDrawIndexed", indices=600, instances=1),
    ]
    shadow_end = _pass_end(13, "Shadow")

    gbuffer_pass = _pass_begin(20, "GBuffer")
    gbuffer_pass.children = [
        _indexed_draw(21, "vkCmdDrawIndexed", indices=3600, instances=1),
        _clear(22, "vkCmdClear"),
        _dispatch(23, "vkCmdDispatch"),
    ]
    gbuffer_end = _pass_end(24, "GBuffer")

    return [shadow_pass, shadow_end, gbuffer_pass, gbuffer_end]


def _make_pipe_state(
    vs: int = 0,
    hs: int = 0,
    ds: int = 0,
    gs: int = 0,
    ps: int = 0,
    cs: int = 0,
) -> mrd.MockPipeState:
    """Create a MockPipeState with given shader resource IDs per stage."""
    state = mrd.MockPipeState()
    if vs:
        state._shaders[mrd.ShaderStage.Vertex] = mrd.ResourceId(vs)
    if hs:
        state._shaders[mrd.ShaderStage.Hull] = mrd.ResourceId(hs)
    if ds:
        state._shaders[mrd.ShaderStage.Domain] = mrd.ResourceId(ds)
    if gs:
        state._shaders[mrd.ShaderStage.Geometry] = mrd.ResourceId(gs)
    if ps:
        state._shaders[mrd.ShaderStage.Pixel] = mrd.ResourceId(ps)
    if cs:
        state._shaders[mrd.ShaderStage.Compute] = mrd.ResourceId(cs)
    return state


# ---------------------------------------------------------------------------
# Tests: count aggregation logic
# ---------------------------------------------------------------------------


class TestCountAggregation:
    """Test the count aggregation logic in query_service."""

    def test_count_draws(self) -> None:
        from rdc.services.query_service import count_from_actions

        assert count_from_actions(_build_action_tree(), "draws") == 3

    def test_count_events(self) -> None:
        from rdc.services.query_service import count_from_actions

        assert count_from_actions(_build_action_tree(), "events") == 9

    def test_count_triangles(self) -> None:
        from rdc.services.query_service import count_from_actions

        # (900 + 600 + 3600) // 3 = 1700
        assert count_from_actions(_build_action_tree(), "triangles") == 1700

    def test_count_dispatches(self) -> None:
        from rdc.services.query_service import count_from_actions

        assert count_from_actions(_build_action_tree(), "dispatches") == 1

    def test_count_clears(self) -> None:
        from rdc.services.query_service import count_from_actions

        assert count_from_actions(_build_action_tree(), "clears") == 1

    def test_count_passes(self) -> None:
        from rdc.services.query_service import count_from_actions

        assert count_from_actions(_build_action_tree(), "passes") == 2

    def test_count_resources(self) -> None:
        from rdc.services.query_service import count_resources

        assert count_resources([mrd.ResourceDescription() for _ in range(5)]) == 5

    def test_count_draws_with_pass_filter(self) -> None:
        from rdc.services.query_service import count_from_actions

        assert count_from_actions(_build_action_tree(), "draws", pass_name="Shadow") == 2

    def test_count_triangles_with_pass_filter(self) -> None:
        from rdc.services.query_service import count_from_actions

        assert count_from_actions(_build_action_tree(), "triangles", pass_name="Shadow") == 500

    def test_count_draws_nonexistent_pass(self) -> None:
        from rdc.services.query_service import count_from_actions

        assert count_from_actions(_build_action_tree(), "draws", pass_name="Nope") == 0

    def test_count_zero_draws(self) -> None:
        from rdc.services.query_service import count_from_actions

        assert count_from_actions([], "draws") == 0

    def test_count_invalid_target(self) -> None:
        from rdc.services.query_service import count_from_actions

        with pytest.raises(ValueError, match="unknown count target"):
            count_from_actions([], "bogus_target")


# ---------------------------------------------------------------------------
# Tests: shader-map collection logic
# ---------------------------------------------------------------------------


class TestShaderMapCollection:
    """Test shader-map collection logic."""

    def test_shader_map_basic(self) -> None:
        from rdc.services.query_service import collect_shader_map

        actions = [_indexed_draw(42, "draw")]
        states = {42: _make_pipe_state(vs=10, ps=11)}
        rows = collect_shader_map(actions, states)
        assert len(rows) == 1
        assert rows[0] == {
            "eid": 42,
            "vs": 10,
            "hs": "-",
            "ds": "-",
            "gs": "-",
            "ps": 11,
            "cs": "-",
        }

    def test_shader_map_mixed_stages(self) -> None:
        from rdc.services.query_service import collect_shader_map

        actions = [_indexed_draw(42, "d1"), _indexed_draw(43, "d2")]
        states = {
            42: _make_pipe_state(vs=10, gs=12, ps=11),
            43: _make_pipe_state(vs=10, hs=20, ds=21, ps=11),
        }
        rows = collect_shader_map(actions, states)
        assert len(rows) == 2
        assert rows[0]["gs"] == 12
        assert rows[1]["hs"] == 20

    def test_shader_map_compute_only(self) -> None:
        from rdc.services.query_service import collect_shader_map

        actions = [_dispatch(50, "dispatch")]
        states = {50: _make_pipe_state(cs=99)}
        rows = collect_shader_map(actions, states)
        assert len(rows) == 1
        assert rows[0]["cs"] == 99
        assert rows[0]["vs"] == "-"

    def test_shader_map_empty(self) -> None:
        from rdc.services.query_service import collect_shader_map

        assert collect_shader_map([], {}) == []


# ---------------------------------------------------------------------------
# Tests: CLI output format
# ---------------------------------------------------------------------------


class TestCountCLIOutput:
    """Test that rdc count outputs exactly a single integer."""

    def test_count_outputs_integer(self) -> None:
        from rdc.cli import main

        runner = CliRunner()
        with patch("rdc.commands.unix_helpers._get_count_value", return_value=42):
            result = runner.invoke(main, ["count", "draws"])
        assert result.exit_code == 0
        assert result.output == "42\n"
        assert result.output.strip().isdigit()

    def test_count_zero(self) -> None:
        from rdc.cli import main

        runner = CliRunner()
        with patch("rdc.commands.unix_helpers._get_count_value", return_value=0):
            result = runner.invoke(main, ["count", "draws"])
        assert result.exit_code == 0
        assert result.output == "0\n"

    def test_count_no_session_error(self) -> None:
        from rdc.cli import main

        runner = CliRunner()
        with patch("rdc.commands.unix_helpers._get_count_value", side_effect=SystemExit(1)):
            result = runner.invoke(main, ["count", "draws"])
        assert result.exit_code == 1

    def test_count_invalid_target(self) -> None:
        from rdc.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["count", "bogus"])
        assert result.exit_code != 0


class TestShaderMapCLIOutput:
    """Test rdc shader-map TSV output format."""

    def test_shader_map_with_header(self) -> None:
        from rdc.cli import main

        runner = CliRunner()
        rows = [{"eid": 42, "vs": 10, "hs": "-", "ds": "-", "gs": "-", "ps": 11, "cs": "-"}]
        with patch("rdc.commands.unix_helpers._get_shader_map_rows", return_value=rows):
            result = runner.invoke(main, ["shader-map"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "EID\tVS\tHS\tDS\tGS\tPS\tCS"
        assert lines[1] == "42\t10\t-\t-\t-\t11\t-"

    def test_shader_map_no_header(self) -> None:
        from rdc.cli import main

        runner = CliRunner()
        rows = [{"eid": 42, "vs": 10, "hs": "-", "ds": "-", "gs": "-", "ps": 11, "cs": "-"}]
        with patch("rdc.commands.unix_helpers._get_shader_map_rows", return_value=rows):
            result = runner.invoke(main, ["shader-map", "--no-header"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "42\t10\t-\t-\t-\t11\t-"

    def test_shader_map_empty_with_header(self) -> None:
        from rdc.cli import main

        runner = CliRunner()
        with patch("rdc.commands.unix_helpers._get_shader_map_rows", return_value=[]):
            result = runner.invoke(main, ["shader-map"])
        assert result.exit_code == 0
        assert "EID\tVS\tHS\tDS\tGS\tPS\tCS" in result.output

    def test_shader_map_empty_no_header(self) -> None:
        from rdc.cli import main

        runner = CliRunner()
        with patch("rdc.commands.unix_helpers._get_shader_map_rows", return_value=[]):
            result = runner.invoke(main, ["shader-map", "--no-header"])
        assert result.exit_code == 0
        assert result.output == ""


# ---------------------------------------------------------------------------
# Tests: daemon JSON-RPC handlers
# ---------------------------------------------------------------------------


class TestDaemonCountMethod:
    """Test the daemon count JSON-RPC method."""

    def test_count_draws(self) -> None:
        from rdc.daemon_server import DaemonState, _handle_request

        actions = _build_action_tree()
        state = DaemonState(
            capture="test.rdc",
            current_eid=0,
            token="tok",
            adapter=MagicMock(
                get_root_actions=MagicMock(return_value=actions),
                get_resources=MagicMock(return_value=[]),
            ),
        )
        req = {"id": 1, "method": "count", "params": {"_token": "tok", "what": "draws"}}
        resp, _ = _handle_request(req, state)
        assert resp["result"]["value"] == 3

    def test_count_resources(self) -> None:
        from rdc.daemon_server import DaemonState, _handle_request

        resources = [mrd.ResourceDescription() for _ in range(7)]
        state = DaemonState(
            capture="test.rdc",
            current_eid=0,
            token="tok",
            adapter=MagicMock(
                get_root_actions=MagicMock(return_value=[]),
                get_resources=MagicMock(return_value=resources),
            ),
        )
        req = {"id": 1, "method": "count", "params": {"_token": "tok", "what": "resources"}}
        resp, _ = _handle_request(req, state)
        assert resp["result"]["value"] == 7

    def test_count_invalid_target(self) -> None:
        from rdc.daemon_server import DaemonState, _handle_request

        state = DaemonState(
            capture="test.rdc",
            current_eid=0,
            token="tok",
            adapter=MagicMock(get_root_actions=MagicMock(return_value=[])),
        )
        req = {"id": 1, "method": "count", "params": {"_token": "tok", "what": "bogus"}}
        resp, _ = _handle_request(req, state)
        assert "error" in resp

    def test_count_with_pass_filter(self) -> None:
        from rdc.daemon_server import DaemonState, _handle_request

        actions = _build_action_tree()
        state = DaemonState(
            capture="test.rdc",
            current_eid=0,
            token="tok",
            adapter=MagicMock(get_root_actions=MagicMock(return_value=actions)),
        )
        req = {
            "id": 1,
            "method": "count",
            "params": {"_token": "tok", "what": "draws", "pass": "Shadow"},
        }
        resp, _ = _handle_request(req, state)
        assert resp["result"]["value"] == 2


class TestDaemonShaderMapMethod:
    """Test the daemon shader_map JSON-RPC method."""

    def test_shader_map_returns_rows(self) -> None:
        from rdc.daemon_server import DaemonState, _handle_request

        draw = _indexed_draw(42, "draw")
        pipe_state = _make_pipe_state(vs=10, ps=11)

        adapter = MagicMock()
        adapter.get_root_actions.return_value = [draw]
        adapter.get_pipeline_state.return_value = pipe_state
        adapter.set_frame_event = MagicMock()

        state = DaemonState(
            capture="test.rdc",
            current_eid=0,
            token="tok",
            adapter=adapter,
        )

        req = {"id": 1, "method": "shader_map", "params": {"_token": "tok"}}
        resp, _ = _handle_request(req, state)
        rows = resp["result"]["rows"]
        assert len(rows) == 1
        assert rows[0]["eid"] == 42
        assert rows[0]["vs"] == 10
        assert rows[0]["ps"] == 11
        assert rows[0]["hs"] == "-"
