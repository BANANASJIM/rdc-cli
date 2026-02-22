"""Tests for VFS formatter: render_ls and render_ls_long."""

from __future__ import annotations

from rdc.vfs.formatter import render_ls, render_ls_long


class TestRenderLsLong:
    def test_header_row(self) -> None:
        columns = ["NAME", "DRAWS", "DISPATCHES", "TRIANGLES"]
        result = render_ls_long([], columns)
        assert result == "NAME\tDRAWS\tDISPATCHES\tTRIANGLES"

    def test_data_rows(self) -> None:
        columns = ["EID", "NAME", "TYPE"]
        children = [
            {"eid": 42, "name": "draw1", "type": "DrawIndexed"},
            {"eid": 100, "name": "draw2", "type": "Draw"},
        ]
        result = render_ls_long(children, columns)
        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == "EID\tNAME\tTYPE"
        assert lines[1] == "42\tdraw1\tDrawIndexed"
        assert lines[2] == "100\tdraw2\tDraw"

    def test_none_field_becomes_dash(self) -> None:
        columns = ["NAME", "SIZE"]
        children = [{"name": "res1", "size": None}]
        result = render_ls_long(children, columns)
        lines = result.split("\n")
        assert lines[1] == "res1\t-"

    def test_missing_field_becomes_dash(self) -> None:
        columns = ["NAME", "SIZE"]
        children = [{"name": "res1"}]
        result = render_ls_long(children, columns)
        lines = result.split("\n")
        assert lines[1] == "res1\t-"

    def test_empty_children(self) -> None:
        columns = ["NAME", "TYPE"]
        result = render_ls_long([], columns)
        lines = result.split("\n")
        assert len(lines) == 1
        assert lines[0] == "NAME\tTYPE"


class TestRenderLsRegression:
    def test_render_ls_unchanged(self) -> None:
        children = [
            {"name": "info", "kind": "leaf"},
            {"name": "draws", "kind": "dir"},
        ]
        result = render_ls(children)
        assert result == "info\ndraws"

    def test_render_ls_classify(self) -> None:
        children = [
            {"name": "info", "kind": "leaf"},
            {"name": "draws", "kind": "dir"},
            {"name": "current", "kind": "alias"},
        ]
        result = render_ls(children, classify=True)
        assert "info" in result
        assert "draws/" in result
        assert "current@" in result
