"""Tests for semantic EID shell completion callbacks."""

from __future__ import annotations

import sys

from rdc.commands._helpers import complete_eid
from rdc.commands.assert_ci import assert_pixel_cmd, assert_state_cmd
from rdc.commands.counters import counters_cmd
from rdc.commands.debug import pixel_cmd as debug_pixel_cmd
from rdc.commands.debug import thread_cmd, vertex_cmd
from rdc.commands.diff import diff_cmd
from rdc.commands.events import draw_cmd, event_cmd
from rdc.commands.export import rt_cmd
from rdc.commands.info import log_cmd
from rdc.commands.mesh import mesh_cmd
from rdc.commands.pick_pixel import pick_pixel_cmd
from rdc.commands.pipeline import bindings_cmd, pipeline_cmd, shader_cmd
from rdc.commands.pixel import pixel_cmd
from rdc.commands.session import goto_cmd
from rdc.commands.shader_edit import shader_replace_cmd, shader_restore_cmd
from rdc.commands.snapshot import snapshot_cmd
from rdc.commands.tex_stats import tex_stats_cmd


def _param(cmd, name: str):
    return next(p for p in cmd.params if p.name == name)


def test_complete_eid_suggests_events(monkeypatch) -> None:
    monkeypatch.setattr(
        "rdc.commands._helpers.try_call",
        lambda _m, _p: {
            "events": [
                {"eid": 12, "name": "vkCmdDrawIndexed"},
                {"eid": 34, "name": "vkCmdDispatch"},
            ]
        },
    )

    items = complete_eid(None, None, "")
    assert [item.value for item in items] == ["12", "34"]
    assert [item.help for item in items] == ["vkCmdDrawIndexed", "vkCmdDispatch"]


def test_complete_eid_applies_prefix_filter(monkeypatch) -> None:
    monkeypatch.setattr(
        "rdc.commands._helpers.try_call",
        lambda _m, _p: {"events": [{"eid": 12, "name": "a"}, {"eid": 34, "name": "b"}]},
    )

    items = complete_eid(None, None, "3")
    assert [item.value for item in items] == ["34"]


def test_complete_eid_daemon_failure_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr("rdc.commands._helpers.try_call", lambda _m, _p: None)

    assert complete_eid(None, None, "") == []


def test_complete_eid_does_not_force_limit(monkeypatch) -> None:
    seen_params: dict[str, object] = {}

    def _try_call(_method: str, params: dict[str, object]) -> dict[str, object]:
        seen_params.update(params)
        return {"events": []}

    monkeypatch.setattr("rdc.commands._helpers.try_call", _try_call)

    assert complete_eid(None, None, "") == []
    assert "limit" not in seen_params


def test_complete_eid_failure_keeps_stderr_empty(monkeypatch, capsys) -> None:
    def _failing_try_call(_method: str, _params: dict[str, object]) -> None:
        sys.stderr.write("error: no active session\n")
        return None

    monkeypatch.setattr("rdc.commands._helpers.try_call", _failing_try_call)

    assert complete_eid(None, None, "") == []
    assert capsys.readouterr().err == ""


def test_eid_arguments_are_wired_for_completion() -> None:
    assert _param(event_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(draw_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(pipeline_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(bindings_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(goto_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(rt_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(mesh_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(pixel_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(pick_pixel_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(tex_stats_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(shader_replace_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(shader_restore_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(snapshot_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(assert_pixel_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(assert_state_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(debug_pixel_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(thread_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(vertex_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(shader_cmd, "first").shell_complete is not None
    assert _param(counters_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(log_cmd, "eid")._custom_shell_complete is complete_eid
    assert _param(diff_cmd, "eid")._custom_shell_complete is complete_eid
