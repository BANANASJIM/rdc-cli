"""Tests for draws daemon handler: pass filter call-site and summary stats (phase2.7 Fixes 2+3)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import mock_renderdoc as rd
from conftest import make_daemon_state, rpc_request

from rdc.daemon_server import _handle_request
from rdc.services.query_service import FlatAction


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
        for i in range(2, 12)
    ]
    end = rd.ActionDescription(
        eventId=12,
        flags=rd.ActionFlags.EndPass | rd.ActionFlags.PassBoundary,
        _name="EndPass",
    )
    return [begin, *draws, end]


def _make_state(actions: list | None = None) -> Any:
    ctrl = rd.MockReplayController()
    ctrl._actions = actions or _build_actions()
    return make_daemon_state(
        capture="x.rdc",
        ctrl=ctrl,
        structured_file=SimpleNamespace(chunks=[]),
    )


# ---------------------------------------------------------------------------
# Fix 2 call-site: _handle_draws passes actions+sf to filter_by_pass
# ---------------------------------------------------------------------------


class TestDrawsPassFilterCallSite:
    def test_filter_by_pass_receives_actions(self) -> None:
        """filter_by_pass is called with non-None actions when pass param is set."""
        state = _make_state()
        captured: dict[str, Any] = {}

        def _spy_fbp(flat, pass_name, actions=None, sf=None):
            captured["actions"] = actions
            captured["sf"] = sf
            return flat  # pass everything through

        with patch("rdc.services.query_service.filter_by_pass", side_effect=_spy_fbp):
            _handle_request(rpc_request("draws", {"pass": "Colour Pass #1"}), state)

        assert "actions" in captured, "filter_by_pass was not called"
        assert captured["actions"] is not None
        assert captured["sf"] is not None

    def test_filter_by_pass_not_called_without_pass_param(self) -> None:
        """filter_by_pass is not called when no pass param is supplied."""
        state = _make_state()
        call_count = 0

        def _spy_fbp(flat, pass_name, actions=None, sf=None):
            nonlocal call_count
            call_count += 1
            return flat

        with patch("rdc.services.query_service.filter_by_pass", side_effect=_spy_fbp):
            _handle_request(rpc_request("draws"), state)

        assert call_count == 0


# ---------------------------------------------------------------------------
# Fix 3: summary reflects filtered flat, not all_flat
# ---------------------------------------------------------------------------


def _make_flat(n: int, flags: int = 0x0002) -> list[FlatAction]:
    return [FlatAction(eid=i, name=f"d{i}", flags=flags) for i in range(n)]


class TestDrawsSummaryFiltered:
    def test_pass_filter_reduces_summary(self) -> None:
        """After pass filter yields 3 draws, summary starts with '3 draw calls'."""
        all_flat = _make_flat(10)
        filtered = _make_flat(3)

        state = _make_state()

        with (
            patch("rdc.daemon_server._get_flat_actions", return_value=all_flat),
            patch("rdc.services.query_service.filter_by_pass", return_value=filtered),
        ):
            resp, _ = _handle_request(rpc_request("draws", {"pass": "SomePass"}), state)

        summary = resp["result"]["summary"]
        assert summary.startswith("3 draw calls"), f"Got: {summary!r}"

    def test_no_filter_summary_equals_total(self) -> None:
        """No pass filter: summary draw count equals total draw actions."""
        all_flat = _make_flat(7)
        state = _make_state()

        with patch("rdc.daemon_server._get_flat_actions", return_value=all_flat):
            resp, _ = _handle_request(rpc_request("draws"), state)

        summary = resp["result"]["summary"]
        assert summary.startswith("7 draw calls"), f"Got: {summary!r}"

    def test_summary_count_matches_draws_list(self) -> None:
        """Summary count equals len(draws) in the response."""
        state = _make_state()
        resp, _ = _handle_request(rpc_request("draws"), state)
        result = resp["result"]
        draws = result["draws"]
        summary = result["summary"]
        expected_prefix = f"{len(draws)} draw calls"
        assert summary.startswith(expected_prefix), f"summary={summary!r}, draws={len(draws)}"

    def test_summary_includes_dispatches_and_clears(self) -> None:
        """Summary format includes dispatches and clears counts."""
        state = _make_state()
        resp, _ = _handle_request(rpc_request("draws"), state)
        summary = resp["result"]["summary"]
        assert "dispatches" in summary
        assert "clears" in summary

    def test_type_filter_does_not_affect_summary(self) -> None:
        """Summary is based on post-pass-filter all_flat, not post-type-filter flat."""
        # Build all_flat with 5 draws + 2 dispatches
        draws_flat = _make_flat(5, flags=0x0002)
        dispatch_flat = _make_flat(2, flags=0x0004)
        all_flat = draws_flat + dispatch_flat

        state = _make_state()
        with patch("rdc.daemon_server._get_flat_actions", return_value=all_flat):
            resp, _ = _handle_request(rpc_request("draws"), state)

        summary = resp["result"]["summary"]
        # 5 draws, 2 dispatches — summary must report all 5 draws, not 7
        assert summary.startswith("5 draw calls"), f"Got: {summary!r}"
        assert "2 dispatches" in summary
