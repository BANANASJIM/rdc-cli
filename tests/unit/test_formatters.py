from __future__ import annotations

import io

from click.testing import CliRunner

from rdc.cli import main
from rdc.formatters.json_fmt import write_json, write_jsonl
from rdc.formatters.options import render_list
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


def _flag(name: str) -> None:
    raise AssertionError(f"unexpected branch: {name}")


class TestRenderList:
    """Cover each branch of the json/jsonl/quiet/table ladder."""

    _ROWS = [{"eid": 1, "type": "Draw"}, {"eid": 2, "type": "Clear"}]

    def test_json_branch(self) -> None:
        out = io.StringIO()
        render_list(
            self._ROWS,
            use_json=True,
            use_jsonl=False,
            quiet=False,
            quiet_key="eid",
            table=lambda: _flag("table"),
            out=out,
        )
        assert out.getvalue() == (
            '[\n  {\n    "eid": 1,\n    "type": "Draw"\n  },\n'
            '  {\n    "eid": 2,\n    "type": "Clear"\n  }\n]\n'
        )

    def test_jsonl_branch(self) -> None:
        out = io.StringIO()
        render_list(
            self._ROWS,
            use_json=False,
            use_jsonl=True,
            quiet=False,
            quiet_key="eid",
            table=lambda: _flag("table"),
            out=out,
        )
        assert out.getvalue() == '{"eid": 1, "type": "Draw"}\n{"eid": 2, "type": "Clear"}\n'

    def test_quiet_branch(self) -> None:
        out = io.StringIO()
        render_list(
            self._ROWS,
            use_json=False,
            use_jsonl=False,
            quiet=True,
            quiet_key="eid",
            table=lambda: _flag("table"),
            out=out,
        )
        assert out.getvalue() == "1\n2\n"

    def test_table_branch(self) -> None:
        calls: list[str] = []
        render_list(
            self._ROWS,
            use_json=False,
            use_jsonl=False,
            quiet=False,
            quiet_key="eid",
            table=lambda: calls.append("table"),
        )
        assert calls == ["table"]

    def test_json_wins_over_jsonl_and_quiet(self) -> None:
        out = io.StringIO()
        render_list(
            [{"eid": 1}],
            use_json=True,
            use_jsonl=True,
            quiet=True,
            quiet_key="eid",
            table=lambda: _flag("table"),
            out=out,
        )
        assert out.getvalue().startswith("[")

    def test_quiet_missing_key_uses_default_not_keyerror(self) -> None:
        """A row missing the quiet key must yield the default, never KeyError."""
        out = io.StringIO()
        render_list(
            [{"type": "Draw"}],
            use_json=False,
            use_jsonl=False,
            quiet=True,
            quiet_key="eid",
            quiet_default="",
            table=lambda: _flag("table"),
            out=out,
        )
        assert out.getvalue() == "\n"

    def test_quiet_custom_default(self) -> None:
        out = io.StringIO()
        render_list(
            [{"type": "Draw"}],
            use_json=False,
            use_jsonl=False,
            quiet=True,
            quiet_key="eid",
            quiet_default=0,
            table=lambda: _flag("table"),
            out=out,
        )
        assert out.getvalue() == "0\n"


def _patch(monkeypatch, mod_name: str, response: dict) -> None:
    mod = __import__(f"rdc.commands.{mod_name}", fromlist=["call"])
    monkeypatch.setattr(mod, "call", lambda method, params=None: response)


_EVENTS = {
    "events": [
        {"eid": 1, "type": "Draw", "name": "vkCmdDraw"},
        {"eid": 2, "type": "Dispatch", "name": "vkCmdDispatch"},
    ]
}
_RESOURCES = {
    "rows": [
        {"id": 10, "type": "Texture", "name": "albedo"},
        {"id": 20, "type": "Buffer", "name": "verts"},
    ]
}
_COUNTERS = {
    "counters": [
        {
            "id": 1,
            "name": "GPUDuration",
            "unit": "Seconds",
            "type": "Float",
            "category": "Built-in",
        },
        {
            "id": 8,
            "name": "VSInvocations",
            "unit": "Absolute",
            "type": "UInt",
            "category": "Built-in",
        },
    ]
}


class TestListGoldenParity:
    """Byte-identical golden output for list commands across all four modes."""

    def test_events_quiet(self, monkeypatch) -> None:
        _patch(monkeypatch, "events", _EVENTS)
        result = CliRunner().invoke(main, ["events", "-q"])
        assert result.exit_code == 0
        assert result.output == "1\n2\n"

    def test_events_jsonl(self, monkeypatch) -> None:
        _patch(monkeypatch, "events", _EVENTS)
        result = CliRunner().invoke(main, ["events", "--jsonl"])
        assert result.exit_code == 0
        assert result.output == (
            '{"eid": 1, "type": "Draw", "name": "vkCmdDraw"}\n'
            '{"eid": 2, "type": "Dispatch", "name": "vkCmdDispatch"}\n'
        )

    def test_events_json(self, monkeypatch) -> None:
        _patch(monkeypatch, "events", _EVENTS)
        result = CliRunner().invoke(main, ["events", "--json"])
        assert result.exit_code == 0
        assert result.output == (
            "[\n"
            '  {\n    "eid": 1,\n    "type": "Draw",\n    "name": "vkCmdDraw"\n  },\n'
            '  {\n    "eid": 2,\n    "type": "Dispatch",\n    "name": "vkCmdDispatch"\n  }\n'
            "]\n"
        )

    def test_events_table(self, monkeypatch) -> None:
        _patch(monkeypatch, "events", _EVENTS)
        result = CliRunner().invoke(main, ["events"])
        assert result.exit_code == 0
        assert result.output == "EID\tTYPE\tNAME\n1\tDraw\tvkCmdDraw\n2\tDispatch\tvkCmdDispatch\n"

    def test_resources_quiet(self, monkeypatch) -> None:
        _patch(monkeypatch, "resources", _RESOURCES)
        result = CliRunner().invoke(main, ["resources", "-q"])
        assert result.exit_code == 0
        assert result.output == "10\n20\n"

    def test_resources_jsonl(self, monkeypatch) -> None:
        _patch(monkeypatch, "resources", _RESOURCES)
        result = CliRunner().invoke(main, ["resources", "--jsonl"])
        assert result.exit_code == 0
        assert result.output == (
            '{"id": 10, "type": "Texture", "name": "albedo"}\n'
            '{"id": 20, "type": "Buffer", "name": "verts"}\n'
        )

    def test_resources_json(self, monkeypatch) -> None:
        _patch(monkeypatch, "resources", _RESOURCES)
        result = CliRunner().invoke(main, ["resources", "--json"])
        assert result.exit_code == 0
        assert result.output == (
            "[\n"
            '  {\n    "id": 10,\n    "type": "Texture",\n    "name": "albedo"\n  },\n'
            '  {\n    "id": 20,\n    "type": "Buffer",\n    "name": "verts"\n  }\n'
            "]\n"
        )

    def test_resources_table(self, monkeypatch) -> None:
        _patch(monkeypatch, "resources", _RESOURCES)
        result = CliRunner().invoke(main, ["resources"])
        assert result.exit_code == 0
        assert result.output == (
            "ID\tTYPE\tNAME\tWIDTH\tHEIGHT\tFORMAT\tSIZE\n"
            "10\tTexture\talbedo\t-\t-\t-\t-\n"
            "20\tBuffer\tverts\t-\t-\t-\t-\n"
        )

    def test_counters_quiet(self, monkeypatch) -> None:
        _patch(monkeypatch, "counters", _COUNTERS)
        result = CliRunner().invoke(main, ["counters", "--list", "-q"])
        assert result.exit_code == 0
        assert result.output == "1\n8\n"

    def test_counters_jsonl(self, monkeypatch) -> None:
        _patch(monkeypatch, "counters", _COUNTERS)
        result = CliRunner().invoke(main, ["counters", "--list", "--jsonl"])
        assert result.exit_code == 0
        assert result.output == (
            '{"id": 1, "name": "GPUDuration", "unit": "Seconds", '
            '"type": "Float", "category": "Built-in"}\n'
            '{"id": 8, "name": "VSInvocations", "unit": "Absolute", '
            '"type": "UInt", "category": "Built-in"}\n'
        )

    def test_counters_table(self, monkeypatch) -> None:
        _patch(monkeypatch, "counters", _COUNTERS)
        result = CliRunner().invoke(main, ["counters", "--list"])
        assert result.exit_code == 0
        assert result.output == (
            "ID\tNAME\tUNIT\tTYPE\tCATEGORY\n"
            "1\tGPUDuration\tSeconds\tFloat\tBuilt-in\n"
            "8\tVSInvocations\tAbsolute\tUInt\tBuilt-in\n"
        )


class TestQuietKeyNormalization:
    """A row missing the quiet key yields the default, not a KeyError.

    This fails on the pre-refactor bracket-access commands (events/draws/etc).
    """

    def test_events_missing_eid_no_keyerror(self, monkeypatch) -> None:
        _patch(monkeypatch, "events", {"events": [{"type": "Draw", "name": "noeid"}]})
        result = CliRunner().invoke(main, ["events", "-q"])
        assert result.exit_code == 0
        assert result.exception is None
        assert result.output == "\n"
