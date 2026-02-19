"""Integration tests against real renderdoc module with vkcube.rdc."""

from __future__ import annotations

from typing import Any

import pytest

from rdc.adapter import RenderDocAdapter
from rdc.services.query_service import (
    aggregate_stats,
    bindings_rows,
    count_from_actions,
    get_pass_hierarchy,
    get_resources,
    walk_actions,
)

pytestmark = pytest.mark.gpu


class TestRealReplay:
    def test_open_and_enumerate(self, vkcube_replay: tuple[Any, Any, Any]) -> None:
        _, controller, _ = vkcube_replay
        actions = controller.GetRootActions()
        assert len(actions) == 6

    def test_walk_actions_real(
        self, vkcube_replay: tuple[Any, Any, Any], adapter: RenderDocAdapter
    ) -> None:
        _, _, sf = vkcube_replay
        actions = adapter.get_root_actions()
        flat = walk_actions(actions, sf)
        assert len(flat) > 0
        assert all(hasattr(a, "pass_name") for a in flat)

    def test_aggregate_stats_real(
        self, vkcube_replay: tuple[Any, Any, Any], adapter: RenderDocAdapter
    ) -> None:
        _, _, sf = vkcube_replay
        flat = walk_actions(adapter.get_root_actions(), sf)
        stats = aggregate_stats(flat)
        assert stats.total_draws == 1
        assert stats.dispatches == 0
        assert len(stats.per_pass) == 1

    def test_count_draws(self, adapter: RenderDocAdapter) -> None:
        actions = adapter.get_root_actions()
        assert count_from_actions(actions, "draws") == 1

    def test_pipeline_state(
        self, vkcube_replay: tuple[Any, Any, Any], adapter: RenderDocAdapter
    ) -> None:
        _, _, sf = vkcube_replay
        flat = walk_actions(adapter.get_root_actions(), sf)
        draws = [a for a in flat if a.flags & 0x0002]
        assert len(draws) == 1
        adapter.set_frame_event(draws[0].eid)
        pipe = adapter.get_pipeline_state()
        assert pipe is not None

    def test_shader_bound(
        self, vkcube_replay: tuple[Any, Any, Any], adapter: RenderDocAdapter
    ) -> None:
        _, _, sf = vkcube_replay
        flat = walk_actions(adapter.get_root_actions(), sf)
        draws = [a for a in flat if a.flags & 0x0002]
        adapter.set_frame_event(draws[0].eid)
        pipe = adapter.get_pipeline_state()
        vs = pipe.GetShader(0)  # vertex
        ps = pipe.GetShader(4)  # pixel/fragment
        assert int(vs) != 0
        assert int(ps) != 0

    def test_resources_nonempty(self, adapter: RenderDocAdapter) -> None:
        rows = get_resources(adapter)
        assert len(rows) > 0
        first = rows[0]
        assert "id" in first
        assert "name" in first
        assert "type" in first

    def test_pass_hierarchy(
        self, vkcube_replay: tuple[Any, Any, Any], adapter: RenderDocAdapter
    ) -> None:
        _, _, sf = vkcube_replay
        actions = adapter.get_root_actions()
        tree = get_pass_hierarchy(actions, sf)
        assert len(tree["passes"]) >= 1

    def test_shader_disassembly(
        self, vkcube_replay: tuple[Any, Any, Any], adapter: RenderDocAdapter
    ) -> None:
        _, controller, sf = vkcube_replay
        flat = walk_actions(adapter.get_root_actions(), sf)
        draws = [a for a in flat if a.flags & 0x0002]
        adapter.set_frame_event(draws[0].eid)
        pipe = adapter.get_pipeline_state()
        refl = pipe.GetShaderReflection(0)
        targets = controller.GetDisassemblyTargets(True)
        pipeline_obj = pipe.GetGraphicsPipelineObject()
        disasm = controller.DisassembleShader(pipeline_obj, refl, str(targets[0]))
        assert len(disasm) > 0

    def test_bindings_rows(
        self, vkcube_replay: tuple[Any, Any, Any], adapter: RenderDocAdapter
    ) -> None:
        _, _, sf = vkcube_replay
        flat = walk_actions(adapter.get_root_actions(), sf)
        draws = [a for a in flat if a.flags & 0x0002]
        adapter.set_frame_event(draws[0].eid)
        pipe = adapter.get_pipeline_state()
        rows = bindings_rows(draws[0].eid, pipe)
        assert isinstance(rows, list)
