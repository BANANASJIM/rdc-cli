"""CaptureFile handlers: thumbnail, gpus, sections, section content, callstacks, write."""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import _error_response, _result_response
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState

_log = logging.getLogger(__name__)

_PROTECTED_SECTION_TYPES: frozenset[str] = frozenset(
    {
        "FrameCapture",
        "ResolveDatabase",
        "ExtendedThumbnail",
        "EmbeddedLogfile",
        "ResourceRenames",
        "AMDRGPProfile",
    }
)


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


def _parse_resolve_string(s: str) -> dict[str, Any]:
    """Parse a resolve string like ``'func file.c:42'`` into a frame dict."""
    parts = s.rsplit(" ", 1)
    func = parts[0] if len(parts) > 1 else s
    file_line = parts[1] if len(parts) > 1 else ""
    file_name = ""
    line = 0
    if ":" in file_line:
        fl_parts = file_line.rsplit(":", 1)
        file_name = fl_parts[0]
        try:
            line = int(fl_parts[1])
        except ValueError:
            file_name = file_line
    else:
        file_name = file_line
    return {"function": func, "file": file_name, "line": line}


def _handle_callstack_resolve(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Resolve CPU callstack for an event ID."""
    if state.cap is None:
        return _error_response(request_id, -32002, "no capture file open"), True
    if not state.cap.HasCallstacks():
        return _error_response(request_id, -32002, "no callstacks recorded in this capture"), True
    try:
        ok = state.cap.InitResolver(interactive=False, progress=None)
    except Exception as exc:  # noqa: BLE001
        return _error_response(request_id, -32002, f"symbols not available: {exc}"), True
    if not ok:
        return _error_response(request_id, -32002, "symbols not available"), True

    eid = params.get("eid", state.current_eid)
    if not isinstance(eid, int) or eid < 0:
        return _error_response(request_id, -32602, "invalid eid"), True
    if eid > state.max_eid:
        return _error_response(
            request_id, -32602, f"eid {eid} out of range (max {state.max_eid})"
        ), True

    callstack: list[int] = []
    ctrl = getattr(state.adapter, "controller", None) if state.adapter else None
    get_cs = getattr(ctrl, "GetCallstack", None) if ctrl else None
    if callable(get_cs):
        try:
            callstack = list(get_cs(eid))
        except Exception:  # noqa: BLE001
            _log.debug("GetCallstack(%d) failed, falling back", eid)

    frames: list[dict[str, Any]] = []
    if callstack:
        resolved = state.cap.GetResolve(callstack)
        frames = [_parse_resolve_string(s) for s in resolved]

    return _result_response(request_id, {"eid": eid, "frames": frames}), True


def _handle_section_write(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Write a named section to the capture file."""
    if state.cap is None:
        return _error_response(request_id, -32002, "no capture file open"), True

    name = params.get("name")
    if not name or not isinstance(name, str):
        return _error_response(request_id, -32602, "missing or empty 'name'"), True

    data_b64 = params.get("data")
    if data_b64 is None or not isinstance(data_b64, str):
        return _error_response(request_id, -32602, "missing 'data' parameter"), True

    idx = state.cap.FindSectionByName(name)
    if idx >= 0:
        props = state.cap.GetSectionProperties(idx)
        type_name = getattr(getattr(props, "type", None), "name", "")
        if type_name in _PROTECTED_SECTION_TYPES:
            return _error_response(
                request_id,
                -32602,
                f"cannot overwrite built-in section '{name}'",
            ), True

    try:
        decoded = base64.b64decode(data_b64)
    except Exception:  # noqa: BLE001
        return _error_response(request_id, -32602, "invalid base64 data"), True

    rd = state.rd
    sec_type = getattr(rd, "SectionType", None) if rd else None
    unknown_type = getattr(sec_type, "Unknown", 0) if sec_type else 0
    sec_flags_cls = getattr(rd, "SectionFlags", None) if rd else None
    no_flags = getattr(sec_flags_cls, "NoFlags", 0) if sec_flags_cls else 0
    sp_cls = getattr(rd, "SectionProperties", None) if rd else None

    if sp_cls is not None:
        new_props = sp_cls()
        new_props.name = name
        new_props.type = unknown_type
        new_props.flags = no_flags
    else:
        from types import SimpleNamespace

        new_props = SimpleNamespace(
            name=name,
            type=unknown_type,
            version=1,
            flags=no_flags,
            compressedSize=0,
            uncompressedSize=0,
        )

    state.cap.WriteSection(new_props, decoded)
    return _result_response(request_id, {"name": name, "bytes": len(decoded)}), True


HANDLERS: dict[str, Handler] = {
    "capture_thumbnail": _handle_capture_thumbnail,
    "capture_gpus": _handle_capture_gpus,
    "capture_sections": _handle_capture_sections,
    "capture_section_content": _handle_capture_section_content,
    "callstack_resolve": _handle_callstack_resolve,
    "section_write": _handle_section_write,
}
