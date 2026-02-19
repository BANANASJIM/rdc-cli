from __future__ import annotations

import click

from rdc import __version__
from rdc.commands.capture import capture_cmd
from rdc.commands.doctor import doctor_cmd
from rdc.commands.events import draw_cmd, draws_cmd, event_cmd, events_cmd
from rdc.commands.info import info_cmd, stats_cmd
from rdc.commands.pipeline import bindings_cmd, pipeline_cmd, shader_cmd, shaders_cmd
from rdc.commands.session import close_cmd, goto_cmd, open_cmd, status_cmd
from rdc.commands.unix_helpers import count_cmd, shader_map_cmd


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
main.add_command(info_cmd, name="info")
main.add_command(stats_cmd, name="stats")
main.add_command(events_cmd, name="events")
main.add_command(draws_cmd, name="draws")
main.add_command(event_cmd, name="event")
main.add_command(draw_cmd, name="draw")
main.add_command(count_cmd, name="count")
main.add_command(shader_map_cmd, name="shader-map")
main.add_command(pipeline_cmd, name="pipeline")
main.add_command(bindings_cmd, name="bindings")
main.add_command(shader_cmd, name="shader")
main.add_command(shaders_cmd, name="shaders")


if __name__ == "__main__":
    main()
