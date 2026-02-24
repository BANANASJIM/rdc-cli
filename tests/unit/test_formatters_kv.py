"""Tests for rdc.formatters.kv module."""

from __future__ import annotations

import io

from rdc.formatters.kv import format_kv, write_kv


class TestFormatKv:
    def test_aligned_columns(self) -> None:
        result = format_kv({"Key": "val", "LongerKey": "v"})
        lines = result.split("\n")
        # max_key=9, label width=9+2=11; "Key:" (4) padded to 11
        assert lines[0] == "Key:       val"
        assert lines[1] == "LongerKey: v"

    def test_none_value_shows_dash(self) -> None:
        assert format_kv({"nullable": None}) == "nullable: -"

    def test_empty_string_shows_dash(self) -> None:
        assert format_kv({"empty": ""}) == "empty: -"

    def test_empty_dict_fallback(self) -> None:
        assert format_kv({}) == str({})

    def test_non_dict_fallback(self) -> None:
        assert format_kv("not a dict") == "not a dict"  # type: ignore[arg-type]

    def test_single_key(self) -> None:
        # max_key=1, label width=1+2=3; "k:" (2) padded to 3
        assert format_kv({"k": 42}) == "k: 42"


class TestWriteKv:
    def test_writes_to_stream(self) -> None:
        buf = io.StringIO()
        write_kv({"a": 1, "bb": 2}, out=buf)
        text = buf.getvalue()
        assert text.endswith("\n")
        lines = text.strip().split("\n")
        # max_key=2, label width=2+2=4; "a:" (2) padded to 4
        assert lines[0] == "a:  1"
        assert lines[1] == "bb: 2"
