"""rdc serve: launch renderdoccmd remoteserver."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

from rdc import _platform
from rdc.discover import find_renderdoccmd


def _remoteserver_conf_path() -> Path:
    """Return platform-specific remoteserver.conf path."""
    if sys.platform == "win32":
        import os

        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(appdata) / "renderdoc" / "remoteserver.conf"
    return Path.home() / ".renderdoc" / "remoteserver.conf"


def _generate_config(allow_ips: list[str] | None, no_exec: bool) -> str:
    """Generate remoteserver.conf content."""
    cidrs = allow_ips or [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
    ]
    lines = [f"whitelist {cidr}" for cidr in cidrs]
    if no_exec:
        lines.append("noexec")
    return "\n".join(lines) + "\n"


def _start_remoteserver(
    cmd: str,
    port: int,
    host: str,
) -> subprocess.Popen[bytes]:
    """Launch renderdoccmd remoteserver subprocess."""
    argv = [cmd, "remoteserver", "--port", str(port), "--host", host]
    return subprocess.Popen(argv, **_platform.popen_flags())


@click.command("serve")
@click.option("--port", default=39920, show_default=True, help="Listen port.")
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind address.")
@click.option(
    "--allow-ips",
    default=None,
    metavar="CIDR[,CIDR...]",
    help="Comma-separated CIDR whitelist written to remoteserver.conf.",
)
@click.option("--no-exec", is_flag=True, help="Add 'noexec' to config (replay-only).")
@click.option("--daemon", "as_daemon", is_flag=True, help="Detach after printing PID.")
def serve_cmd(
    port: int,
    host: str,
    allow_ips: str | None,
    no_exec: bool,
    as_daemon: bool,
) -> None:
    """Launch renderdoccmd remoteserver for remote replay."""
    cmd_path = find_renderdoccmd()
    if cmd_path is None:
        click.echo("error: renderdoccmd not found", err=True)
        raise SystemExit(1)

    ip_list = allow_ips.split(",") if allow_ips else None
    conf_path = _remoteserver_conf_path()
    conf_path.parent.mkdir(parents=True, exist_ok=True)
    _platform.secure_write_text(conf_path, _generate_config(ip_list, no_exec))

    proc = _start_remoteserver(str(cmd_path), port, host)

    if as_daemon:
        click.echo(f"pid: {proc.pid}")
        return

    click.echo(f"serving on {host}:{port} (pid {proc.pid})")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    if proc.returncode and proc.returncode != 0:
        raise SystemExit(1)
