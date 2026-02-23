"""CaptureFile handlers: thumbnail, gpus, sections, section content."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import _error_response, _result_response
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _handle_capture_thumbnail(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Return capture file thumbnail as base64."""
    if state.cap is None:
        return _error_response(request_id, -32002, "no capture file open"), True
    maxsize = int(params.get("maxsize", 0))
    file_type = int(params.get("fileType", 2))  # default JPG
    thumb = state.cap.GetThumbnail(file_type, maxsize)
    data_b64 = base64.b64encode(thumb.data).decode() if thumb.data else ""
    return _result_response(
        request_id,
        {
            "data": data_b64,
            "width": thumb.width,
            "height": thumb.height,
        },
    ), True


def _handle_capture_gpus(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """List GPUs available at capture time."""
    if state.cap is None:
        return _error_response(request_id, -32002, "no capture file open"), True
    gpus = state.cap.GetAvailableGPUs()
    return _result_response(
        request_id,
        {
            "gpus": [
                {"name": g.name, "vendor": g.vendor, "deviceID": g.deviceID, "driver": g.driver}
                for g in gpus
            ],
        },
    ), True


def _handle_capture_sections(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """List all embedded sections in the capture file."""
    if state.cap is None:
        return _error_response(request_id, -32002, "no capture file open"), True
    count = state.cap.GetSectionCount()
    sections = []
    for i in range(count):
        p = state.cap.GetSectionProperties(i)
        sections.append(
            {
                "index": i,
                "name": p.name,
                "type": int(p.type),
                "version": p.version,
                "compressedSize": p.compressedSize,
                "uncompressedSize": p.uncompressedSize,
            }
        )
    return _result_response(request_id, {"sections": sections}), True


def _handle_capture_section_content(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Extract named section contents (UTF-8 text or base64 binary)."""
    if state.cap is None:
        return _error_response(request_id, -32002, "no capture file open"), True
    name = params.get("name")
    if not name:
        return _error_response(request_id, -32602, "missing 'name' parameter"), True
    idx = state.cap.FindSectionByName(name)
    if idx < 0:
        return _error_response(request_id, -32002, f"section '{name}' not found"), True
    raw = state.cap.GetSectionContents(idx)
    try:
        text = raw.decode("utf-8")
        return _result_response(
            request_id,
            {
                "name": name,
                "contents": text,
                "encoding": "utf-8",
            },
        ), True
    except UnicodeDecodeError:
        return _result_response(
            request_id,
            {
                "name": name,
                "contents": base64.b64encode(raw).decode(),
                "encoding": "base64",
            },
        ), True


HANDLERS: dict[str, Handler] = {
    "capture_thumbnail": _handle_capture_thumbnail,
    "capture_gpus": _handle_capture_gpus,
    "capture_sections": _handle_capture_sections,
    "capture_section_content": _handle_capture_section_content,
}
