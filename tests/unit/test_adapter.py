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


def test_get_api_properties() -> None:
    props = SimpleNamespace(pipelineType="Vulkan")
    controller = SimpleNamespace(GetAPIProperties=lambda: props)
    adapter = RenderDocAdapter(controller=controller, version=(1, 33))
    assert adapter.get_api_properties().pipelineType == "Vulkan"


def test_get_resources() -> None:
    controller = SimpleNamespace(GetResources=lambda: ["res1", "res2"])
    adapter = RenderDocAdapter(controller=controller, version=(1, 33))
    assert adapter.get_resources() == ["res1", "res2"]


def test_get_pipeline_state() -> None:
    state = SimpleNamespace(name="pipe")
    controller = SimpleNamespace(GetPipelineState=lambda: state)
    adapter = RenderDocAdapter(controller=controller, version=(1, 33))
    assert adapter.get_pipeline_state().name == "pipe"


def test_set_frame_event() -> None:
    calls: list[tuple[int, bool]] = []
    controller = SimpleNamespace(SetFrameEvent=lambda eid, force: calls.append((eid, force)))
    adapter = RenderDocAdapter(controller=controller, version=(1, 33))
    adapter.set_frame_event(142)
    assert calls == [(142, True)]


def test_shutdown() -> None:
    state = {"shutdown": False}
    controller = SimpleNamespace(Shutdown=lambda: state.update(shutdown=True))
    adapter = RenderDocAdapter(controller=controller, version=(1, 33))
    adapter.shutdown()
    assert state["shutdown"] is True
