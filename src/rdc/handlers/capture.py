"""Daemon handlers for CLI capture and remote capture commands."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from rdc.capture_core import (
    CaptureResult,
    build_capture_options,
    execute_and_capture,
    terminate_process,
)
from rdc.discover import find_renderdoc
from rdc.handlers._helpers import _error_response, _result_response
from rdc.handlers._types import Handler
from rdc.remote_core import (
    build_conn_url,
    connect_remote_server,
    enumerate_remote_targets,
    remote_capture,
)


def _renderdoc_or_error(request_id: int) -> tuple[Any, tuple[dict[str, Any], bool] | None]:
    rd = find_renderdoc()
    if rd is None:
        return rd, (_error_response(request_id, -32002, "renderdoc module not available"), True)
    return rd, None


def _resolve_output_path(state: Any, requested: str, fallback: str) -> str:
    temp_dir = getattr(state, "temp_dir", None)
    name = Path(requested or fallback).name or fallback
    if temp_dir:
        return str(Path(temp_dir) / name)
    return requested or fallback


def _serialize(result: CaptureResult) -> dict[str, Any]:
    return asdict(result)


def _handle_capture_run(
    request_id: int, params: dict[str, Any], state: Any
) -> tuple[dict[str, Any], bool]:
    rd, error = _renderdoc_or_error(request_id)
    if error is not None:
        return error
    app = params.get("app")
    if not app:
        return _error_response(request_id, -32602, "missing app parameter"), True
    args = params.get("args", "")
    workdir = params.get("workdir", "")
    output = params.get("output", "")
    output_local = _resolve_output_path(state, output, "capture.rdc")
    opts_dict = params.get("opts", {}) or {}
    frame = params.get("frame")
    trigger = bool(params.get("trigger", False))
    timeout = float(params.get("timeout", 60.0))
    wait_for_exit = bool(params.get("wait_for_exit", False))
    keep_alive = bool(params.get("keep_alive", False))

    cap_opts = build_capture_options(opts_dict)
    result = execute_and_capture(
        rd,
        app,
        args=args,
        workdir=workdir,
        output=output_local,
        opts=cap_opts,
        frame=frame,
        trigger=trigger,
        timeout=timeout,
        wait_for_exit=wait_for_exit,
    )
    if not trigger and not keep_alive and result.pid:
        terminate_process(result.pid)
    return _result_response(request_id, _serialize(result)), True


def _handle_remote_connect(
    request_id: int, params: dict[str, Any], state: Any
) -> tuple[dict[str, Any], bool]:
    rd, error = _renderdoc_or_error(request_id)
    if error is not None:
        return error
    host = params.get("host")
    port = params.get("port")
    if not host or not isinstance(host, str):
        return _error_response(request_id, -32602, "missing host"), True
    if not isinstance(port, int):
        return _error_response(request_id, -32602, "missing port"), True
    conn_url = build_conn_url(host, port)
    try:
        remote = connect_remote_server(rd, conn_url)
    except RuntimeError as exc:  # noqa: BLE001
        return _error_response(request_id, -32002, str(exc)), True

    try:
        remote.Ping()
    finally:
        remote.ShutdownConnection()

    return _result_response(request_id, {"host": host, "port": port}), True


def _handle_remote_list(
    request_id: int, params: dict[str, Any], state: Any
) -> tuple[dict[str, Any], bool]:
    rd, error = _renderdoc_or_error(request_id)
    if error is not None:
        return error
    host = params.get("host")
    port = params.get("port")
    if not host or not isinstance(host, str):
        return _error_response(request_id, -32602, "missing host"), True
    if not isinstance(port, int):
        return _error_response(request_id, -32602, "missing port"), True
    conn_url = build_conn_url(host, port)
    targets: list[dict[str, Any]] = []
    for ident in enumerate_remote_targets(rd, conn_url):
        tc = rd.CreateTargetControl(conn_url, ident, "rdc-cli", False)
        if tc is None:
            targets.append({"ident": ident, "target": "unknown", "pid": 0, "api": "unknown"})
            continue
        try:
            targets.append(
                {
                    "ident": ident,
                    "target": tc.GetTarget(),
                    "pid": tc.GetPID(),
                    "api": tc.GetAPI(),
                }
            )
        finally:
            tc.Shutdown()
    return _result_response(request_id, {"targets": targets}), True


def _handle_remote_capture(
    request_id: int, params: dict[str, Any], state: Any
) -> tuple[dict[str, Any], bool]:
    rd, error = _renderdoc_or_error(request_id)
    if error is not None:
        return error
    host = params.get("host")
    port = params.get("port")
    if not host or not isinstance(host, str):
        return _error_response(request_id, -32602, "missing host"), True
    if not isinstance(port, int):
        return _error_response(request_id, -32602, "missing port"), True
    app = params.get("app")
    if not app:
        return _error_response(request_id, -32602, "missing app parameter"), True
    output = params.get("output")
    if not output:
        return _error_response(request_id, -32602, "missing output parameter"), True

    conn_url = build_conn_url(host, port)
    try:
        remote = connect_remote_server(rd, conn_url)
    except RuntimeError as exc:  # noqa: BLE001
        return _error_response(request_id, -32002, str(exc)), True

    output_local = _resolve_output_path(state, output, "remote-capture.rdc")

    try:
        result = remote_capture(
            rd,
            remote,
            conn_url,
            app,
            args=params.get("args", ""),
            workdir=params.get("workdir", ""),
            output=output_local,
            opts=params.get("opts", {}) or {},
            frame=params.get("frame"),
            timeout=float(params.get("timeout", 60.0)),
            keep_remote=bool(params.get("keep_remote", False)),
        )
    finally:
        remote.ShutdownConnection()

    return _result_response(request_id, _serialize(result)), True


_handle_capture_run._no_replay = True  # type: ignore[attr-defined]
_handle_remote_connect._no_replay = True  # type: ignore[attr-defined]
_handle_remote_list._no_replay = True  # type: ignore[attr-defined]
_handle_remote_capture._no_replay = True  # type: ignore[attr-defined]


HANDLERS: dict[str, Handler] = {
    "capture_run": _handle_capture_run,
    "remote_connect_run": _handle_remote_connect,
    "remote_list_run": _handle_remote_list,
    "remote_capture_run": _handle_remote_capture,
}
