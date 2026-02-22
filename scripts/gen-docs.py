#!/usr/bin/env python3
"""Auto-generate command reference markdown from rdc --help output.

Runs `rdc --help` and `rdc <cmd> --help` for each command,
parses Click's output, and writes markdown files to docs/src/content/docs/.

Usage:
    python scripts/gen-docs.py
    pixi run gen-docs
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs" / "src" / "content" / "docs"


def run_help(args: list[str]) -> str:
    """Run rdc with given args and return stdout."""
    result = subprocess.run(
        ["rdc", *args, "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout


def parse_commands(help_text: str) -> list[str]:
    """Extract command names from `rdc --help` output."""
    commands: list[str] = []
    in_commands = False
    for line in help_text.splitlines():
        if line.strip().startswith("Commands:"):
            in_commands = True
            continue
        if in_commands:
            match = re.match(r"\s+(\w[\w-]*)", line)
            if match:
                commands.append(match.group(1))
            elif line.strip() == "":
                continue
            else:
                break
    return sorted(commands)


def generate_command_md(cmd: str, help_text: str) -> str:
    """Generate markdown for a single command."""
    lines = [f"# rdc {cmd}\n"]
    # Extract the first description line
    for line in help_text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("Usage:") and not stripped.startswith("Options:"):
            lines.append(f"{stripped}\n")
            break

    lines.append("\n## Usage\n")
    lines.append("```")
    in_usage = False
    for line in help_text.splitlines():
        if line.strip().startswith("Usage:"):
            in_usage = True
            lines.append(line.strip())
        elif in_usage and line.strip():
            lines.append(line.strip())
        elif in_usage:
            break
    lines.append("```\n")

    # Options section
    in_options = False
    option_lines: list[str] = []
    for line in help_text.splitlines():
        if line.strip().startswith("Options:"):
            in_options = True
            continue
        if in_options:
            if line.strip():
                option_lines.append(line)
            else:
                option_lines.append("")

    if option_lines:
        lines.append("## Options\n")
        lines.append("```")
        lines.extend(option_lines)
        lines.append("```\n")

    return "\n".join(lines)


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    main_help = run_help([])
    commands = parse_commands(main_help)

    if not commands:
        print("No commands found. Is rdc installed?")
        return

    print(f"Found {len(commands)} commands: {', '.join(commands)}")

    index_lines = ["# Command Reference\n"]
    index_lines.append("Auto-generated from `rdc --help`.\n")
    index_lines.append("| Command | Description |")
    index_lines.append("|---------|-------------|")

    for cmd in commands:
        help_text = run_help([cmd])
        # Extract first description line
        desc = ""
        for line in help_text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("Usage:"):
                desc = stripped
                break

        index_lines.append(f"| [`rdc {cmd}`]({cmd}/) | {desc} |")

        md = generate_command_md(cmd, help_text)
        cmd_file = DOCS_DIR / f"{cmd}.md"
        cmd_file.write_text(md)
        print(f"  Generated {cmd_file.name}")

    index_file = DOCS_DIR / "commands.md"
    index_file.write_text("\n".join(index_lines) + "\n")
    print(f"Generated index: {index_file.name}")
    print("Done!")


if __name__ == "__main__":
    main()
