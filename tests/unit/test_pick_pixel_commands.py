"""Tests for rdc pick-pixel CLI command."""

from __future__ import annotations

from click.testing import CliRunner
from conftest import assert_json_output

import rdc.commands.pick_pixel as mod
from rdc.cli import main
from rdc.commands.pick_pixel import pick_pixel_cmd

_HAPPY = {
    "x": 512,
    "y": 384,
    "eid": 120,
    "target": {"index": 0, "id": 42},
    "color": {"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0},
}


def _patch(monkeypatch, response=_HAPPY):
    captured: dict = {}

    def fake_call(method, params=None):
        captured["method"] = method
        captured["params"] = params
        return response

    monkeypatch.setattr(mod, "_daemon_call", fake_call)
    return captured


def test_pick_pixel_default_output(monkeypatch):
    _patch(monkeypatch)
    r = CliRunner().invoke(pick_pixel_cmd, ["512", "384"])
    assert r.exit_code == 0
    assert "r=0.5000  g=0.3000  b=0.1000  a=1.0000" in r.output


def test_pick_pixel_json(monkeypatch):
    _patch(monkeypatch)
    r = CliRunner().invoke(pick_pixel_cmd, ["512", "384", "--json"])
    data = assert_json_output(r)
    assert "color" in data
    assert data["color"]["r"] == 0.5
    assert data["color"]["g"] == 0.3
    assert data["color"]["b"] == 0.1
    assert data["color"]["a"] == 1.0


def test_pick_pixel_eid_arg(monkeypatch):
    cap = _patch(monkeypatch)
    CliRunner().invoke(pick_pixel_cmd, ["512", "384", "120"])
    assert cap["params"]["eid"] == 120


def test_pick_pixel_eid_omitted(monkeypatch):
    cap = _patch(monkeypatch)
    CliRunner().invoke(pick_pixel_cmd, ["512", "384"])
    assert "eid" not in cap["params"]


def test_pick_pixel_target_option(monkeypatch):
    cap = _patch(monkeypatch)
    CliRunner().invoke(pick_pixel_cmd, ["512", "384", "--target", "2"])
    assert cap["params"]["target"] == 2


def test_pick_pixel_default_target(monkeypatch):
    cap = _patch(monkeypatch)
    CliRunner().invoke(pick_pixel_cmd, ["512", "384"])
    assert cap["params"]["target"] == 0


def test_pick_pixel_method_name(monkeypatch):
    cap = _patch(monkeypatch)
    CliRunner().invoke(pick_pixel_cmd, ["512", "384"])
    assert cap["method"] == "pick_pixel"


def test_pick_pixel_non_integer_x():
    r = CliRunner().invoke(pick_pixel_cmd, ["abc", "384"])
    assert r.exit_code == 2


def test_pick_pixel_non_integer_y():
    r = CliRunner().invoke(pick_pixel_cmd, ["512", "xyz"])
    assert r.exit_code == 2


def test_pick_pixel_help():
    r = CliRunner().invoke(pick_pixel_cmd, ["--help"])
    assert r.exit_code == 0
    assert "pick-pixel" in r.output.lower() or "Read pixel color" in r.output


def test_pick_pixel_in_main_help():
    r = CliRunner().invoke(main, ["--help"])
    assert r.exit_code == 0
    assert "pick-pixel" in r.output


def test_pick_pixel_float_formatting(monkeypatch):
    resp = {
        "x": 0,
        "y": 0,
        "eid": 1,
        "target": {"index": 0, "id": 1},
        "color": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 0.5},
    }
    _patch(monkeypatch, resp)
    r = CliRunner().invoke(pick_pixel_cmd, ["0", "0"])
    assert r.exit_code == 0
    assert "r=1.0000  g=0.0000  b=0.0000  a=0.5000" in r.output


def test_pick_pixel_daemon_error(monkeypatch):
    monkeypatch.setattr(mod, "_daemon_call", lambda m, p=None: (_ for _ in ()).throw(SystemExit(1)))
    r = CliRunner().invoke(pick_pixel_cmd, ["512", "384"])
    assert r.exit_code == 1
