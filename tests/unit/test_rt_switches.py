"""Tests for RT switch detection (T8: rdc passes --switches)."""

from __future__ import annotations

import json

from click.testing import CliRunner
from conftest import patch_cli_session
from mock_renderdoc import ActionDescription, ActionFlags, ResourceId

from rdc.commands.resources import passes_cmd
from rdc.services.query_service import _count_rt_switches


def _action(
    eid: int,
    flags: int = ActionFlags.Drawcall,
    outputs: list[int] | None = None,
    depth: int = 0,
) -> ActionDescription:
    out = [ResourceId(v) for v in (outputs or [0] * 8)]
    while len(out) < 8:
        out.append(ResourceId(0))
    return ActionDescription(
        eventId=eid,
        flags=flags,
        _name=f"draw@{eid}",
        outputs=out,
        depthOut=ResourceId(depth),
        numIndices=3,
        numInstances=1,
    )


# ── Service tests ──────────────────────────────────────────────────


def test_no_rt_switches() -> None:
    """All actions share same RT -> 0 switches."""
    actions = [
        _action(10, outputs=[100]),
        _action(20, outputs=[100]),
        _action(30, outputs=[100]),
    ]
    result = _count_rt_switches(actions, 10, 30)
    assert result["count"] == 0
    assert result["switches"] == []


def test_two_rt_switches() -> None:
    """RT changes twice within the pass EID range."""
    actions = [
        _action(10, outputs=[100], depth=50),
        _action(20, outputs=[200], depth=50),  # switch 1
        _action(30, outputs=[200], depth=50),
        _action(40, outputs=[300], depth=60),  # switch 2
    ]
    result = _count_rt_switches(actions, 10, 40)
    assert result["count"] == 2
    assert len(result["switches"]) == 2

    sw0 = result["switches"][0]
    assert sw0["eid"] == 20
    assert 100 in sw0["from_targets"]
    assert 200 in sw0["to_targets"]

    sw1 = result["switches"][1]
    assert sw1["eid"] == 40


def test_actions_outside_eid_range_ignored() -> None:
    """Actions outside the specified EID range are not counted."""
    actions = [
        _action(5, outputs=[100]),  # before range
        _action(10, outputs=[100]),
        _action(20, outputs=[200]),  # switch within range
        _action(50, outputs=[300]),  # after range
    ]
    result = _count_rt_switches(actions, 10, 20)
    assert result["count"] == 1
    assert result["switches"][0]["eid"] == 20


def test_nested_actions() -> None:
    """Actions nested in children are found."""
    child1 = _action(10, outputs=[100])
    child2 = _action(20, outputs=[200])
    parent = ActionDescription(
        eventId=5,
        flags=ActionFlags.PushMarker,
        _name="Marker",
        children=[child1, child2],
    )
    result = _count_rt_switches([parent], 5, 25)
    assert result["count"] == 1


def test_dispatch_and_clear_counted() -> None:
    """Dispatch and clear actions participate in RT switch detection."""
    actions = [
        _action(10, flags=ActionFlags.Drawcall, outputs=[100]),
        _action(20, flags=ActionFlags.Dispatch, outputs=[200]),
        _action(30, flags=ActionFlags.Clear, outputs=[200]),
    ]
    result = _count_rt_switches(actions, 10, 30)
    assert result["count"] == 1


def test_empty_actions() -> None:
    """No actions -> 0 switches."""
    result = _count_rt_switches([], 0, 100)
    assert result["count"] == 0
    assert result["switches"] == []


# ── Handler test ───────────────────────────────────────────────────


def test_handle_passes_switches() -> None:
    """Handler adds rt_switches when switches param is set."""
    from conftest import make_daemon_state

    a1 = _action(10, outputs=[100])
    a2 = _action(20, outputs=[200])
    begin = ActionDescription(
        eventId=5,
        flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
        _name="TestPass",
        children=[a1, a2],
    )
    end = ActionDescription(
        eventId=25,
        flags=ActionFlags.EndPass | ActionFlags.PassBoundary,
        _name="EndPass",
    )
    state = make_daemon_state(actions=[begin, end])

    from rdc.handlers.query import _handle_passes

    resp, _ = _handle_passes(1, {"switches": True}, state)
    passes = resp["result"]["tree"]["passes"]
    assert len(passes) >= 1
    p = passes[0]
    assert "rt_switches" in p
    assert p["rt_switches"]["count"] == 1


def test_handle_passes_no_switches_param() -> None:
    """Without switches param, no rt_switches key is added."""
    from conftest import make_daemon_state

    a1 = _action(10, outputs=[100])
    begin = ActionDescription(
        eventId=5,
        flags=ActionFlags.BeginPass | ActionFlags.PassBoundary,
        _name="TestPass",
        children=[a1],
    )
    end = ActionDescription(
        eventId=15,
        flags=ActionFlags.EndPass | ActionFlags.PassBoundary,
        _name="EndPass",
    )
    state = make_daemon_state(actions=[begin, end])

    from rdc.handlers.query import _handle_passes

    resp, _ = _handle_passes(1, {}, state)
    passes = resp["result"]["tree"]["passes"]
    for p in passes:
        assert "rt_switches" not in p


# ── CLI tests ──────────────────────────────────────────────────────

_PASSES_WITH_SWITCHES = {
    "tree": {
        "passes": [
            {
                "name": "Shadow",
                "draws": 3,
                "dispatches": 0,
                "triangles": 600,
                "begin_eid": 10,
                "end_eid": 50,
                "load_ops": [],
                "store_ops": [],
                "rt_switches": {
                    "count": 2,
                    "switches": [
                        {"eid": 20, "from_targets": [100, 0], "to_targets": [200, 0]},
                        {"eid": 40, "from_targets": [200, 0], "to_targets": [300, 0]},
                    ],
                },
            },
        ]
    }
}


def test_cli_switches_tsv(monkeypatch: object) -> None:
    """--switches adds RT_SWITCHES column in TSV."""
    patch_cli_session(monkeypatch, _PASSES_WITH_SWITCHES)  # type: ignore[arg-type]
    result = CliRunner().invoke(passes_cmd, ["--switches"])
    assert result.exit_code == 0
    assert "RT_SWITCHES" in result.output
    assert "2" in result.output


def test_cli_switches_json(monkeypatch: object) -> None:
    """--switches --json includes rt_switches in output."""
    patch_cli_session(monkeypatch, _PASSES_WITH_SWITCHES)  # type: ignore[arg-type]
    result = CliRunner().invoke(passes_cmd, ["--switches", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "rt_switches" in data["passes"][0]
    assert data["passes"][0]["rt_switches"]["count"] == 2


def test_cli_no_switches_no_column(monkeypatch: object) -> None:
    """Without --switches, no RT_SWITCHES column."""
    patch_cli_session(
        monkeypatch,  # type: ignore[arg-type]
        {
            "tree": {
                "passes": [
                    {
                        "name": "Shadow",
                        "draws": 3,
                        "dispatches": 0,
                        "triangles": 600,
                        "begin_eid": 10,
                        "end_eid": 50,
                        "load_ops": [],
                        "store_ops": [],
                    }
                ]
            }
        },
    )
    result = CliRunner().invoke(passes_cmd, [])
    assert result.exit_code == 0
    assert "RT_SWITCHES" not in result.output
