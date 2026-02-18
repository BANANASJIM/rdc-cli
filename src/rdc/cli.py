from __future__ import annotations

import click

from rdc import __version__
from rdc.commands.capture import capture_cmd
from rdc.commands.doctor import doctor_cmd


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="rdc")
def main() -> None:
    """rdc: Unix-friendly CLI for RenderDoc captures."""


main.add_command(doctor_cmd, name="doctor")
main.add_command(capture_cmd, name="capture")


if __name__ == "__main__":
    main()
