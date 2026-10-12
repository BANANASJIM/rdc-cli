"""Connection failures must stay local to one RPC and leave useful diagnostics."""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TextIO
from unittest.mock import MagicMock

import pytest

from rdc import daemon_server
from rdc.protocol import shutdown_request, status_request
from rdc.services import session_service

_TOKEN = "private-session-token-do-not-log"


def _connection(
    request: dict[str, object] | None = None,
    *,
    recv_error: Exception | None = None,
    send_error: Exception | None = None,
) -> MagicMock:
    conn = MagicMock(spec=socket.socket)
    conn.__enter__.return_value = conn
    if recv_error is not None:
        conn.recv.side_effect = recv_error
    else:
        conn.recv.return_value = (json.dumps(request) + "\n").encode()
    if send_error is not None:
        conn.sendall.side_effect = send_error
    return conn


def _serve(
    monkeypatch: pytest.MonkeyPatch, *connections: MagicMock, temp_dir: Path | None = None
) -> MagicMock:
    """Inject only socket I/O; exercise the real dispatcher and status/shutdown."""
    listener = MagicMock(spec=socket.socket)
    listener.__enter__.return_value = listener
    listener.accept.side_effect = [(conn, ("127.0.0.1", 12345)) for conn in connections]
    monkeypatch.setattr(daemon_server.socket, "socket", lambda *_a, **_kw: listener)
    state = daemon_server.DaemonState(capture="test.rdc", current_eid=42, token=_TOKEN)
    state.temp_dir = temp_dir
    daemon_server.run_server("127.0.0.1", 39999, state, idle_timeout_s=0)
    return listener


def _assert_status_and_shutdown(status: MagicMock, shutdown: MagicMock) -> None:
    response = json.loads(status.sendall.call_args.args[0])
    assert response["id"] == 2
    assert response["result"]["current_eid"] == 42
    assert response["result"]["capture"] == "test.rdc"
    assert json.loads(shutdown.sendall.call_args.args[0])["result"]["ok"] is True


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionResetError(10054, "peer reset connection"),
        TimeoutError("peer did not finish sending"),
        ValueError("recv_line: message exceeds max_bytes limit"),
    ],
    ids=["reset", "timeout", "oversized-request"],
)
def test_receive_failure_does_not_block_later_status(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failure: Exception,
) -> None:
    broken = _connection(recv_error=failure)
    status = _connection(status_request(_TOKEN, 2))
    shutdown = _connection(shutdown_request(_TOKEN, 3))
    with caplog.at_level(logging.INFO, logger="rdc.daemon"):
        listener = _serve(monkeypatch, broken, status, shutdown)

    assert listener.accept.call_count == 3
    broken.sendall.assert_not_called()
    _assert_status_and_shutdown(status, shutdown)
    assert any(
        record.levelno == logging.WARNING and "RPC receive failed" in record.getMessage()
        for record in caplog.records
    )
    assert _TOKEN not in caplog.text


@pytest.mark.parametrize(
    "failure",
    [ConnectionResetError(10054, "peer reset connection"), BrokenPipeError("peer closed")],
    ids=["reset", "broken-pipe"],
)
def test_send_failure_does_not_block_later_status(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failure: Exception,
) -> None:
    broken = _connection(status_request(_TOKEN, 1), send_error=failure)
    status = _connection(status_request(_TOKEN, 2))
    shutdown = _connection(shutdown_request(_TOKEN, 3))
    with caplog.at_level(logging.INFO, logger="rdc.daemon"):
        listener = _serve(monkeypatch, broken, status, shutdown)

    assert listener.accept.call_count == 3
    broken.sendall.assert_called_once()
    _assert_status_and_shutdown(status, shutdown)
    assert any(
        record.levelno == logging.WARNING
        and "RPC send failed" in record.getMessage()
        and "method=status" in record.getMessage()
        and "id=1" in record.getMessage()
        and "stage=response" in record.getMessage()
        for record in caplog.records
    )
    assert not any(
        "RPC response sent" in record.getMessage() and "id=1" in record.getMessage()
        for record in caplog.records
    )
    assert _TOKEN not in caplog.text


def test_rpc_diagnostics_record_phases_without_request_params(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    request = status_request(_TOKEN, 2)
    request["params"]["private_note"] = "private-request-param-do-not-log"
    status = _connection(request)
    shutdown = _connection(shutdown_request(_TOKEN, 3))
    with caplog.at_level(logging.INFO, logger="rdc.daemon"):
        _serve(monkeypatch, status, shutdown)

    _assert_status_and_shutdown(status, shutdown)
    messages = [record.getMessage() for record in caplog.records if record.levelno == logging.INFO]
    for phase in ("RPC request started", "RPC handler completed", "RPC response sent"):
        assert any(
            phase in message and "method=status" in message and "id=2" in message
            for message in messages
        )
    for phase in ("RPC handler completed", "RPC response sent"):
        assert any(
            phase in message and "id=2" in message and "elapsed_ms=" in message
            for message in messages
        )
    assert _TOKEN not in caplog.text
    assert "private-request-param-do-not-log" not in caplog.text


def test_binary_send_reset_reports_stage_and_allows_later_status(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    data_dir = tmp_path / "exports"
    data_dir.mkdir()
    data_path = data_dir / "output.bin"
    data_path.write_bytes(b"binary payload")
    request = {"id": 1, "method": "file_read", "params": {"_token": _TOKEN, "path": str(data_path)}}
    broken = _connection(request)
    broken.sendall.side_effect = [None, ConnectionResetError(10054, "peer reset connection")]
    status = _connection(status_request(_TOKEN, 2))
    shutdown = _connection(shutdown_request(_TOKEN, 3))
    with caplog.at_level(logging.INFO, logger="rdc.daemon"):
        _serve(monkeypatch, broken, status, shutdown, temp_dir=data_dir)

    assert broken.sendall.call_count == 2
    _assert_status_and_shutdown(status, shutdown)
    assert "RPC send failed: method=file_read id=1 stage=binary payload" in caplog.text
    assert not any(
        "RPC response sent" in record.getMessage() and "id=1" in record.getMessage()
        for record in caplog.records
    )
    assert _TOKEN not in caplog.text


@pytest.mark.parametrize("env_value", [None, ""], ids=["unset", "empty"])
def test_diagnostics_are_opt_in(monkeypatch: pytest.MonkeyPatch, env_value: str | None) -> None:
    if env_value is None:
        monkeypatch.delenv("RDC_DAEMON_LOG", raising=False)
    else:
        monkeypatch.setenv("RDC_DAEMON_LOG", env_value)
    enable = MagicMock()
    monkeypatch.setattr(daemon_server.faulthandler, "enable", enable)
    logger = logging.Logger("test-diagnostics-disabled")
    monkeypatch.setattr(daemon_server, "_log", logger)

    assert daemon_server._configure_diagnostics() is None
    assert logger.handlers == []
    enable.assert_not_called()


def test_diagnostics_file_records_rpc_without_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "daemon.log"
    monkeypatch.setenv("RDC_DAEMON_LOG", str(log_path))
    enable = MagicMock()
    monkeypatch.setattr(daemon_server.faulthandler, "enable", enable)
    logger = logging.Logger("test-diagnostics-enabled")
    monkeypatch.setattr(daemon_server, "_log", logger)

    handler = daemon_server._configure_diagnostics()
    assert isinstance(handler, logging.FileHandler)
    try:
        enable.assert_called_once_with(file=handler.stream, all_threads=True)
        assert logger.getEffectiveLevel() == logging.INFO
        status = _connection(status_request(_TOKEN, 2))
        shutdown = _connection(shutdown_request(_TOKEN, 3))
        _serve(monkeypatch, status, shutdown)
        handler.flush()
        contents = log_path.read_text(encoding="utf-8")
        assert f"pid={os.getpid()}" in contents
        assert "python=" in contents and sys.platform in contents
        assert "RPC request started: method=status id=2" in contents
        assert "RPC handler completed: method=status id=2 elapsed_ms=" in contents
        assert "RPC response sent: method=status id=2 elapsed_ms=" in contents
        assert _TOKEN not in contents
    finally:
        logger.removeHandler(handler)
        handler.close()


def test_main_logs_loaded_replay_version_and_module(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["daemon_server", "--port", "39999", "--capture", "test.rdc", "--token", _TOKEN],
    )
    monkeypatch.setattr(daemon_server._platform, "install_shutdown_signal", lambda: None)
    monkeypatch.setattr(daemon_server, "_configure_diagnostics", lambda: None)
    serve = MagicMock()
    monkeypatch.setattr(daemon_server, "run_server", serve)

    def load_replay(state: daemon_server.DaemonState) -> None:
        state.rd = SimpleNamespace(
            GetVersionString=lambda: "1.46", __file__="actual-renderdoc-module.pyd"
        )
        state.api_name = "Vulkan"

    monkeypatch.setattr(daemon_server, "_load_replay", load_replay)
    with caplog.at_level(logging.INFO, logger="rdc.daemon"):
        daemon_server.main()

    serve.assert_called_once()
    assert (
        "replay ready: renderdoc=(1, 46) module=actual-renderdoc-module.pyd api=Vulkan"
        in caplog.text
    )
    assert _TOKEN not in caplog.text


def test_start_daemon_appends_native_stderr_to_separate_diagnostics_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "daemon.log"
    log_path.write_text("previous RPC diagnostics\n", encoding="utf-8")
    stderr_path = Path(str(log_path) + ".stderr")
    stderr_path.write_text("previous native stderr\n", encoding="utf-8")
    monkeypatch.setenv("RDC_DAEMON_LOG", str(log_path))
    monkeypatch.setattr(session_service, "_renderdoc_available", lambda: False)
    proc = MagicMock()
    streams: list[TextIO] = []

    def popen(_cmd: list[str], **kwargs: Any) -> MagicMock:
        stream = kwargs["stderr"]
        streams.append(stream)
        assert Path(stream.name) == stderr_path
        stream.write("native replay stderr\n")
        stream.flush()
        return proc

    monkeypatch.setattr(session_service.subprocess, "Popen", popen)
    assert session_service.start_daemon("test.rdc", 39999, _TOKEN) is proc
    assert proc._rdc_stderr_path == str(stderr_path)
    assert proc._rdc_preserve_stderr is True
    assert streams[0].closed
    assert (
        stderr_path.read_text(encoding="utf-8") == "previous native stderr\nnative replay stderr\n"
    )
    assert log_path.read_text(encoding="utf-8") == "previous RPC diagnostics\n"


@pytest.mark.parametrize(
    "cleanup", ["read", "discard"], ids=["failed-startup", "successful-startup"]
)
def test_requested_native_stderr_file_survives_cleanup(tmp_path: Path, cleanup: str) -> None:
    log_path = tmp_path / "daemon.log"
    log_path.write_text("RPC diagnostics\n", encoding="utf-8")
    stderr_path = Path(str(log_path) + ".stderr")
    contents = "\n".join(f"diagnostic line {i}" for i in range(25)) + "\n"
    stderr_path.write_text(contents, encoding="utf-8")
    proc = MagicMock()
    proc._rdc_stderr_path = str(stderr_path)
    proc._rdc_preserve_stderr = True

    if cleanup == "read":
        assert session_service._read_daemon_stderr(proc) == "\n".join(contents.splitlines()[-20:])
    else:
        session_service._discard_daemon_stderr(proc)

    assert stderr_path.read_text(encoding="utf-8") == contents
    assert log_path.read_text(encoding="utf-8") == "RPC diagnostics\n"
