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
_r(r"/draws/(?P<eid>\d+)/bindings", "dir", None, [("eid", int)])

# passes
_r("/passes", "dir")
_r(r"/passes/(?P<name>[^/]+)", "dir")
_r(r"/passes/(?P<name>[^/]+)/info", "leaf", "pass")
_r(r"/passes/(?P<name>[^/]+)/draws", "dir")
_r(r"/passes/(?P<name>[^/]+)/attachments", "dir")

# resources
_r("/resources", "dir")
_r(r"/resources/(?P<id>\d+)", "dir", None, [("id", int)])
_r(r"/resources/(?P<id>\d+)/info", "leaf", "resource", [("id", int)])

# top-level dirs / aliases
_r("/shaders", "dir")
_r("/by-marker", "dir")
_r("/textures", "dir")
_r("/buffers", "dir")
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
