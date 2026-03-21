"""rdc unused-targets command -- detect render targets never consumed by output."""

from __future__ import annotations

import sys
from typing import Any

import click

from rdc.commands._helpers import call
from rdc.formatters.json_fmt import write_json
from rdc.formatters.tsv import write_tsv


@click.command("unused-targets")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("-q", "--quiet", is_flag=True, help="One resource ID per line")
@click.option("--no-header", is_flag=True, help="Omit TSV header")
def unused_targets_cmd(
    use_json: bool,
    quiet: bool,
    no_header: bool,
) -> None:
    """Detect render targets produced but never consumed by visible output."""
    result: dict[str, Any] = call("unused_targets", {})
    if use_json:
        write_json(result)
        return
    unused = result.get("unused", [])
    if quiet:
        for entry in unused:
            sys.stdout.write(str(entry["id"]) + "\n")
        return
    rows = [
        [
            entry["id"],
            entry["name"],
            ",".join(entry["written_by"]) if entry["written_by"] else "-",
            entry["wave"],
        ]
        for entry in unused
    ]
    write_tsv(rows, header=["ID", "NAME", "WRITTEN_BY", "WAVE"], no_header=no_header)
