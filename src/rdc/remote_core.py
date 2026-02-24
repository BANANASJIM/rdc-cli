"""Remote capture core: connect, enumerate, and capture on remote RenderDoc servers."""

from __future__ import annotations

import re
from typing import Any

import click

from rdc.capture_core import CaptureResult, build_capture_options, run_target_control_loop

_PRIVATE_NETS = (
    re.compile(r"^10\."),
    re.compile(r"^172\.(1[6-9]|2\d|3[01])\."),
    re.compile(r"^192\.168\."),
    re.compile(r"^127\."),
    re.compile(r"^::1$"),
    re.compile(r"^localhost$", re.IGNORECASE),
)

DEFAULT_PORT = 39920


def warn_if_public(host: str) -> str | None:
    """Return warning message if host appears to be a public IP."""
    if any(p.match(host) for p in _PRIVATE_NETS):
        return None
    return f"warning: {host} is not a private IP — ensure remoteserver.conf restricts access"


def parse_url(url: str) -> tuple[str, int]:
    """Parse host[:port] string. Default port is 39920.

    IPv6 addresses must use brackets: [::1]:port
    """
    if url.startswith("["):
        # IPv6 bracket notation
        bracket_end = url.find("]")
        if bracket_end == -1:
            raise ValueError(f"malformed IPv6 address: {url!r}")
        host = url[1:bracket_end]
        if not host:
            raise ValueError(f"empty IPv6 address: {url!r}")
        rest = url[bracket_end + 1 :]
        if rest.startswith(":"):
            port_str = rest[1:]
            try:
                port = int(port_str)
            except ValueError:
                raise ValueError(f"invalid port: {port_str!r}") from None
            if not (1 <= port <= 65535):
                raise ValueError(f"invalid port: {port_str!r}")
            return host, port
        if rest:
            raise ValueError(f"unexpected content after IPv6 address: {url!r}")
        return host, DEFAULT_PORT
    if ":" in url:
        host, _, port_str = url.rpartition(":")
        if ":" in host:
            raise ValueError(f"IPv6 address must use brackets: [{url}]")
        try:
            port = int(port_str)
        except ValueError:
            raise ValueError(f"invalid port: {port_str!r}") from None
        if not (1 <= port <= 65535):
            raise ValueError(f"invalid port: {port_str!r}")
        return host, port
    return url, DEFAULT_PORT


def connect_remote_server(rd: Any, url: str) -> Any:
    """Connect to a remote RenderDoc server.

    Args:
        rd: The renderdoc module.
        url: Connection URL string (host or host:port).

    Returns:
        The IRemoteServer object.

    Raises:
        RuntimeError: On connection failure.
    """
    result, remote = rd.CreateRemoteServerConnection(url)
    if hasattr(result, "result"):
        code = result.result
    else:
        code = int(result)
    if code != 0:
        msg = f"connection failed (code {code})"
        raise RuntimeError(msg)
    return remote


def enumerate_remote_targets(rd: Any, url: str) -> list[int]:
    """List all active target idents on remote host. Max 1000 iterations."""
    targets: list[int] = []
    ident = 0
    for _ in range(1000):
        ident = rd.EnumerateRemoteTargets(url, ident)
        if ident == 0:
            break
        targets.append(ident)
    return targets


def remote_capture(
    rd: Any,
    remote: Any,
    url: str,
    app: str,
    *,
    args: str = "",
    workdir: str = "",
    output: str,
    opts: dict[str, Any] | None = None,
    frame: int | None = None,
    timeout: float = 60.0,
) -> CaptureResult:
    """Execute app on remote, capture frame, transfer to local.

    Args:
        rd: The renderdoc module.
        remote: IRemoteServer object.
        url: Remote host URL for CreateTargetControl.
        app: Path to executable on remote.
        args: Command-line arguments for the app.
        workdir: Working directory on remote.
        output: Local output path for the capture file.
        opts: CaptureOptions overrides dict.
        frame: Queue capture at specific frame number.
        timeout: Seconds to wait for a capture.

    Returns:
        CaptureResult with capture metadata.
    """
    capture_opts = build_capture_options(opts or {})
    env_mods: list[Any] = []
    exec_result = remote.ExecuteAndInject(app, workdir, args, env_mods, capture_opts)

    if exec_result.result != 0:
        return CaptureResult(error=f"remote inject failed (code {exec_result.result})")
    if exec_result.ident == 0:
        return CaptureResult(error="remote inject returned zero ident")

    tc = rd.CreateTargetControl(url, exec_result.ident, "rdc-cli", True)
    if tc is None:
        return CaptureResult(
            error=f"failed to connect to target ident={exec_result.ident}",
            ident=exec_result.ident,
        )

    try:
        result = run_target_control_loop(tc, frame=frame, timeout=timeout)
    finally:
        tc.Shutdown()

    if not result.success:
        result.ident = exec_result.ident
        return result

    # Transfer capture from remote to local
    if not result.local:
        try:
            remote.CopyCaptureFromRemote(result.path, output, None)
            result.path = output
            result.local = True
        except Exception as exc:
            result.success = False
            result.error = f"capture succeeded but transfer failed: {exc}"
            click.echo(f"warning: {result.error}", err=True)
            click.echo(f"  remote path: {result.path}", err=True)
    result.ident = exec_result.ident
    return result
