"""Tests for resource comparison and renderers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from rdc.commands import diff as diff_mod
from rdc.commands.diff import diff_cmd
from rdc.diff.draws import DiffStatus
from rdc.diff.resources import (
    ResourceDiffRow,
    ResourceRecord,
    diff_resources,
    render_json,
    render_shortstat,
    render_tsv,
    render_unified,
)
from rdc.services.diff_service import DiffContext


def _rec(rid: int = 1, rtype: str = "Buffer", name: str = "MyBuf") -> ResourceRecord:
    return ResourceRecord(id=rid, type=rtype, name=name)


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


# ---------------------------------------------------------------------------
# diff_resources() — named matching
# ---------------------------------------------------------------------------


class TestDiffResourcesNamed:
    def test_both_empty(self) -> None:
        assert diff_resources([], []) == []

    def test_all_equal(self) -> None:
        a = [_rec(1, "Buffer", "VB"), _rec(2, "Texture2D", "Albedo")]
        b = [_rec(10, "Buffer", "VB"), _rec(20, "Texture2D", "Albedo")]
        rows = diff_resources(a, b)
        assert len(rows) == 2
        assert all(r.status == DiffStatus.EQUAL for r in rows)
        assert all(r.confidence == "high" for r in rows)

    def test_modified_type_changed(self) -> None:
        a = [_rec(1, "Texture2D", "SceneDepth")]
        b = [_rec(10, "Texture2DMS", "SceneDepth")]
        rows = diff_resources(a, b)
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.MODIFIED
        assert rows[0].type_a == "Texture2D"
        assert rows[0].type_b == "Texture2DMS"
        assert rows[0].confidence == "high"

    def test_added(self) -> None:
        a: list[ResourceRecord] = []
        b = [_rec(10, "Texture2D", "NewTex")]
        rows = diff_resources(a, b)
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.ADDED
        assert rows[0].type_a is None
        assert rows[0].type_b == "Texture2D"
        assert rows[0].name == "NewTex"

    def test_deleted(self) -> None:
        a = [_rec(1, "Buffer", "OldBuf")]
        b: list[ResourceRecord] = []
        rows = diff_resources(a, b)
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.DELETED
        assert rows[0].type_a == "Buffer"
        assert rows[0].type_b is None
        assert rows[0].name == "OldBuf"

    def test_mixed_batch(self) -> None:
        a = [
            _rec(1, "Buffer", "X"),
            _rec(2, "Texture2D", "Y"),
            _rec(3, "Buffer", "Z"),
        ]
        b = [
            _rec(10, "Buffer", "X"),
            _rec(20, "Texture2DMS", "Y"),
            _rec(30, "Buffer", "W"),
        ]
        rows = diff_resources(a, b)
        by_name = {r.name: r.status for r in rows}
        assert by_name["X"] == DiffStatus.EQUAL
        assert by_name["Y"] == DiffStatus.MODIFIED
        assert by_name["Z"] == DiffStatus.DELETED
        assert by_name["W"] == DiffStatus.ADDED

    def test_case_insensitive_match(self) -> None:
        a = [_rec(1, "Buffer", "MyBuffer")]
        b = [_rec(10, "Buffer", "mybuffer")]
        rows = diff_resources(a, b)
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.EQUAL

    def test_name_collision_no_crash(self) -> None:
        a = [_rec(1, "Buffer", "Dup"), _rec(2, "Buffer", "Dup")]
        b = [_rec(10, "Buffer", "Dup")]
        rows = diff_resources(a, b)
        # First Dup matched as named (EQUAL), second Dup goes to unnamed
        assert len(rows) >= 2
        statuses = {r.status for r in rows}
        assert DiffStatus.EQUAL in statuses


# ---------------------------------------------------------------------------
# diff_resources() — unnamed matching
# ---------------------------------------------------------------------------


class TestDiffResourcesUnnamed:
    def test_unnamed_same_type_same_count(self) -> None:
        a = [_rec(1, "Buffer", ""), _rec(2, "Buffer", "")]
        b = [_rec(10, "Buffer", ""), _rec(20, "Buffer", "")]
        rows = diff_resources(a, b)
        assert len(rows) == 2
        assert all(r.status == DiffStatus.EQUAL for r in rows)
        assert all(r.confidence == "low" for r in rows)

    def test_unnamed_count_mismatch(self) -> None:
        a = [_rec(1, "Texture2D", ""), _rec(2, "Texture2D", ""), _rec(3, "Texture2D", "")]
        b = [_rec(10, "Texture2D", ""), _rec(20, "Texture2D", "")]
        rows = diff_resources(a, b)
        assert len(rows) == 3
        equal_count = sum(1 for r in rows if r.status == DiffStatus.EQUAL)
        deleted_count = sum(1 for r in rows if r.status == DiffStatus.DELETED)
        assert equal_count == 2
        assert deleted_count == 1
        assert all(r.confidence == "low" for r in rows)

    def test_unnamed_type_absent_in_other(self) -> None:
        a = [_rec(1, "Buffer", "")]
        b: list[ResourceRecord] = []
        rows = diff_resources(a, b)
        assert len(rows) == 1
        assert rows[0].status == DiffStatus.DELETED
        assert rows[0].confidence == "low"

    def test_mixed_named_and_unnamed(self) -> None:
        a = [_rec(1, "Buffer", "VB"), _rec(2, "Buffer", "")]
        b = [_rec(10, "Buffer", "VB"), _rec(20, "Buffer", ""), _rec(30, "Texture2D", "")]
        rows = diff_resources(a, b)
        named_rows = [r for r in rows if r.name]
        unnamed_rows = [r for r in rows if not r.name]
        assert len(named_rows) == 1
        assert named_rows[0].status == DiffStatus.EQUAL
        assert named_rows[0].confidence == "high"
        # unnamed: 1 Buffer EQUAL + 1 Texture2D ADDED
        assert len(unnamed_rows) == 2
        assert all(r.confidence == "low" for r in unnamed_rows)


# ---------------------------------------------------------------------------
# render_tsv
# ---------------------------------------------------------------------------


class TestRenderTsv:
    def test_header_present(self) -> None:
        output = render_tsv([])
        assert output == "STATUS\tNAME\tTYPE_A\tTYPE_B"

    def test_header_false(self) -> None:
        output = render_tsv([], header=False)
        assert output == ""

    def test_equal_row(self) -> None:
        row = ResourceDiffRow(DiffStatus.EQUAL, "MyBuf", "Buffer", "Buffer", "high")
        output = render_tsv([row], header=False)
        assert output == "=\tMyBuf\tBuffer\tBuffer"

    def test_modified_row(self) -> None:
        row = ResourceDiffRow(DiffStatus.MODIFIED, "SceneDepth", "Texture2D", "Texture2DMS", "high")
        output = render_tsv([row], header=False)
        assert output == "~\tSceneDepth\tTexture2D\tTexture2DMS"

    def test_deleted_row(self) -> None:
        row = ResourceDiffRow(DiffStatus.DELETED, "Old", "Buffer", None, "high")
        output = render_tsv([row], header=False)
        assert output == "-\tOld\tBuffer\t"

    def test_added_row(self) -> None:
        row = ResourceDiffRow(DiffStatus.ADDED, "New", None, "Texture2D", "high")
        output = render_tsv([row], header=False)
        assert output == "+\tNew\t\tTexture2D"


# ---------------------------------------------------------------------------
# render_shortstat
# ---------------------------------------------------------------------------


class TestRenderShortstat:
    def test_all_statuses(self) -> None:
        rows = [
            ResourceDiffRow(DiffStatus.ADDED, "A", None, "Buffer", "high"),
            ResourceDiffRow(DiffStatus.ADDED, "B", None, "Buffer", "high"),
            ResourceDiffRow(DiffStatus.DELETED, "C", "Buffer", None, "high"),
            ResourceDiffRow(DiffStatus.MODIFIED, "D", "Tex2D", "Tex2DMS", "high"),
            ResourceDiffRow(DiffStatus.EQUAL, "E", "Buffer", "Buffer", "high"),
            ResourceDiffRow(DiffStatus.EQUAL, "F", "Buffer", "Buffer", "high"),
            ResourceDiffRow(DiffStatus.EQUAL, "G", "Buffer", "Buffer", "high"),
        ]
        assert render_shortstat(rows) == "2 added, 1 deleted, 1 modified, 3 unchanged"

    def test_all_equal(self) -> None:
        rows = [
            ResourceDiffRow(DiffStatus.EQUAL, "A", "Buffer", "Buffer", "high"),
            ResourceDiffRow(DiffStatus.EQUAL, "B", "Buffer", "Buffer", "high"),
        ]
        assert render_shortstat(rows) == "0 added, 0 deleted, 0 modified, 2 unchanged"


# ---------------------------------------------------------------------------
# render_json
# ---------------------------------------------------------------------------


class TestRenderJson:
    def test_schema(self) -> None:
        row = ResourceDiffRow(DiffStatus.MODIFIED, "SceneDepth", "Texture2D", "Texture2DMS", "high")
        data = json.loads(render_json([row]))
        assert isinstance(data, list)
        assert len(data) == 1
        obj = data[0]
        assert obj["status"] == "~"
        assert obj["name"] == "SceneDepth"
        assert obj["type_a"] == "Texture2D"
        assert obj["type_b"] == "Texture2DMS"
        assert obj["confidence"] == "high"

    def test_null_for_added(self) -> None:
        row = ResourceDiffRow(DiffStatus.ADDED, "New", None, "Texture2D", "high")
        data = json.loads(render_json([row]))
        assert data[0]["type_a"] is None
        assert data[0]["status"] == "+"

    def test_all_keys_present(self) -> None:
        row = ResourceDiffRow(DiffStatus.EQUAL, "X", "Buffer", "Buffer", "low")
        data = json.loads(render_json([row]))
        required = {"status", "name", "type_a", "type_b", "confidence"}
        assert required == set(data[0].keys())

    def test_empty(self) -> None:
        assert json.loads(render_json([])) == []


# ---------------------------------------------------------------------------
# render_unified
# ---------------------------------------------------------------------------


class TestRenderUnified:
    def test_header_lines(self) -> None:
        output = render_unified([], "a.rdc", "b.rdc")
        assert output.startswith("--- a/a.rdc\n+++ b/b.rdc")

    def test_equal_line(self) -> None:
        row = ResourceDiffRow(DiffStatus.EQUAL, "MyBuf", "Buffer", "Buffer", "high")
        output = render_unified([row], "a.rdc", "b.rdc")
        lines = output.split("\n")
        assert lines[2] == " MyBuf Buffer"

    def test_modified_lines(self) -> None:
        row = ResourceDiffRow(DiffStatus.MODIFIED, "SceneDepth", "Texture2D", "Texture2DMS", "high")
        output = render_unified([row], "a.rdc", "b.rdc")
        lines = output.split("\n")
        assert lines[2] == "-SceneDepth Texture2D"
        assert lines[3] == "+SceneDepth Texture2DMS"

    def test_deleted_line(self) -> None:
        row = ResourceDiffRow(DiffStatus.DELETED, "Old", "Buffer", None, "high")
        output = render_unified([row], "a.rdc", "b.rdc")
        lines = output.split("\n")
        assert lines[2] == "-Old Buffer"

    def test_added_line(self) -> None:
        row = ResourceDiffRow(DiffStatus.ADDED, "New", None, "Texture2D", "high")
        output = render_unified([row], "a.rdc", "b.rdc")
        lines = output.split("\n")
        assert lines[2] == "+New Texture2D"


# ---------------------------------------------------------------------------
# CLI dispatch tests
# ---------------------------------------------------------------------------


def _rpc_response(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"result": {"rows": rows}}


class TestCliResources:
    def _setup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        resp_a: dict[str, object] | None = None,
        resp_b: dict[str, object] | None = None,
        err: str = "",
    ) -> tuple[Path, Path]:
        a = tmp_path / "a.rdc"
        b = tmp_path / "b.rdc"
        a.touch()
        b.touch()
        ctx = _make_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)
        monkeypatch.setattr(diff_mod, "query_both", lambda *a, **kw: (resp_a, resp_b, err))
        return a, b

    def test_resources_no_longer_stub(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = self._setup(
            monkeypatch,
            tmp_path,
            resp_a=_rpc_response([]),
            resp_b=_rpc_response([]),
        )
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--resources"])
        assert "not yet implemented" not in (result.output or "").lower()

    def test_exit_0_no_differences(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        rows = [{"id": 1, "type": "Buffer", "name": "VB"}]
        a, b = self._setup(
            monkeypatch,
            tmp_path,
            resp_a=_rpc_response(rows),
            resp_b=_rpc_response(rows),
        )
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--resources"])
        assert result.exit_code == 0

    def test_exit_1_differences_found(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        a, b = self._setup(
            monkeypatch,
            tmp_path,
            resp_a=_rpc_response([{"id": 1, "type": "Buffer", "name": "X"}]),
            resp_b=_rpc_response([{"id": 10, "type": "Texture2D", "name": "Y"}]),
        )
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--resources"])
        assert result.exit_code == 1

    def test_exit_2_both_failed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = self._setup(
            monkeypatch,
            tmp_path,
            resp_a=None,
            resp_b=None,
            err="both daemons failed",
        )
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--resources"])
        assert result.exit_code == 2
        assert "both daemons failed" in result.output

    def test_exit_2_one_side_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = self._setup(
            monkeypatch,
            tmp_path,
            resp_a=_rpc_response([]),
            resp_b=None,
        )
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--resources"])
        assert result.exit_code == 2

    def test_default_tsv_output(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = self._setup(
            monkeypatch,
            tmp_path,
            resp_a=_rpc_response([{"id": 1, "type": "Buffer", "name": "VB"}]),
            resp_b=_rpc_response([{"id": 10, "type": "Buffer", "name": "VB"}]),
        )
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--resources"])
        assert "STATUS" in result.output
        assert "=" in result.output

    def test_shortstat(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = self._setup(
            monkeypatch,
            tmp_path,
            resp_a=_rpc_response([{"id": 1, "type": "Buffer", "name": "VB"}]),
            resp_b=_rpc_response([{"id": 10, "type": "Buffer", "name": "VB"}]),
        )
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--resources", "--shortstat"])
        assert "added" in result.output
        assert "deleted" in result.output
        assert "modified" in result.output
        assert "unchanged" in result.output

    def test_json_flag(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = self._setup(
            monkeypatch,
            tmp_path,
            resp_a=_rpc_response([{"id": 1, "type": "Buffer", "name": "VB"}]),
            resp_b=_rpc_response([{"id": 10, "type": "Buffer", "name": "VB"}]),
        )
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--resources", "--json"])
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)

    def test_format_unified(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = self._setup(
            monkeypatch,
            tmp_path,
            resp_a=_rpc_response([{"id": 1, "type": "Buffer", "name": "VB"}]),
            resp_b=_rpc_response([{"id": 10, "type": "Buffer", "name": "VB"}]),
        )
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--resources", "--format", "unified"])
        assert result.output.startswith("--- a/")

    def test_no_header(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = self._setup(
            monkeypatch,
            tmp_path,
            resp_a=_rpc_response([{"id": 1, "type": "Buffer", "name": "VB"}]),
            resp_b=_rpc_response([{"id": 10, "type": "Buffer", "name": "VB"}]),
        )
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [str(a), str(b), "--resources", "--no-header"])
        first_line = result.output.strip().split("\n")[0]
        assert not first_line.startswith("STATUS")
