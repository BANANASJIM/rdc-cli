"""Tests for resources schema fix and filter/sort options (phase2.7)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd  # noqa: E402

from rdc.adapter import RenderDocAdapter  # noqa: E402
from rdc.commands.resources import resources_cmd  # noqa: E402
from rdc.daemon_server import DaemonState, _handle_request  # noqa: E402
from rdc.services.query_service import _resource_row  # type: ignore[attr-defined]  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _req(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    p: dict[str, Any] = {"_token": "tok"}
    if params:
        p.update(params)
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": p}


def _make_res(rid: int, name: str, type_name: str) -> Any:
    """Build a mock ResourceDescription with a type whose .name equals type_name."""
    rtype = SimpleNamespace(name=type_name)
    return rd.ResourceDescription(
        resourceId=rd.ResourceId(rid),
        name=name,
        type=rtype,  # type: ignore[arg-type]
    )


def _state_with_resources(resources: list[Any]) -> DaemonState:
    ctrl = rd.MockReplayController()
    ctrl._resources = resources
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 33))
    return state


def _patch_resources(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]) -> None:
    import rdc.commands.resources as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})


# ---------------------------------------------------------------------------
# TestResourceRow — schema fix
# ---------------------------------------------------------------------------


class TestResourceRow:
    def test_type_enum_name(self) -> None:
        rtype = SimpleNamespace(name="Texture")
        r = rd.ResourceDescription(resourceId=rd.ResourceId(1), name="tex", type=rtype)  # type: ignore[arg-type]
        row = _resource_row(r)
        assert row["type"] == "Texture"

    def test_type_fallback_no_name_attr(self) -> None:
        # type object has no .name — fallback to str(type)
        rtype = SimpleNamespace()
        r = rd.ResourceDescription(resourceId=rd.ResourceId(2), name="buf", type=rtype)  # type: ignore[arg-type]
        row = _resource_row(r)
        assert row["type"] == str(rtype)

    def test_type_none_gives_empty_string(self) -> None:
        r = SimpleNamespace(resourceId=rd.ResourceId(3), name="x", type=None)
        row = _resource_row(r)
        assert row["type"] == ""

    def test_ghost_fields_absent(self) -> None:
        r = rd.ResourceDescription(resourceId=rd.ResourceId(4), name="n")
        row = _resource_row(r)
        for ghost in ("width", "height", "depth", "format"):
            assert ghost not in row, f"ghost field '{ghost}' present in row"

    def test_id_and_name_passthrough(self) -> None:
        r = rd.ResourceDescription(resourceId=rd.ResourceId(42), name="hello")
        row = _resource_row(r)
        assert row["id"] == 42
        assert row["name"] == "hello"

    def test_schema_has_exactly_three_keys(self) -> None:
        r = rd.ResourceDescription(resourceId=rd.ResourceId(5), name="n")
        row = _resource_row(r)
        assert set(row.keys()) == {"id", "type", "name"}


# ---------------------------------------------------------------------------
# TestDaemonTypeFilter
# ---------------------------------------------------------------------------


class TestDaemonTypeFilter:
    def _resources(self) -> list[Any]:
        return [
            _make_res(1, "myTex", "Texture"),
            _make_res(2, "myTex2", "Texture"),
            _make_res(3, "myBuf", "Buffer"),
        ]

    def test_exact_match_case_insensitive(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"type": "texture"}), state)
        rows = resp["result"]["rows"]
        assert len(rows) == 2
        assert all(r["type"] == "Texture" for r in rows)

    def test_no_match(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"type": "Sampler"}), state)
        assert resp["result"]["rows"] == []

    def test_not_supplied_returns_all(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources"), state)
        assert len(resp["result"]["rows"]) == 3

    def test_upper_case_match(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"type": "TEXTURE"}), state)
        rows = resp["result"]["rows"]
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# TestDaemonNameFilter
# ---------------------------------------------------------------------------


class TestDaemonNameFilter:
    def _resources(self) -> list[Any]:
        return [
            _make_res(1, "hello_triangle", "Texture"),
            _make_res(2, "depth_buffer", "Buffer"),
            _make_res(3, "swapchain", "Texture"),
        ]

    def test_substring_match(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"name": "tri"}), state)
        rows = resp["result"]["rows"]
        assert len(rows) == 1
        assert rows[0]["name"] == "hello_triangle"

    def test_no_match(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"name": "zzz"}), state)
        assert resp["result"]["rows"] == []

    def test_not_supplied_returns_all(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources"), state)
        assert len(resp["result"]["rows"]) == 3

    def test_case_insensitive(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"name": "TRI"}), state)
        rows = resp["result"]["rows"]
        assert len(rows) == 1
        assert "tri" in rows[0]["name"].lower()


# ---------------------------------------------------------------------------
# TestDaemonCombinedFilter
# ---------------------------------------------------------------------------


class TestDaemonCombinedFilter:
    def _resources(self) -> list[Any]:
        return [
            _make_res(1, "hello_triangle", "Texture"),
            _make_res(2, "depth_buffer", "Buffer"),
            _make_res(3, "triangle_buf", "Buffer"),
        ]

    def test_both_filters(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"type": "Texture", "name": "tri"}), state)
        rows = resp["result"]["rows"]
        assert len(rows) == 1
        assert rows[0]["name"] == "hello_triangle"

    def test_type_matches_name_does_not(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"type": "Buffer", "name": "zzz"}), state)
        assert resp["result"]["rows"] == []


# ---------------------------------------------------------------------------
# TestDaemonSort
# ---------------------------------------------------------------------------


class TestDaemonSort:
    def _resources(self) -> list[Any]:
        return [
            _make_res(3, "zebra", "Texture"),
            _make_res(1, "apple", "Buffer"),
            _make_res(2, "mango", "Texture"),
        ]

    def test_sort_by_name(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"sort": "name"}), state)
        names = [r["name"] for r in resp["result"]["rows"]]
        assert names == sorted(names, key=str.lower)

    def test_sort_by_type(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"sort": "type"}), state)
        types = [r["type"] for r in resp["result"]["rows"]]
        assert types == sorted(types, key=str.lower)

    def test_sort_by_id_default(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources"), state)
        ids = [r["id"] for r in resp["result"]["rows"]]
        # id sort is enumeration order (3, 1, 2 as added to ctrl._resources)
        assert ids == [3, 1, 2]

    def test_unknown_sort_no_crash(self) -> None:
        state = _state_with_resources(self._resources())
        resp, _ = _handle_request(_req("resources", {"sort": "foobar"}), state)
        assert "rows" in resp["result"]
        assert len(resp["result"]["rows"]) == 3


# ---------------------------------------------------------------------------
# TestResourcesCLI
# ---------------------------------------------------------------------------


class TestResourcesCLI:
    _BASE_ROWS = [
        {"id": 1, "type": "Texture", "name": "myTex"},
        {"id": 2, "type": "Buffer", "name": "myBuf"},
    ]

    def _patch(self, monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> None:
        _patch_resources(monkeypatch, {"rows": rows})

    def test_no_options_three_column_header(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, self._BASE_ROWS)
        result = CliRunner().invoke(resources_cmd, [])
        assert result.exit_code == 0
        assert "ID" in result.output
        assert "TYPE" in result.output
        assert "NAME" in result.output
        for ghost in ("WIDTH", "HEIGHT", "DEPTH", "FORMAT"):
            assert ghost not in result.output

    def test_type_option_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import rdc.commands.resources as mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(mod, "load_session", lambda: session)
        captured: list[dict[str, Any]] = []

        def fake_send(_h: str, _p: int, payload: dict[str, Any]) -> dict[str, Any]:
            captured.append(payload["params"])
            return {"result": {"rows": []}}

        monkeypatch.setattr(mod, "send_request", fake_send)
        CliRunner().invoke(resources_cmd, ["--type", "Texture"])
        assert captured[0].get("type") == "Texture"

    def test_name_option_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import rdc.commands.resources as mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(mod, "load_session", lambda: session)
        captured: list[dict[str, Any]] = []

        def fake_send(_h: str, _p: int, payload: dict[str, Any]) -> dict[str, Any]:
            captured.append(payload["params"])
            return {"result": {"rows": []}}

        monkeypatch.setattr(mod, "send_request", fake_send)
        CliRunner().invoke(resources_cmd, ["--name", "tri"])
        assert captured[0].get("name") == "tri"

    def test_sort_option_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import rdc.commands.resources as mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(mod, "load_session", lambda: session)
        captured: list[dict[str, Any]] = []

        def fake_send(_h: str, _p: int, payload: dict[str, Any]) -> dict[str, Any]:
            captured.append(payload["params"])
            return {"result": {"rows": []}}

        monkeypatch.setattr(mod, "send_request", fake_send)
        CliRunner().invoke(resources_cmd, ["--sort", "name"])
        assert captured[0].get("sort") == "name"

    def test_json_output_three_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, self._BASE_ROWS)
        result = CliRunner().invoke(resources_cmd, ["--json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        for row in data:
            assert set(row.keys()) == {"id", "type", "name"}

    def test_all_three_options_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import rdc.commands.resources as mod

        session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
        monkeypatch.setattr(mod, "load_session", lambda: session)
        captured: list[dict[str, Any]] = []

        def fake_send(_h: str, _p: int, payload: dict[str, Any]) -> dict[str, Any]:
            captured.append(payload["params"])
            return {"result": {"rows": []}}

        monkeypatch.setattr(mod, "send_request", fake_send)
        CliRunner().invoke(resources_cmd, ["--type", "X", "--name", "Y", "--sort", "type"])
        p = captured[0]
        assert p.get("type") == "X"
        assert p.get("name") == "Y"
        assert p.get("sort") == "type"

    def test_invalid_sort_rejected_by_click(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, [])
        result = CliRunner().invoke(resources_cmd, ["--sort", "invalid"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# TestResourcesRegressionNoSession
# ---------------------------------------------------------------------------


class TestResourcesRegressionNoSession:
    def test_no_session_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import rdc.commands.resources as mod

        monkeypatch.setattr(mod, "load_session", lambda: None)
        result = CliRunner().invoke(resources_cmd, [])
        assert result.exit_code != 0
