#!/usr/bin/env python3
"""Cross-platform gen/check runner for pixi tasks."""

import difflib
import subprocess
import sys
from pathlib import Path


def run_generator(script: str) -> str:
    """Run a generator script and return its stdout.

    Args:
        script: Path to the generator script.

    Returns:
        The captured stdout as a string.

    Raises:
        SystemExit: If the generator exits with a non-zero code.
    """
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(result.returncode)
    return result.stdout


def cmd_gen(script: str, output: str) -> None:
    """Run generator and write output to file.

    Args:
        script: Path to the generator script.
        output: Path to the output file.
    """
    content = run_generator(script)
    Path(output).write_text(content, encoding="utf-8")


def cmd_check(script: str, output: str) -> None:
    """Run generator and compare output to existing file.

    Args:
        script: Path to the generator script.
        output: Path to the file to compare against.
    """
    generated = run_generator(script)
    existing = Path(output).read_text(encoding="utf-8")
    if generated == existing:
        sys.exit(0)
    diff = difflib.unified_diff(
        existing.splitlines(keepends=True),
        generated.splitlines(keepends=True),
        fromfile=output,
        tofile="<generated>",
    )
    sys.stderr.writelines(diff)
    sys.exit(1)


def main() -> None:
    """Entry point for gen_and_check.

    Usage:
        python scripts/gen_and_check.py gen   <generator_script> <output_file>
        python scripts/gen_and_check.py check <generator_script> <output_file>

    Modes:
        gen:   Run the generator and write its stdout to the output file.
        check: Run the generator, compare stdout to the output file; exit 1 with
               a unified diff on stderr if they differ.
    """
    if len(sys.argv) != 4 or sys.argv[1] not in ("gen", "check"):
        sys.stderr.write(
            "Usage: gen_and_check.py gen|check <generator_script> <output_file>\n"
        )
        sys.exit(2)

    _, mode, script, output = sys.argv
    if mode == "gen":
        cmd_gen(script, output)
    else:
        cmd_check(script, output)


if __name__ == "__main__":
    main()
