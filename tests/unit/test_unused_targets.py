"""Tests for unused render targets: service, daemon handler, CLI."""

from __future__ import annotations

import json
from typing import Any

import mock_renderdoc as rd
from click.testing import CliRunner
from conftest import rpc_request

from rdc.adapter import RenderDocAdapter
from rdc.cli import main
from rdc.commands import unused_targets as unused_mod
from rdc.daemon_server import DaemonState, _handle_request
from rdc.services.query_service import find_unused_targets

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _eu(eid: int, usage: rd.ResourceUsage) -> rd.EventUsage:
    return rd.EventUsage(eventId=eid, usage=usage)


def _pass(name: str, begin: int, end: int) -> dict[str, Any]:
    return {"name": name, "begin_eid": begin, "end_eid": end, "draws": 0}


# ---------------------------------------------------------------------------
# Service: find_unused_targets()
# ---------------------------------------------------------------------------


class TestServiceNoUnused:
    """All targets feed into swapchain."""

    def test_empty_when_all_consumed(self) -> None:
        passes = [_pass("Shadow", 1, 10), _pass("Main", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ],
            200: [_eu(15, rd.ResourceUsage.ColorTarget)],
        }
        result = find_unused_targets(passes, usage, {97: "ShadowMap", 200: "Swapchain"}, {200})
        assert result["unused"] == []
        assert result["waves"] == 0

    def test_empty_passes(self) -> None:
        result = find_unused_targets([], {}, {}, set())
        assert result["unused"] == []

    def test_empty_usage(self) -> None:
        result = find_unused_targets([_pass("A", 1, 10)], {}, {}, set())
        assert result["unused"] == []


class TestServiceOneUnused:
    """One render target written but never consumed."""

    def test_single_unused_rt(self) -> None:
        passes = [_pass("Shadow", 1, 10), _pass("Main", 11, 20)]
        usage = {
            97: [_eu(5, rd.ResourceUsage.ColorTarget)],  # written, never read
            200: [_eu(15, rd.ResourceUsage.ColorTarget)],  # swapchain
        }
        result = find_unused_targets(passes, usage, {97: "ShadowMap", 200: "Swapchain"}, {200})
        assert len(result["unused"]) == 1
        entry = result["unused"][0]
        assert entry["id"] == 97
        assert entry["name"] == "ShadowMap"
        assert entry["wave"] == 1
        assert "Shadow" in entry["written_by"]


class TestServiceMultiWave:
    """Wave 1 removes leaf dead, wave 2 removes newly orphaned."""

    def test_two_wave_pruning(self) -> None:
        # A writes 97 -> B reads 97 and writes 200 -> nothing reads 200
        # C writes 300 (swapchain)
        passes = [_pass("A", 1, 10), _pass("B", 11, 20), _pass("C", 21, 30)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ],
            200: [_eu(16, rd.ResourceUsage.ColorTarget)],
            300: [_eu(25, rd.ResourceUsage.ColorTarget)],
        }
        result = find_unused_targets(passes, usage, {97: "Tex97", 200: "Tex200", 300: "SC"}, {300})
        assert result["waves"] == 2
        wave_map = {e["id"]: e["wave"] for e in result["unused"]}
        assert wave_map[200] == 1  # leaf dead first
        assert wave_map[97] == 2  # orphaned after 200 removed


class TestServiceSwapchainAlwaysLive:
    """Swapchain images are never reported as unused."""

    def test_swapchain_live(self) -> None:
        passes = [_pass("Main", 1, 10)]
        usage = {200: [_eu(5, rd.ResourceUsage.ColorTarget)]}
        result = find_unused_targets(passes, usage, {200: "SC"}, {200})
        assert result["unused"] == []


class TestServiceDepthConservativeKeep:
    """Depth-only pass feeding nothing is conservatively kept alive."""

    def test_depth_kept(self) -> None:
        passes = [_pass("DepthOnly", 1, 10), _pass("Main", 11, 20)]
        usage = {
            97: [_eu(5, rd.ResourceUsage.DepthStencilTarget)],  # depth, never read
            200: [_eu(15, rd.ResourceUsage.ColorTarget)],
        }
        result = find_unused_targets(passes, usage, {97: "DepthBuf", 200: "SC"}, {200})
        # Depth resource should NOT be reported
        ids = [e["id"] for e in result["unused"]]
        assert 97 not in ids


class TestServiceOutOfPassConsumer:
    """Resource consumed outside any pass should be considered live."""

    def test_copysrc_outside_pass_keeps_resource_live(self) -> None:
        """Render in pass, then CopySrc to swapchain outside pass boundaries."""
        passes = [_pass("Shadow", 1, 10), _pass("Main", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),  # written in Shadow pass
                _eu(25, rd.ResourceUsage.CopySrc),  # read outside any pass (eid 25)
            ],
            200: [_eu(15, rd.ResourceUsage.ColorTarget)],  # swapchain
        }
        result = find_unused_targets(passes, usage, {97: "RT", 200: "SC"}, {200})
        ids = [e["id"] for e in result["unused"]]
        assert 97 not in ids, "resource read outside pass should be live"


class TestServiceGlesNoPassFallback:
    """GLES-style captures with no BeginPass should still detect unused targets."""

    def test_synthetic_passes_detect_unused(self) -> None:
        from rdc.services.query_service import _pass_list_with_fallback

        actions = [
            rd.ActionDescription(
                eventId=5,
                flags=rd.ActionFlags.Drawcall,
                _name="Draw #5",
            ),
            rd.ActionDescription(
                eventId=10,
                flags=rd.ActionFlags.Drawcall,
                _name="Draw #10",
            ),
        ]
        passes = _pass_list_with_fallback(actions)
        assert len(passes) > 0, "synthetic fallback should produce passes"

        usage = {
            97: [_eu(5, rd.ResourceUsage.ColorTarget)],  # written, never read
            200: [_eu(10, rd.ResourceUsage.ColorTarget)],  # swapchain
        }
        result = find_unused_targets(passes, usage, {97: "RT", 200: "SC"}, {200})
        ids = [e["id"] for e in result["unused"]]
        assert 97 in ids


# ---------------------------------------------------------------------------
# Daemon handler
# ---------------------------------------------------------------------------


def _make_unused_state(
    *,
    has_unused: bool = True,
) -> DaemonState:
    """Build state with passes and resources for unused targets testing."""
    ctrl = rd.MockReplayController()
    ctrl._actions = [
        rd.ActionDescription(
            eventId=1,
            flags=rd.ActionFlags.BeginPass,
            children=[
                rd.ActionDescription(
                    eventId=5,
                    flags=rd.ActionFlags.Drawcall,
                    _name="Draw #5",
                ),
            ],
            _name="Shadow",
        ),
        rd.ActionDescription(eventId=10, flags=rd.ActionFlags.EndPass, _name="End"),
        rd.ActionDescription(
            eventId=11,
            flags=rd.ActionFlags.BeginPass,
            children=[
                rd.ActionDescription(
                    eventId=15,
                    flags=rd.ActionFlags.Drawcall,
                    _name="Draw #15",
                ),
            ],
            _name="Main",
        ),
        rd.ActionDescription(eventId=20, flags=rd.ActionFlags.EndPass, _name="End"),
    ]
    res_shadow = rd.ResourceDescription(
        resourceId=rd.ResourceId(97), name="ShadowMap", type=rd.ResourceType.Texture
    )
    res_sc = rd.ResourceDescription(
        resourceId=rd.ResourceId(200),
        name="Swapchain",
        type=rd.ResourceType.SwapchainImage,
    )
    ctrl._resources = [res_shadow, res_sc]

    if has_unused:
        ctrl._usage_map = {
            97: [rd.EventUsage(eventId=5, usage=rd.ResourceUsage.ColorTarget)],
            200: [rd.EventUsage(eventId=15, usage=rd.ResourceUsage.ColorTarget)],
        }
    else:
        ctrl._usage_map = {
            97: [
                rd.EventUsage(eventId=5, usage=rd.ResourceUsage.ColorTarget),
                rd.EventUsage(eventId=15, usage=rd.ResourceUsage.PS_Resource),
            ],
            200: [rd.EventUsage(eventId=15, usage=rd.ResourceUsage.ColorTarget)],
        }

    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.res_names = {int(r.resourceId): r.name for r in ctrl._resources}
    state.res_types = {int(r.resourceId): r.type.name for r in ctrl._resources}
    state.res_rid_map = {int(r.resourceId): r for r in ctrl._resources}
    return state


class TestHandlerHappy:
    def test_has_unused(self) -> None:
        state = _make_unused_state(has_unused=True)
        resp, running = _handle_request(rpc_request("unused_targets"), state)
        assert running
        assert "unused" in resp["result"]
        assert len(resp["result"]["unused"]) == 1
        assert resp["result"]["unused"][0]["id"] == 97

    def test_no_unused(self) -> None:
        state = _make_unused_state(has_unused=False)
        resp, running = _handle_request(rpc_request("unused_targets"), state)
        assert running
        assert resp["result"]["unused"] == []


class TestHandlerNoAdapter:
    def test_error(self) -> None:
        state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(rpc_request("unused_targets"), state)
        assert resp["error"]["code"] == -32002


class TestHandlerSchema:
    def test_response_structure(self) -> None:
        state = _make_unused_state(has_unused=True)
        resp, _ = _handle_request(rpc_request("unused_targets"), state)
        r = resp["result"]
        assert "unused" in r
        assert "waves" in r
        assert isinstance(r["waves"], int)
        for entry in r["unused"]:
            assert set(entry.keys()) == {"id", "name", "written_by", "wave"}
            assert isinstance(entry["id"], int)
            assert isinstance(entry["written_by"], list)
            assert isinstance(entry["wave"], int)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_UNUSED_RESPONSE: dict[str, Any] = {
    "unused": [
        {"id": 97, "name": "ShadowMap", "written_by": ["Shadow"], "wave": 1},
        {"id": 200, "name": "TempRT", "written_by": ["GBuffer", "Lighting"], "wave": 2},
    ],
    "waves": 2,
}

_EMPTY_RESPONSE: dict[str, Any] = {"unused": [], "waves": 0}


def _patch(monkeypatch: Any, response: dict[str, Any]) -> None:
    def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        return response

    monkeypatch.setattr(unused_mod, "call", fake_call)


class TestCliTsv:
    def test_tsv_output(self, monkeypatch: Any) -> None:
        _patch(monkeypatch, _UNUSED_RESPONSE)
        result = CliRunner().invoke(main, ["unused-targets"])
        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert lines[0] == "ID\tNAME\tWRITTEN_BY\tWAVE"
        assert "97\tShadowMap\tShadow\t1" == lines[1]
        assert "GBuffer,Lighting" in lines[2]

    def test_tsv_no_header(self, monkeypatch: Any) -> None:
        _patch(monkeypatch, _UNUSED_RESPONSE)
        result = CliRunner().invoke(main, ["unused-targets", "--no-header"])
        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert lines[0].startswith("97")

    def test_tsv_empty(self, monkeypatch: Any) -> None:
        _patch(monkeypatch, _EMPTY_RESPONSE)
        result = CliRunner().invoke(main, ["unused-targets"])
        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert lines == ["ID\tNAME\tWRITTEN_BY\tWAVE"]


class TestCliJson:
    def test_json_output(self, monkeypatch: Any) -> None:
        _patch(monkeypatch, _UNUSED_RESPONSE)
        result = CliRunner().invoke(main, ["unused-targets", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "unused" in data
        assert data["waves"] == 2
        assert len(data["unused"]) == 2

    def test_json_empty(self, monkeypatch: Any) -> None:
        _patch(monkeypatch, _EMPTY_RESPONSE)
        result = CliRunner().invoke(main, ["unused-targets", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["unused"] == []


class TestCliQuiet:
    def test_quiet_output(self, monkeypatch: Any) -> None:
        _patch(monkeypatch, _UNUSED_RESPONSE)
        result = CliRunner().invoke(main, ["unused-targets", "-q"])
        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert lines == ["97", "200"]

    def test_quiet_empty(self, monkeypatch: Any) -> None:
        _patch(monkeypatch, _EMPTY_RESPONSE)
        result = CliRunner().invoke(main, ["unused-targets", "-q"])
        assert result.exit_code == 0
        assert result.output.strip() == ""


class TestCliRegistered:
    def test_help(self) -> None:
        result = CliRunner().invoke(main, ["unused-targets", "--help"])
        assert result.exit_code == 0
        assert "render targets" in result.output.lower() or "unused" in result.output.lower()

    def test_in_main_help(self) -> None:
        result = CliRunner().invoke(main, ["--help"])
        assert "unused-targets" in result.output
