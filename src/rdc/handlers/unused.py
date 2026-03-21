"""Handler for unused render target detection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import _error_response, _result_response
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _handle_unused_targets(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Detect render targets produced but never consumed by swapchain output."""
    if state.adapter is None:
        return _error_response(request_id, -32002, "no replay loaded"), True

    from rdc.services.query_service import _build_pass_list, find_unused_targets

    actions = state.adapter.get_root_actions()
    passes = _build_pass_list(actions, state.structured_file)

    usage_data: dict[int, list[Any]] = {}
    for resid, rid_obj in state.res_rid_map.items():
        usage_data[resid] = state.adapter.controller.GetUsage(rid_obj.resourceId)

    swapchain_ids: set[int] = {
        rid for rid, tname in state.res_types.items() if tname == "SwapchainImage"
    }

    result = find_unused_targets(passes, usage_data, state.res_names, swapchain_ids)
    return _result_response(request_id, result), True


HANDLERS: dict[str, Handler] = {
    "unused_targets": _handle_unused_targets,
}
