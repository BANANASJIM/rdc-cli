#!/usr/bin/env python3
"""Generate stats.json from Click introspection for documentation and badges."""
from __future__ import annotations

import argparse
import importlib.metadata
import json

import click


def _count_leaf_commands(group: click.Group, ctx: click.Context) -> int:
    total = 0
    for name in group.list_commands(ctx):
        cmd = group.get_command(ctx, name)
        if cmd is None or getattr(cmd, "hidden", False):
            continue
        if isinstance(cmd, click.Group):
            sub_ctx = click.Context(cmd, parent=ctx)
            total += _count_leaf_commands(cmd, sub_ctx)
        else:
            total += 1
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate stats.json for docs/badges")
    parser.add_argument("--version", help="Version string (from git tag, e.g. v0.3.0)")
    parser.add_argument("--test-count", type=int, default=0)
    parser.add_argument("--coverage", default="")
    args = parser.parse_args()

    from rdc.cli import main as cli_group  # noqa: PLC0415

    ctx = click.Context(cli_group)
    command_count = _count_leaf_commands(cli_group, ctx)

    version_raw = args.version or importlib.metadata.version("rdc-cli")
    version = version_raw.lstrip("v")

    meta = importlib.metadata.metadata("rdc-cli")
    description = meta["Summary"] or ""

    stats = {
        "command_count": command_count,
        "version": version,
        "description": description,
        "test_count": args.test_count,
        "coverage": args.coverage,
    }
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
