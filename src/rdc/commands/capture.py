"""Capture command: execute application and capture a frame."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

from rdc.capture_core import build_capture_options, execute_and_capture, terminate_process
from rdc.discover import find_renderdoc


def _find_renderdoccmd() -> str | None:
    """Locate the renderdoccmd binary."""
    in_path = shutil.which("renderdoccmd")
    if in_path:
        return in_path
    common_paths = [
        Path("/opt/renderdoc/bin/renderdoccmd"),
        Path("/usr/local/bin/renderdoccmd"),
    ]
    for path in common_paths:
        if path.exists() and path.is_file():
            return str(path)
    return None


@click.command(
    "capture",
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
)
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output .rdc file path.")
@click.option("--api", "api_name", type=str, help="Capture API name.")
@click.option("--list-apis", is_flag=True, help="List capture APIs and exit.")
@click.option("--frame", type=int, default=None, help="Queue capture at frame N.")
@click.option("--trigger", is_flag=True, help="Inject only; do not auto-capture.")
@click.option("--timeout", type=float, default=60.0, help="Capture timeout in seconds.")
@click.option("--wait-for-exit", is_flag=True, help="Wait for process to exit.")
@click.option("--keep-alive", is_flag=True, help="Keep target process running after capture.")
@click.option("--auto-open", is_flag=True, help="Open capture after success.")
@click.option("--api-validation", is_flag=True, help="Enable API validation.")
@click.option("--callstacks", is_flag=True, help="Capture callstacks.")
@click.option("--hook-children", is_flag=True, help="Hook child processes.")
@click.option("--ref-all-resources", is_flag=True, help="Reference all resources.")
@click.option("--soft-memory-limit", type=int, default=None, help="Soft memory limit (MB).")
@click.option("--delay-for-debugger", type=int, default=None, help="Debugger attach delay (s).")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def capture_cmd(
    ctx: click.Context,
    output: Path | None,
    api_name: str | None,
    list_apis: bool,
    frame: int | None,
    trigger: bool,
    timeout: float,
    wait_for_exit: bool,
    keep_alive: bool,
    auto_open: bool,
    api_validation: bool,
    callstacks: bool,
    hook_children: bool,
    ref_all_resources: bool,
    soft_memory_limit: int | None,
    delay_for_debugger: int | None,
    use_json: bool,
) -> None:
    """Execute application and capture a frame.

    Usage: rdc capture [OPTIONS] -- EXECUTABLE [APP_ARGS...]
    """
    if list_apis:
        _run_list_apis()
        return

    if not ctx.args:
        raise click.UsageError("EXECUTABLE is required (use -- before executable)")
    executable = ctx.args[0]
    app_args = ctx.args[1:]

    opts: dict[str, Any] = {}
    if api_validation:
        opts["api_validation"] = True
    if callstacks:
        opts["callstacks"] = True
    if hook_children:
        opts["hook_children"] = True
    if ref_all_resources:
        opts["ref_all_resources"] = True
    if soft_memory_limit is not None:
        opts["soft_memory_limit"] = soft_memory_limit
    if delay_for_debugger is not None:
        opts["delay_for_debugger"] = delay_for_debugger

    output_path = str(output) if output else ""

    rd = find_renderdoc()
    if rd is not None:
        if api_name:
            click.echo("warning: --api is ignored with Python API path", err=True)
        cap_opts = build_capture_options(opts)
        result = execute_and_capture(
            rd,
            executable,
            args=shlex.join(app_args),
            workdir="",
            output=output_path,
            opts=cap_opts,
            frame=frame,
            trigger=trigger,
            timeout=timeout,
            wait_for_exit=wait_for_exit,
        )
        if not trigger and not keep_alive and result.success and result.pid:
            terminate_process(result.pid)
        _emit_result(result, use_json, auto_open)
        return

    click.echo("warning: renderdoc module unavailable, falling back to renderdoccmd", err=True)
    if opts:
        click.echo("warning: CaptureOptions flags ignored in fallback mode", err=True)
    _fallback_renderdoccmd(executable, app_args, output_path, api_name)


def _emit_result(result: Any, use_json: bool, auto_open: bool) -> None:
    """Print capture result."""
    if use_json:
        import dataclasses

        click.echo(json.dumps(dataclasses.asdict(result)))
        if not result.success:
            raise SystemExit(1)
        return

    if not result.success:
        click.echo(f"error: {result.error}", err=True)
        raise SystemExit(1)

    if result.path:
        click.echo(result.path)  # stdout: machine-parseable
        click.echo(f"next: rdc open {result.path}", err=True)
    elif result.ident:
        click.echo(f"injected: ident={result.ident}", err=True)
        click.echo(f"next: rdc attach {result.ident}", err=True)

    if auto_open and result.path:
        subprocess.run([sys.executable, "-m", "rdc", "open", result.path], check=False)


def _run_list_apis() -> None:
    """List available capture APIs via renderdoccmd."""
    bin_path = _find_renderdoccmd()
    if not bin_path:
        click.echo("error: renderdoccmd not found", err=True)
        raise SystemExit(1)
    result = subprocess.run([bin_path, "capture", "--list-apis"], check=False)
    raise SystemExit(result.returncode)


def _fallback_renderdoccmd(
    app: str, extra_args: list[str], output: str, api_name: str | None
) -> None:
    """Fall back to renderdoccmd subprocess for capture."""
    bin_path = _find_renderdoccmd()
    if not bin_path:
        click.echo("error: renderdoccmd not found", err=True)
        raise SystemExit(1)

    argv: list[str] = [bin_path, "capture"]
    if api_name:
        argv.extend(["--opt-api", api_name])
    if output:
        argv.extend(["--capture-file", output])
    argv.append(app)
    argv.extend(extra_args)

    result = subprocess.run(argv, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    if output:
        click.echo(output)  # stdout: machine-parseable
        click.echo(f"next: rdc open {output}", err=True)
