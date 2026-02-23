#!/usr/bin/env python3
"""Generate commands.json from Click CLI introspection for the Astro docs site.

Output: JSON with categories and commands, each with name, help, usage, and
structured option/argument metadata.  The Astro commands page imports this JSON
directly so it never drifts from the actual CLI.
"""
from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator

import click

# ---------------------------------------------------------------------------
# Category definitions — the one piece that must be maintained manually.
# Validation below ensures every leaf command is assigned to exactly one
# category and catches any newly-added commands that are missing.
# (name, html-id, optional description, ordered command names)
# ---------------------------------------------------------------------------
CATEGORIES: list[tuple[str, str, str | None, list[str]]] = [
    ("Session", "session", None, [
        "open", "close", "status", "goto", "capture", "doctor",
    ]),
    ("Inspection", "inspection", None, [
        "info", "stats", "events", "draws", "event", "draw", "log", "counters",
    ]),
    ("Draw Analysis", "draw-analysis", None, [
        "pipeline", "bindings",
    ]),
    ("Resources", "resources-section", None, [
        "resources", "resource", "usage", "shader", "shaders", "shader-map",
        "search", "passes", "pass",
    ]),
    ("Export", "export", None, [
        "texture", "buffer", "rt", "mesh", "snapshot",
    ]),
    ("Pixel & Debug", "pixel-debug", None, [
        "pixel", "pick-pixel", "tex-stats",
        "debug pixel", "debug vertex", "debug thread",
    ]),
    ("Shader Edit-Replay", "shader-edit-replay", None, [
        "shader-encodings", "shader-build", "shader-replace",
        "shader-restore", "shader-restore-all",
    ]),
    ("CI Assertions", "ci-assertions", None, [
        "assert-pixel", "assert-image", "assert-clean",
        "assert-count", "assert-state",
    ]),
    ("Capture Diff", "capture-diff", None, [
        "diff",
    ]),
    (
        "Target Control", "target-control",
        "Live interaction with a running RenderDoc-injected target process.",
        ["attach", "capture-trigger", "capture-list", "capture-copy"],
    ),
    (
        "Capture Metadata", "capture-metadata",
        "Inspect capture file metadata without full replay.",
        ["thumbnail", "gpus", "sections", "section"],
    ),
    ("VFS Navigation", "vfs", None, [
        "ls", "cat", "tree",
    ]),
    ("Utilities", "utilities", None, [
        "count", "completion", "script", "install-skill",
    ]),
]

# Commands whose usage line can't be auto-derived from Click params.
USAGE_OVERRIDES: dict[str, str] = {
    "capture": (
        "rdc capture <EXECUTABLE> [ARGS...] [-o OUTPUT]\n"
        "  [--frame N] [--trigger] [--timeout N] [--wait-for-exit]\n"
        "  [--keep-alive] [--auto-open] [--api-validation] [--callstacks]\n"
        "  [--hook-children] [--ref-all-resources]\n"
        "  [--soft-memory-limit N] [--delay-for-debugger N]\n"
        "  [--api TEXT] [--list-apis] [--json]"
    ),
}


# ---------------------------------------------------------------------------
# Click introspection helpers
# ---------------------------------------------------------------------------

def iter_leaf_commands(
    group: click.Group, ctx: click.Context, prefix: str = "",
) -> Iterator[tuple[str, click.Command]]:
    """Yield ``(full_name, command)`` for every non-hidden leaf command."""
    for name in sorted(group.list_commands(ctx)):
        cmd = group.get_command(ctx, name)
        if cmd is None or getattr(cmd, "hidden", False):
            continue
        full = f"{prefix}{name}"
        if isinstance(cmd, click.Group):
            sub_ctx = click.Context(cmd, parent=ctx)
            yield from iter_leaf_commands(cmd, sub_ctx, prefix=f"{full} ")
        else:
            yield full, cmd


def _build_usage(name: str, cmd: click.Command) -> str:
    """Reconstruct a concise usage line from Click params."""
    if name in USAGE_OVERRIDES:
        return USAGE_OVERRIDES[name]

    parts = [f"rdc {name}"]

    for p in cmd.params:
        if not isinstance(p, click.Argument):
            continue
        meta = p.human_readable_name.upper().replace("_", "-")
        if p.nargs == -1:
            parts.append(f"[{meta}...]")
        elif p.required:
            parts.append(f"<{meta}>")
        else:
            parts.append(f"[{meta}]")

    for p in cmd.params:
        if not isinstance(p, click.Option) or p.name == "help":
            continue
        flag = p.opts[0]
        if p.is_flag:
            parts.append(f"[{flag}]")
        else:
            meta = p.metavar or p.type.name.upper()
            if p.required:
                parts.append(f"{flag} <{meta}>")
            else:
                parts.append(f"[{flag} {meta}]")

    return " ".join(parts)


def _help_to_html(text: str) -> str:
    """Convert backtick-wrapped text to <code> tags."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)


def _extract_command(name: str, cmd: click.Command) -> dict:
    """Build JSON-serialisable dict for one command."""
    help_text = ""
    if cmd.help:
        help_text = cmd.help.split("\n\n")[0].strip()

    return {
        "name": name,
        "id": name.replace(" ", "-"),
        "help": _help_to_html(help_text),
        "usage": _build_usage(name, cmd),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    from rdc.cli import main as cli_group  # noqa: PLC0415

    ctx = click.Context(cli_group)
    commands = dict(iter_leaf_commands(cli_group, ctx))

    # Validate: every referenced command exists, no duplicates
    assigned: set[str] = set()
    for _, _, _, cmd_names in CATEGORIES:
        for n in cmd_names:
            if n not in commands:
                print(f"error: category references unknown command: {n}", file=sys.stderr)
                sys.exit(1)
            if n in assigned:
                print(f"error: command {n!r} in multiple categories", file=sys.stderr)
                sys.exit(1)
            assigned.add(n)

    unassigned = set(commands.keys()) - assigned
    if unassigned:
        print(f"error: unassigned commands: {sorted(unassigned)}", file=sys.stderr)
        sys.exit(1)

    result = {
        "categories": [
            {
                "name": cat_name,
                "id": cat_id,
                "description": cat_desc,
                "commands": [_extract_command(n, commands[n]) for n in cmd_names],
            }
            for cat_name, cat_id, cat_desc, cmd_names in CATEGORIES
        ],
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
