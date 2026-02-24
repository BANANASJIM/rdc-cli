"""Tests for Fix 1: draws PASS column uses friendly pass name."""

from __future__ import annotations

from types import SimpleNamespace

import mock_renderdoc as rd
from conftest import make_daemon_state, rpc_request

from rdc.daemon_server import _handle_request
from rdc.services.query_service import _build_pass_list, pass_name_for_eid
from rdc.vfs.tree_cache import build_vfs_skeleton


def _build_actions(pass_name: str = "vkCmdBeginRenderPass(C=Load)") -> list:
    begin = rd.ActionDescription(
        eventId=1,
        flags=rd.ActionFlags.BeginPass | rd.ActionFlags.PassBoundary,
        _name=pass_name,
    )
    draws = [
        rd.ActionDescription(
            eventId=i,
            flags=rd.ActionFlags.Drawcall,
            numIndices=3,
            _name=f"draw{i}",
        )
        for i in range(2, 5)
    ]
    end = rd.ActionDescription(
        eventId=5,
        flags=rd.ActionFlags.EndPass | rd.ActionFlags.PassBoundary,
        _name="EndPass",
    )
    return [begin, *draws, end]


def _make_state(actions: list | None = None):
    acts = actions or _build_actions()
    ctrl = rd.MockReplayController()
    ctrl._actions = acts
    sf = SimpleNamespace(chunks=[])
    state = make_daemon_state(capture="x.rdc", ctrl=ctrl, structured_file=sf)
    resources = state.adapter.get_resources()
    state.vfs_tree = build_vfs_skeleton(acts, resources, sf=sf)
    return state


class TestPassNameForEid:
    def test_eid_within_pass(self) -> None:
        actions = _build_actions()
        passes = _build_pass_list(actions)
        assert passes[0]["name"].startswith("Colour Pass #1")
        result = pass_name_for_eid(3, passes)
        assert result == passes[0]["name"]

    def test_eid_outside_pass(self) -> None:
        actions = _build_actions()
        passes = _build_pass_list(actions)
        result = pass_name_for_eid(999, passes)
        assert result == "-"

    def test_empty_pass_list(self) -> None:
        assert pass_name_for_eid(5, []) == "-"


class TestDrawsHandlerFriendlyName:
    def test_pass_column_is_friendly_name(self) -> None:
        state = _make_state()
        resp, _ = _handle_request(rpc_request("draws"), state)
        result = resp["result"]
        for d in result["draws"]:
            assert not d["pass"].startswith("vkCmd"), f"raw API name leaked: {d['pass']}"
            assert d["pass"].startswith("Colour Pass #") or d["pass"] == "-"

    def test_pass_column_matches_passes_output(self) -> None:
        state = _make_state()
        draws_resp, _ = _handle_request(rpc_request("draws"), state)
        passes_resp, _ = _handle_request(rpc_request("passes"), state)
        pass_names = {p["name"] for p in passes_resp["result"]["tree"]["passes"]}
        for d in draws_resp["result"]["draws"]:
            if d["pass"] != "-":
                assert d["pass"] in pass_names, f"{d['pass']} not in {pass_names}"

    def test_pass_filter_still_works(self) -> None:
        """Filtering by friendly pass name still returns results."""
        state = _make_state()
        passes_resp, _ = _handle_request(rpc_request("passes"), state)
        pass_name = passes_resp["result"]["tree"]["passes"][0]["name"]
        draws_resp, _ = _handle_request(rpc_request("draws", {"pass": pass_name}), state)
        assert len(draws_resp["result"]["draws"]) > 0
