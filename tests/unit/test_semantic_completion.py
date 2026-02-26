"""Tests for semantic shell completion callbacks."""

from __future__ import annotations

import sys

from click.shell_completion import CompletionItem

import rdc.commands._helpers as helpers
from rdc.commands.assert_ci import assert_count_cmd
from rdc.commands.events import draws_cmd
from rdc.commands.pipeline import _PIPELINE_SECTIONS, _complete_pipeline_section, pipeline_cmd
from rdc.commands.resources import pass_cmd
from rdc.commands.unix_helpers import count_cmd
from rdc.handlers._helpers import _SECTION_MAP, _SHADER_STAGES


def _values(items: list[CompletionItem]) -> list[str]:
    return [item.value for item in items]


def _param(cmd, name: str):
    return next(p for p in cmd.params if p.name == name)


def test_pass_completion_returns_daemon_pass_names(monkeypatch) -> None:
    monkeypatch.setattr(
        helpers,
        "try_call",
        lambda method, params: {
            "tree": {"passes": [{"name": "GBuffer"}, {"name": "Shadow"}, {"name": "GBuffer"}]}
        },
    )

    assert _values(helpers.complete_pass_name(None, None, "")) == ["GBuffer", "Shadow"]


def test_pass_completion_prefix_match_is_case_insensitive(monkeypatch) -> None:
    monkeypatch.setattr(
        helpers,
        "try_call",
        lambda method, params: {
            "tree": {"passes": [{"name": "GBuffer"}, {"name": "Shadow"}, {"name": "PostFX"}]}
        },
    )

    assert _values(helpers.complete_pass_name(None, None, "g")) == ["GBuffer"]


def test_pass_identifier_completion_returns_indexes_and_names(monkeypatch) -> None:
    monkeypatch.setattr(
        helpers,
        "try_call",
        lambda method, params: {
            "tree": {"passes": [{"name": "GBuffer"}, {"name": "Shadow"}, {"name": "GBuffer"}]}
        },
    )

    assert _values(helpers.complete_pass_identifier(None, None, "")) == [
        "0",
        "GBuffer",
        "1",
        "Shadow",
        "2",
    ]


def test_pass_identifier_completion_prefix_filters_indexes_and_names(monkeypatch) -> None:
    monkeypatch.setattr(
        helpers,
        "try_call",
        lambda method, params: {
            "tree": {"passes": [{"name": "GBuffer"}, {"name": "Shadow"}, {"name": "PostFX"}]}
        },
    )

    assert _values(helpers.complete_pass_identifier(None, None, "1")) == ["1"]
    assert _values(helpers.complete_pass_identifier(None, None, "g")) == ["GBuffer"]


def test_pass_completion_falls_back_to_empty_on_error(monkeypatch) -> None:
    monkeypatch.setattr(helpers, "try_call", lambda method, params: None)
    assert helpers.complete_pass_name(None, None, "") == []


def test_pass_completion_failure_path_keeps_stderr_empty(monkeypatch, capsys) -> None:
    monkeypatch.setattr(helpers, "load_session", lambda: None)

    assert helpers.complete_pass_name(None, None, "") == []
    captured = capsys.readouterr()
    assert captured.err == ""


def test_pass_completion_try_call_exception_is_silent(monkeypatch, capsys) -> None:
    def _raising_try_call(_method, _params):
        sys.stderr.write("should-not-leak\n")
        raise RuntimeError("boom")

    monkeypatch.setattr(helpers, "try_call", _raising_try_call)

    assert helpers.complete_pass_name(None, None, "") == []
    captured = capsys.readouterr()
    assert captured.err == ""


def test_pass_completion_falls_back_to_empty_on_malformed_payload(monkeypatch) -> None:
    monkeypatch.setattr(helpers, "try_call", lambda method, params: {"tree": []})
    assert helpers.complete_pass_name(None, None, "") == []


def test_pipeline_section_completion_candidates() -> None:
    values = _values(_complete_pipeline_section(None, None, ""))
    assert "topology" in values
    assert "depth-stencil" in values
    assert "push-constants" in values
    assert "ps" in values


def test_pipeline_section_completion_prefix_match() -> None:
    assert _values(_complete_pipeline_section(None, None, "de")) == ["depth-stencil"]


def test_pipeline_section_completion_matches_server_section_keys() -> None:
    expected = set(_SECTION_MAP) | set(_SHADER_STAGES)
    assert set(_PIPELINE_SECTIONS) == expected


def test_pass_like_options_are_wired_for_shell_complete() -> None:
    assert _param(draws_cmd, "pass_name").shell_complete is not None
    assert _param(count_cmd, "pass_name").shell_complete is not None
    assert (
        _param(assert_count_cmd, "pass_name")._custom_shell_complete is helpers.complete_pass_name
    )
    assert _param(pass_cmd, "identifier").shell_complete is not None


def test_pipeline_section_argument_has_shell_complete() -> None:
    assert _param(pipeline_cmd, "section").shell_complete is not None
