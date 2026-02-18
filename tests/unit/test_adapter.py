from __future__ import annotations

from types import SimpleNamespace

from rdc.adapter import RenderDocAdapter, parse_version_tuple


def test_parse_version_tuple_valid() -> None:
    assert parse_version_tuple("1.33") == (1, 33)
    assert parse_version_tuple("v1.35") == (1, 35)


def test_parse_version_tuple_invalid_fallback() -> None:
    assert parse_version_tuple("unknown") == (0, 0)


def test_get_root_actions_uses_new_api_for_132_plus() -> None:
    controller = SimpleNamespace(GetRootActions=lambda: ["root"])
    adapter = RenderDocAdapter(controller=controller, version=(1, 33))
    assert adapter.get_root_actions() == ["root"]


def test_get_root_actions_falls_back_to_get_drawcalls() -> None:
    controller = SimpleNamespace(GetDrawcalls=lambda: ["draw"])
    adapter = RenderDocAdapter(controller=controller, version=(1, 31))
    assert adapter.get_root_actions() == ["draw"]
