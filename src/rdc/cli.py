from __future__ import annotations

import click

from rdc import __version__
from rdc.commands.capture import capture_cmd
from rdc.commands.doctor import doctor_cmd
from rdc.commands.session import close_cmd, goto_cmd, open_cmd, status_cmd


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="rdc")
def main() -> None:
    """rdc: Unix-friendly CLI for RenderDoc captures."""


main.add_command(doctor_cmd, name="doctor")
main.add_command(capture_cmd, name="capture")
main.add_command(open_cmd, name="open")
main.add_command(close_cmd, name="close")
main.add_command(status_cmd, name="status")
main.add_command(goto_cmd, name="goto")


if __name__ == "__main__":
    main()
