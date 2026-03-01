from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_STAGES = "vs|hs|ds|gs|ps|cs"


@dataclass(frozen=True)
class PathMatch:
    """Result of resolving a VFS path."""

    kind: str
    handler: str | None
    args: dict[str, Any]


_RouteEntry = tuple[re.Pattern[str], str, str | None, list[tuple[str, type]]]

_ROUTE_TABLE: list[_RouteEntry] = []


def _r(
    pattern: str,
    kind: str,
    handler: str | None = None,
    coercions: list[tuple[str, type]] | None = None,
) -> None:
    _ROUTE_TABLE.append((re.compile(f"^{pattern}$"), kind, handler, coercions or []))


# root
_r("/", "dir")
_r("/info", "leaf", "info")
_r("/stats", "leaf", "stats")
_r("/capabilities", "leaf", "info")
_r("/log", "leaf", "log")

# events
_r("/events", "dir")
_r(r"/events/(?P<eid>\d+)", "leaf", "event", [("eid", int)])

# draws
_r("/draws", "dir")
_r(r"/draws/(?P<eid>\d+)", "dir", None, [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline", "dir", None, [("eid", int)])
_r(
    r"/draws/(?P<eid>\d+)/pipeline/summary",
    "leaf",
    "pipeline",
    [("eid", int)],
)
_r(r"/draws/(?P<eid>\d+)/pipeline/topology", "leaf", "pipe_topology", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline/viewport", "leaf", "pipe_viewport", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline/scissor", "leaf", "pipe_scissor", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline/blend", "leaf", "pipe_blend", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline/stencil", "leaf", "pipe_stencil", [("eid", int)])
_r(
    r"/draws/(?P<eid>\d+)/pipeline/vertex-inputs",
    "leaf",
    "pipe_vinputs",
    [("eid", int)],
)
_r(r"/draws/(?P<eid>\d+)/pipeline/samplers", "leaf", "pipe_samplers", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline/vbuffers", "leaf", "pipe_vbuffers", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline/ibuffer", "leaf", "pipe_ibuffer", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline/push-constants", "leaf", "pipe_push_constants", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline/rasterizer", "leaf", "pipe_rasterizer", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline/depth-stencil", "leaf", "pipe_depth_stencil", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pipeline/msaa", "leaf", "pipe_msaa", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/shader", "dir", None, [("eid", int)])
_r(
    rf"/draws/(?P<eid>\d+)/shader/(?P<stage>{_STAGES})",
    "dir",
    None,
    [("eid", int)],
)
_r(
    rf"/draws/(?P<eid>\d+)/shader/(?P<stage>{_STAGES})/disasm",
    "leaf",
    "shader_disasm",
    [("eid", int)],
)
_r(
    rf"/draws/(?P<eid>\d+)/shader/(?P<stage>{_STAGES})/source",
    "leaf",
    "shader_source",
    [("eid", int)],
)
_r(
    rf"/draws/(?P<eid>\d+)/shader/(?P<stage>{_STAGES})/reflect",
    "leaf",
    "shader_reflect",
    [("eid", int)],
)
_r(
    rf"/draws/(?P<eid>\d+)/shader/(?P<stage>{_STAGES})/constants",
    "leaf",
    "shader_constants",
    [("eid", int)],
)
_r(r"/draws/(?P<eid>\d+)/postvs", "leaf", "postvs", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/cbuffer", "dir", None, [("eid", int)])
_r(
    r"/draws/(?P<eid>\d+)/cbuffer/(?P<set>\d+)/(?P<binding>\d+)",
    "leaf",
    "cbuffer_decode",
    [("eid", int), ("set", int), ("binding", int)],
)
_r(r"/draws/(?P<eid>\d+)/cbuffer/(?P<set>\d+)", "dir", None, [("eid", int), ("set", int)])
_r(r"/draws/(?P<eid>\d+)/vbuffer", "leaf", "vbuffer_decode", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/ibuffer", "leaf", "ibuffer_decode", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/descriptors", "leaf", "descriptors", [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pixel", "dir", None, [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/pixel/(?P<x>\d+)", "dir", None, [("eid", int), ("x", int)])
_r(
    r"/draws/(?P<eid>\d+)/pixel/(?P<x>\d+)/(?P<y>\d+)",
    "leaf",
    "pixel_history",
    [("eid", int), ("x", int), ("y", int)],
)
_r(
    r"/draws/(?P<eid>\d+)/pixel/(?P<x>\d+)/(?P<y>\d+)/color(?P<target>\d+)",
    "leaf",
    "pixel_history",
    [("eid", int), ("x", int), ("y", int), ("target", int)],
)
_r(r"/draws/(?P<eid>\d+)/bindings", "dir", None, [("eid", int)])
_r(
    r"/draws/(?P<eid>\d+)/bindings/(?P<set>\d+)/(?P<binding>\d+)",
    "leaf",
    "bindings",
    [("eid", int), ("set", int), ("binding", int)],
)
_r(r"/draws/(?P<eid>\d+)/bindings/(?P<set>\d+)", "dir", None, [("eid", int), ("set", int)])

# draw targets
_r(r"/draws/(?P<eid>\d+)/targets", "dir", None, [("eid", int)])
_r(
    r"/draws/(?P<eid>\d+)/targets/color(?P<target>\d+)\.png",
    "leaf_bin",
    "rt_export",
    [("eid", int), ("target", int)],
)
_r(r"/draws/(?P<eid>\d+)/targets/depth\.png", "leaf_bin", "rt_depth", [("eid", int)])

# passes
_r("/passes", "dir")
_r(r"/passes/(?P<name>[^/]+)", "dir")
_r(r"/passes/(?P<name>[^/]+)/info", "leaf", "pass")
_r(r"/passes/(?P<name>[^/]+)/draws", "dir")
_r(r"/passes/(?P<name>[^/]+)/attachments", "dir")
_r(r"/passes/(?P<name>[^/]+)/attachments/(?P<attachment>[^/]+)", "leaf", "pass_attachment")

# resources
_r("/resources", "dir")
_r(r"/resources/(?P<id>\d+)", "dir", None, [("id", int)])
_r(r"/resources/(?P<id>\d+)/info", "leaf", "resource", [("id", int)])
_r(r"/resources/(?P<id>\d+)/usage", "leaf", "usage", [("id", int)])

# top-level dirs / aliases
_r("/shaders", "dir")
_r(r"/shaders/(?P<id>\d+)", "dir", None, [("id", int)])
_r(r"/shaders/(?P<id>\d+)/info", "leaf", "shader_list_info", [("id", int)])
_r(r"/shaders/(?P<id>\d+)/disasm", "leaf", "shader_list_disasm", [("id", int)])
_r(r"/shaders/(?P<id>\d+)/used-by", "leaf", "shader_used_by", [("id", int)])
_r("/by-marker", "dir")
_r("/textures", "dir")
_r(r"/textures/(?P<id>\d+)", "dir", None, [("id", int)])
_r(r"/textures/(?P<id>\d+)/info", "leaf", "tex_info", [("id", int)])
_r(r"/textures/(?P<id>\d+)/image\.png", "leaf_bin", "tex_export", [("id", int)])
_r(r"/textures/(?P<id>\d+)/mips", "dir", None, [("id", int)])
_r(
    r"/textures/(?P<id>\d+)/mips/(?P<mip>\d+)\.png",
    "leaf_bin",
    "tex_export",
    [("id", int), ("mip", int)],
)
_r(r"/textures/(?P<id>\d+)/data", "leaf_bin", "tex_raw", [("id", int)])

_r("/buffers", "dir")
_r(r"/buffers/(?P<id>\d+)", "dir", None, [("id", int)])
_r(r"/buffers/(?P<id>\d+)/info", "leaf", "buf_info", [("id", int)])
_r(r"/buffers/(?P<id>\d+)/data", "leaf_bin", "buf_raw", [("id", int)])
_r("/counters", "dir")
_r("/counters/list", "leaf", "counter_list")
_r("/current", "alias")


def resolve_path(path: str) -> PathMatch | None:
    """Resolve a VFS path to its route entry.

    Args:
        path: Virtual filesystem path (e.g. "/draws/142/shader/ps/disasm").
            Empty string resolves as "/". Trailing slashes are stripped.

    Returns:
        PathMatch with kind, handler, and extracted args, or None if no match.
    """
    path = path.rstrip("/") or "/"

    for regex, kind, handler, coercions in _ROUTE_TABLE:
        m = regex.match(path)
        if not m:
            continue

        args: dict[str, Any] = m.groupdict()
        for name, typ in coercions:
            if name in args:
                args[name] = typ(args[name])

        # /pipeline/summary → section=None
        if handler == "pipeline" and "section" not in args:
            args["section"] = None

        return PathMatch(kind=kind, handler=handler, args=args)

    return None
