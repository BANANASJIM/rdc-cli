from __future__ import annotations

import io

from rdc.formatters.json_fmt import write_json, write_jsonl
from rdc.formatters.tsv import escape_field, format_row, write_footer, write_tsv


class TestEscapeField:
    def test_none_returns_dash(self) -> None:
        assert escape_field(None) == "-"

    def test_empty_string_returns_dash(self) -> None:
        assert escape_field("") == "-"

    def test_normal_string_passes_through(self) -> None:
        assert escape_field("hello") == "hello"

    def test_integer_converted(self) -> None:
        assert escape_field(1200000) == "1200000"

    def test_tab_escaped(self) -> None:
        assert escape_field("a\tb") == "a\\tb"

    def test_newline_escaped(self) -> None:
        assert escape_field("a\nb") == "a\\nb"

    def test_both_tab_and_newline(self) -> None:
        assert escape_field("a\tb\nc") == "a\\tb\\nc"


class TestFormatRow:
    def test_basic_row(self) -> None:
        assert format_row([1, "hello", None]) == "1\thello\t-"

    def test_empty_row(self) -> None:
        assert format_row([]) == ""


class TestWriteTsv:
    def test_with_header(self) -> None:
        out = io.StringIO()
        write_tsv(
            [[1, "draw", 100], [2, "clear", None]],
            header=["EID", "TYPE", "COUNT"],
            out=out,
        )
        lines = out.getvalue().strip().split("\n")
        assert lines[0] == "EID\tTYPE\tCOUNT"
        assert lines[1] == "1\tdraw\t100"
        assert lines[2] == "2\tclear\t-"

    def test_no_header(self) -> None:
        out = io.StringIO()
        write_tsv(
            [[1, "draw"]],
            header=["EID", "TYPE"],
            no_header=True,
            out=out,
        )
        lines = out.getvalue().strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == "1\tdraw"

    def test_no_header_param_none(self) -> None:
        out = io.StringIO()
        write_tsv([[42]], out=out)
        assert out.getvalue().strip() == "42"


class TestWriteFooter:
    def test_footer_to_stderr(self) -> None:
        err = io.StringIO()
        write_footer("3 draw calls", err=err)
        assert err.getvalue() == "3 draw calls\n"


class TestJsonFormatters:
    def test_write_json(self) -> None:
        out = io.StringIO()
        write_json({"key": "value"}, out=out)
        assert '"key": "value"' in out.getvalue()

    def test_write_jsonl(self) -> None:
        out = io.StringIO()
        write_jsonl([{"a": 1}, {"b": 2}], out=out)
        lines = out.getvalue().strip().split("\n")
        assert len(lines) == 2
        assert '"a": 1' in lines[0]
        assert '"b": 2' in lines[1]
