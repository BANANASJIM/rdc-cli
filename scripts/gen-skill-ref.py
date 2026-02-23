#!/usr/bin/env python3
"""Generate commands-quick-ref.md from Click introspection."""
from __future__ import annotations

from collections.abc import Iterator

import click


def iter_leaf_commands(
    group: click.Group, ctx: click.Context, prefix: str = ""
) -> Iterator[tuple[str, click.Command]]:
    """Yield ``(full_name, command)`` for every non-hidden leaf command.

    Groups are recursed into; their subcommands are prefixed with the group
    name (e.g. ``"debug pixel"``).

    Args:
        group: Click group to walk.
        ctx: Click context for the group.
        prefix: Name prefix for nested groups.
    """
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


def _render_command(name: str, cmd: click.Command) -> list[str]:
    """Render a single command as markdown lines."""
    lines: list[str] = [f"## `rdc {name}`", ""]
    if cmd.help:
        lines += [cmd.help.split("\n\n")[0].strip(), ""]

    args = [p for p in cmd.params if isinstance(p, click.Argument)]
    opts = [
        p
        for p in cmd.params
        if isinstance(p, click.Option) and p.name != "help"
    ]

    if args:
        lines += ["**Arguments:**", ""]
        lines += ["| Name | Type | Required |", "|------|------|----------|"]
        for a in args:
            type_name = a.type.name if a.type else "TEXT"
            req = "yes" if a.required else "no"
            lines.append(f"| `{a.name}` | {type_name} | {req} |")
        lines.append("")

    if opts:
        lines += ["**Options:**", ""]
        lines += [
            "| Flag | Help | Type | Default |",
            "|------|------|------|---------|",
        ]
        for o in opts:
            flags = ", ".join(o.opts)
            help_text = (o.help or "").replace("|", "\\|")
            if o.is_flag:
                type_name = "flag"
                default = ""
            else:
                type_name = o.type.name if o.type else "TEXT"
                raw = o.default
                default = str(raw) if raw is not None and type(raw).__name__ != "Sentinel" else ""
            lines.append(f"| `{flags}` | {help_text} | {type_name} | {default} |")
        lines.append("")

    return lines


def generate_skill_ref() -> str:
    """Generate the full commands quick-reference as a markdown string.

    Walks the rdc CLI group, introspects every leaf command, and renders
    a markdown document with one section per command including help text,
    arguments, and options tables.

    Returns:
        Complete markdown string ready to write to a file.
    """
    from rdc.cli import main as cli_group  # noqa: PLC0415

    ctx = click.Context(cli_group)
    lines: list[str] = ["# rdc-cli Command Quick Reference", ""]

    for name, cmd in iter_leaf_commands(cli_group, ctx):
        lines += _render_command(name, cmd)

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    sys.stdout.write(generate_skill_ref())
