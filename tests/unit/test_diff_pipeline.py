"""Unit tests for pipeline diff logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from rdc.commands import diff as diff_mod
from rdc.commands.diff import diff_cmd
from rdc.diff.alignment import DrawRecord
from rdc.diff.pipeline import (
    PIPE_SECTION_CALLS,
    PipeFieldDiff,
    build_draw_records,
    diff_pipeline_sections,
    find_aligned_pair,
    render_pipeline_json,
    render_pipeline_tsv,
)
from rdc.services.diff_service import DiffContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dr(
    eid: int = 1,
    marker: str = "GBuffer/Floor",
    draw_type: str = "Draw",
    **kw: Any,
) -> DrawRecord:
    return DrawRecord(
        eid=eid,
        draw_type=draw_type,
        marker_path=marker,
        triangles=kw.get("triangles", 3),
        instances=kw.get("instances", 1),
        pass_name=kw.get("pass_name", "GBuffer"),
        shader_hash=kw.get("shader_hash", ""),
        topology=kw.get("topology", ""),
    )


def _make_ctx() -> DiffContext:
    return DiffContext(
        session_id="aabbccddeeff",
        host="127.0.0.1",
        port_a=5000,
        port_b=5001,
        token_a="ta",
        token_b="tb",
        pid_a=100,
        pid_b=200,
        capture_a="a.rdc",
        capture_b="b.rdc",
    )


# ===========================================================================
# build_draw_records
# ===========================================================================


class TestBuildDrawRecords:
    def test_full_row(self) -> None:
        rows = build_draw_records(
            [
                {
                    "eid": 12,
                    "type": "Draw",
                    "marker": "GBuffer/Floor",
                    "triangles": 3,
                    "instances": 1,
                    "pass": "GBuffer",
                },
            ]
        )
        assert len(rows) == 1
        r = rows[0]
        assert r.eid == 12
        assert r.draw_type == "Draw"
        assert r.marker_path == "GBuffer/Floor"
        assert r.triangles == 3
        assert r.instances == 1
        assert r.pass_name == "GBuffer"
        assert r.shader_hash == ""
        assert r.topology == ""

    def test_missing_marker(self) -> None:
        raw = [{"eid": 1, "type": "Draw", "triangles": 3, "instances": 1, "pass": ""}]
        rows = build_draw_records(raw)
        assert rows[0].marker_path == "-"

    def test_empty_list(self) -> None:
        assert build_draw_records([]) == []


# ===========================================================================
# find_aligned_pair
# ===========================================================================


class TestFindAlignedPair:
    def test_marker_found_both(self) -> None:
        a, b = _dr(eid=10), _dr(eid=20)
        aligned = [(a, b)]
        pair, warning = find_aligned_pair(aligned, "GBuffer/Floor")
        assert pair == (a, b)
        assert warning == ""

    def test_marker_only_in_a(self) -> None:
        a = _dr(eid=10)
        aligned: list[tuple[DrawRecord | None, DrawRecord | None]] = [(a, None)]
        pair, msg = find_aligned_pair(aligned, "GBuffer/Floor")
        assert pair is None
        assert "capture B" in msg

    def test_marker_only_in_b(self) -> None:
        b = _dr(eid=20)
        aligned: list[tuple[DrawRecord | None, DrawRecord | None]] = [(None, b)]
        pair, msg = find_aligned_pair(aligned, "GBuffer/Floor")
        assert pair is None
        assert "capture A" in msg

    def test_marker_absent(self) -> None:
        a, b = _dr(eid=10, marker="Other"), _dr(eid=20, marker="Other")
        aligned = [(a, b)]
        pair, msg = find_aligned_pair(aligned, "GBuffer/Floor")
        assert pair is None
        assert "not found" in msg

    def test_repeated_marker_no_index(self) -> None:
        a1, b1 = _dr(eid=10), _dr(eid=20)
        a2, b2 = _dr(eid=30), _dr(eid=40)
        aligned = [(a1, b1), (a2, b2)]
        pair, warning = find_aligned_pair(aligned, "GBuffer/Floor")
        assert pair == (a1, b1)
        assert "appears 2 times" in warning

    def test_repeated_marker_index_1(self) -> None:
        a1, b1 = _dr(eid=10), _dr(eid=20)
        a2, b2 = _dr(eid=30), _dr(eid=40)
        aligned = [(a1, b1), (a2, b2)]
        pair, warning = find_aligned_pair(aligned, "GBuffer/Floor[1]")
        assert pair == (a2, b2)
        assert warning == ""

    def test_repeated_marker_index_out_of_range(self) -> None:
        a1, b1 = _dr(eid=10), _dr(eid=20)
        aligned = [(a1, b1)]
        pair, msg = find_aligned_pair(aligned, "GBuffer/Floor[99]")
        assert pair is None
        assert "out of range" in msg


# ===========================================================================
# diff_pipeline_sections
# ===========================================================================


class TestDiffPipelineSections:
    def test_identical_flat(self) -> None:
        ra = {"result": {"topology": "TriangleList", "eid": 10}}
        rb = {"result": {"topology": "TriangleList", "eid": 20}}
        diffs = diff_pipeline_sections([ra], [rb], section_names=["topology"])
        assert len(diffs) == 1
        assert diffs[0].field == "topology"
        assert not diffs[0].changed

    def test_scalar_changed(self) -> None:
        ra = {"result": {"topology": "TriangleList", "eid": 10}}
        rb = {"result": {"topology": "TriangleStrip", "eid": 20}}
        diffs = diff_pipeline_sections([ra], [rb], section_names=["topology"])
        changed = [d for d in diffs if d.changed]
        assert len(changed) == 1
        assert changed[0].value_a == "TriangleList"
        assert changed[0].value_b == "TriangleStrip"

    def test_eid_stripped(self) -> None:
        ra = {"result": {"topology": "TriangleList", "eid": 10}}
        rb = {"result": {"topology": "TriangleList", "eid": 20}}
        diffs = diff_pipeline_sections([ra], [rb], section_names=["topology"])
        assert all(d.field != "eid" for d in diffs)

    def test_nested_stencil(self) -> None:
        ra = {
            "result": {
                "eid": 10,
                "front": {"failOperation": "Keep", "passOperation": "Replace"},
                "back": {"failOperation": "Keep", "passOperation": "Keep"},
            }
        }
        rb = {
            "result": {
                "eid": 20,
                "front": {"failOperation": "Zero", "passOperation": "Replace"},
                "back": {"failOperation": "Keep", "passOperation": "Keep"},
            }
        }
        diffs = diff_pipeline_sections([ra], [rb], section_names=["stencil"])
        changed = [d for d in diffs if d.changed]
        assert len(changed) == 1
        assert changed[0].field == "front.failOperation"
        assert changed[0].value_a == "Keep"
        assert changed[0].value_b == "Zero"

    def test_list_element_differs(self) -> None:
        ra = {"result": {"eid": 10, "blends": [{"enabled": True, "srcBlend": "One"}]}}
        rb = {"result": {"eid": 20, "blends": [{"enabled": False, "srcBlend": "One"}]}}
        diffs = diff_pipeline_sections([ra], [rb], section_names=["blend"])
        changed = [d for d in diffs if d.changed]
        assert len(changed) == 1
        assert changed[0].field == "blends[0].enabled"

    def test_list_length_mismatch(self) -> None:
        ra = {"result": {"eid": 10, "blends": [{"enabled": True}, {"enabled": False}]}}
        rb = {"result": {"eid": 20, "blends": [{"enabled": True}]}}
        diffs = diff_pipeline_sections([ra], [rb], section_names=["blend"])
        count_diff = [d for d in diffs if d.field == "count"]
        assert len(count_diff) == 1
        assert count_diff[0].value_a == 2
        assert count_diff[0].value_b == 1
        assert count_diff[0].changed

    def test_section_none_skipped(self) -> None:
        diffs = diff_pipeline_sections([None], [{"result": {"x": 1}}], section_names=["topology"])
        assert diffs == []

    def test_all_identical(self) -> None:
        ra = {"result": {"x": 1, "y": 2, "eid": 10}}
        rb = {"result": {"x": 1, "y": 2, "eid": 20}}
        diffs = diff_pipeline_sections([ra], [rb], section_names=["viewport"])
        assert all(not d.changed for d in diffs)


# ===========================================================================
# Renderers
# ===========================================================================


class TestRenderPipelineTsv:
    def test_changed_only(self) -> None:
        diffs = [
            PipeFieldDiff("topology", "topology", "TriangleList", "TriangleStrip", changed=True),
            PipeFieldDiff("viewport", "width", 800, 800, changed=False),
        ]
        output = render_pipeline_tsv(diffs)
        lines = output.strip().split("\n")
        assert lines[0] == "SECTION\tFIELD\tA\tB"
        assert len(lines) == 2
        assert "<- changed" in lines[1]

    def test_verbose(self) -> None:
        diffs = [
            PipeFieldDiff("topology", "topology", "TriangleList", "TriangleStrip", changed=True),
            PipeFieldDiff("viewport", "width", 800, 800, changed=False),
        ]
        output = render_pipeline_tsv(diffs, verbose=True)
        lines = output.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "<- changed" in lines[1]
        assert "<- changed" not in lines[2]

    def test_no_header(self) -> None:
        diffs = [PipeFieldDiff("topology", "topology", "A", "B", changed=True)]
        output = render_pipeline_tsv(diffs, header=False)
        assert not output.startswith("SECTION")

    def test_no_changes(self) -> None:
        diffs = [PipeFieldDiff("topology", "topology", "Same", "Same", changed=False)]
        output = render_pipeline_tsv(diffs)
        assert output == "SECTION\tFIELD\tA\tB"

    def test_no_changes_no_header(self) -> None:
        diffs = [PipeFieldDiff("topology", "topology", "Same", "Same", changed=False)]
        output = render_pipeline_tsv(diffs, header=False)
        assert output == ""


class TestRenderPipelineJson:
    def test_valid_json(self) -> None:
        diffs = [
            PipeFieldDiff("topology", "topology", "TriangleList", "TriangleStrip", changed=True),
        ]
        data = json.loads(render_pipeline_json(diffs))
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["section"] == "topology"
        assert data[0]["field"] == "topology"
        assert data[0]["value_a"] == "TriangleList"
        assert data[0]["value_b"] == "TriangleStrip"
        assert data[0]["changed"] is True

    def test_empty_list(self) -> None:
        assert json.loads(render_pipeline_json([])) == []


# ===========================================================================
# CLI wiring tests
# ===========================================================================


def _mock_draws_response(draws: list[dict[str, Any]]) -> dict[str, Any]:
    return {"result": {"draws": draws, "summary": "test"}}


def _basic_draws() -> list[dict[str, Any]]:
    return [
        {
            "eid": 10,
            "type": "Draw",
            "marker": "GBuffer/Floor",
            "triangles": 3,
            "instances": 1,
            "pass": "GBuffer",
        },
    ]


def _pipe_result(section_data: dict[str, Any]) -> dict[str, Any]:
    return {"result": section_data}


class TestDiffPipelineCli:
    def _setup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        draws_a: list[dict[str, Any]] | None = None,
        draws_b: list[dict[str, Any]] | None = None,
        pipe_results_a: list[dict[str, Any] | None] | None = None,
        pipe_results_b: list[dict[str, Any] | None] | None = None,
        query_both_fail: bool = False,
    ) -> tuple[Path, Path]:
        a = tmp_path / "a.rdc"
        b = tmp_path / "b.rdc"
        a.touch()
        b.touch()

        ctx = _make_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

        if query_both_fail:
            fail = (None, None, "both daemons failed")
            monkeypatch.setattr(diff_mod, "query_both", lambda *a, **kw: fail)
        else:
            resp_a = _mock_draws_response(draws_a or _basic_draws())
            resp_b = _mock_draws_response(draws_b or _basic_draws())
            monkeypatch.setattr(diff_mod, "query_both", lambda *a, **kw: (resp_a, resp_b, ""))

        n = len(PIPE_SECTION_CALLS)
        default_results = [_pipe_result({"topology": "TriangleList", "eid": 10})] * n
        ra = pipe_results_a if pipe_results_a is not None else default_results
        rb = pipe_results_b if pipe_results_b is not None else default_results
        monkeypatch.setattr(diff_mod, "query_each_sync", lambda *a, **kw: (ra, rb, ""))

        return a, b

    def test_pipeline_exit_0(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = self._setup(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--pipeline", "GBuffer/Floor"])
        assert result.exit_code == 0

    def test_pipeline_json(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = self._setup(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--pipeline", "GBuffer/Floor", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_pipeline_verbose(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = self._setup(monkeypatch, tmp_path)
        runner = CliRunner()
        args = [str(a), str(b), "--pipeline", "GBuffer/Floor", "--verbose"]
        result = runner.invoke(diff_cmd, args)
        assert result.exit_code == 0
        # verbose mode shows all fields including unchanged
        assert "SECTION" in result.output

    def test_pipeline_no_header(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = self._setup(monkeypatch, tmp_path)
        runner = CliRunner()
        args = [str(a), str(b), "--pipeline", "GBuffer/Floor", "--no-header"]
        result = runner.invoke(diff_cmd, args)
        assert result.exit_code == 0
        assert "SECTION" not in result.output

    def test_pipeline_marker_not_found(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = self._setup(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--pipeline", "NoSuchMarker"])
        assert result.exit_code == 2
        assert "not found" in result.output

    def test_pipeline_draws_fetch_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = self._setup(monkeypatch, tmp_path, query_both_fail=True)
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--pipeline", "GBuffer/Floor"])
        assert result.exit_code == 2
        assert "both daemons failed" in result.output

    def test_pipeline_section_rpc_partial_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        n = len(PIPE_SECTION_CALLS)
        # First section fails, rest succeed
        pipe_a: list[dict[str, Any] | None] = [None] + [_pipe_result({"x": 1, "eid": 10})] * (n - 1)
        pipe_b: list[dict[str, Any] | None] = [None] + [_pipe_result({"x": 1, "eid": 20})] * (n - 1)
        a, b = self._setup(monkeypatch, tmp_path, pipe_results_a=pipe_a, pipe_results_b=pipe_b)
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--pipeline", "GBuffer/Floor"])
        assert result.exit_code == 0
        assert "skipped" in result.output

    def test_pipeline_differences_exit_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        n = len(PIPE_SECTION_CALLS)
        pipe_a = [_pipe_result({"topology": "TriangleList", "eid": 10})] * n
        pipe_b = [_pipe_result({"topology": "TriangleStrip", "eid": 20})] * n
        a, b = self._setup(monkeypatch, tmp_path, pipe_results_a=pipe_a, pipe_results_b=pipe_b)
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--pipeline", "GBuffer/Floor"])
        assert result.exit_code == 1
        assert "<- changed" in result.output


# ===========================================================================
# query_each_sync unit tests
# ===========================================================================


class TestQueryEachSync:
    def test_ordering(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.services import diff_service
        from rdc.services.diff_service import query_each_sync

        def mock_send(host: str, port: int, payload: dict, **kw: object) -> dict:
            return {"result": {"method": payload["method"], "port": port}}

        monkeypatch.setattr(diff_service, "send_request", mock_send)

        ctx = _make_ctx()
        calls_a = [("m1", {"x": 1}), ("m2", {"x": 2})]
        calls_b = [("m3", {"x": 3})]
        ra, rb, err = query_each_sync(ctx, calls_a, calls_b)
        assert err == ""
        assert len(ra) == 2
        assert len(rb) == 1
        assert ra[0] is not None and ra[0]["result"]["method"] == "m1"
        assert ra[1] is not None and ra[1]["result"]["method"] == "m2"
        assert rb[0] is not None and rb[0]["result"]["method"] == "m3"

    def test_partial_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.services import diff_service
        from rdc.services.diff_service import query_each_sync

        def mock_send(host: str, port: int, payload: dict, **kw: object) -> dict:
            if port == 5000 and payload["method"] == "m2":
                raise ConnectionRefusedError
            return {"result": {"ok": True}}

        monkeypatch.setattr(diff_service, "send_request", mock_send)

        ctx = _make_ctx()
        calls_a = [("m1", {}), ("m2", {})]
        calls_b = [("m1", {})]
        ra, rb, err = query_each_sync(ctx, calls_a, calls_b)
        assert ra[0] is not None
        assert ra[1] is None
        assert rb[0] is not None

    def test_all_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.services import diff_service
        from rdc.services.diff_service import query_each_sync

        mock = MagicMock(side_effect=ConnectionRefusedError)
        monkeypatch.setattr(diff_service, "send_request", mock)

        ctx = _make_ctx()
        ra, rb, err = query_each_sync(ctx, [("m1", {})], [("m1", {})])
        assert ra[0] is None
        assert rb[0] is None
        assert err != ""
