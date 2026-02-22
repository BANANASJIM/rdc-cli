from __future__ import annotations

import os

import click

from rdc import __version__
from rdc.commands.assert_ci import (
    assert_clean_cmd,
    assert_count_cmd,
    assert_pixel_cmd,
    assert_state_cmd,
)
from rdc.commands.assert_image import assert_image_cmd
from rdc.commands.capture import capture_cmd
from rdc.commands.completion import completion_cmd
from rdc.commands.counters import counters_cmd
from rdc.commands.diff import diff_cmd
from rdc.commands.doctor import doctor_cmd
from rdc.commands.events import draw_cmd, draws_cmd, event_cmd, events_cmd
from rdc.commands.export import buffer_cmd, rt_cmd, texture_cmd
from rdc.commands.info import info_cmd, log_cmd, stats_cmd
from rdc.commands.pipeline import bindings_cmd, pipeline_cmd, shader_cmd, shaders_cmd
from rdc.commands.pixel import pixel_cmd
from rdc.commands.resources import pass_cmd, passes_cmd, resource_cmd, resources_cmd
from rdc.commands.script import script_cmd
from rdc.commands.search import search_cmd
from rdc.commands.session import close_cmd, goto_cmd, open_cmd, status_cmd
from rdc.commands.snapshot import snapshot_cmd
from rdc.commands.unix_helpers import count_cmd, shader_map_cmd
from rdc.commands.usage import usage_cmd
from rdc.commands.vfs import cat_cmd, complete_cmd, ls_cmd, tree_cmd
from rdc.session_state import SESSION_NAME_RE


def _set_session_env(ctx: click.Context, param: click.Parameter, value: str | None) -> None:
    """Validate and export --session NAME to RDC_SESSION environment variable."""
    if value is None:
        return
    if not SESSION_NAME_RE.match(value):
        raise click.BadParameter(
            f"{value!r} is invalid; use [a-zA-Z0-9_-], 1–64 chars",
            ctx=ctx,
            param=param,
        )
    os.environ["RDC_SESSION"] = value


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="rdc")
@click.option(
    "--session",
    default=None,
    metavar="NAME",
    expose_value=False,
    is_eager=True,
    callback=_set_session_env,
    help="Named session (default: value of $RDC_SESSION or 'default').",
)
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
main.add_command(resources_cmd, name="resources")
main.add_command(resource_cmd, name="resource")
main.add_command(passes_cmd, name="passes")
main.add_command(pass_cmd, name="pass")
main.add_command(log_cmd, name="log")
main.add_command(ls_cmd, name="ls")
main.add_command(cat_cmd, name="cat")
main.add_command(tree_cmd, name="tree")
main.add_command(complete_cmd, name="_complete")
main.add_command(texture_cmd, name="texture")
main.add_command(rt_cmd, name="rt")
main.add_command(buffer_cmd, name="buffer")
main.add_command(search_cmd, name="search")
main.add_command(usage_cmd, name="usage")
main.add_command(completion_cmd, name="completion")
main.add_command(counters_cmd, name="counters")
main.add_command(script_cmd, name="script")
main.add_command(pixel_cmd, name="pixel")
main.add_command(diff_cmd, name="diff")
main.add_command(assert_image_cmd, name="assert-image")
main.add_command(assert_pixel_cmd, name="assert-pixel")
main.add_command(assert_clean_cmd, name="assert-clean")
main.add_command(assert_count_cmd, name="assert-count")
main.add_command(assert_state_cmd, name="assert-state")
main.add_command(snapshot_cmd, name="snapshot")


if __name__ == "__main__":
    main()
