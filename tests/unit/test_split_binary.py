"""Tests for Phase S2: Split Binary Export."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from rdc._transport import recv_binary
from rdc.commands import _helpers as helpers_mod
from rdc.commands.export import rt_cmd
from rdc.commands.snapshot import snapshot_cmd
from rdc.commands.vfs import _deliver_binary
from rdc.daemon_client import send_request_binary
from rdc.handlers.core import HANDLERS, _handle_file_read
from rdc.session_state import SessionState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(pid: int = 0, host: str = "10.0.0.1", port: int = 5555) -> SessionState:
    return SessionState(
        capture="test.rdc",
        current_eid=0,
        opened_at="2026-01-01",
        host=host,
        port=port,
        token="tok",
        pid=pid,
    )


def _make_state(tmp_path: Path | None = None) -> Any:
    state = MagicMock()
    state.temp_dir = tmp_path
    state.token = "tok"
    return state


# ===========================================================================
# T1: recv_binary
# ===========================================================================


class TestRecvBinary:
    def test_exact_read(self) -> None:
        """T1.1: Read exactly N bytes in one chunk."""
        sock = MagicMock()
        sock.recv.return_value = b"hello"
        assert recv_binary(sock, 5) == b"hello"

    def test_partial_reads(self) -> None:
        """T1.2: Multiple small chunks summing to N."""
        sock = MagicMock()
        sock.recv.side_effect = [b"he", b"ll", b"o"]
        assert recv_binary(sock, 5) == b"hello"

    def test_premature_eof(self) -> None:
        """T1.3: Socket closes before N bytes."""
        sock = MagicMock()
        sock.recv.side_effect = [b"he", b""]
        with pytest.raises(OSError, match="connection closed"):
            recv_binary(sock, 5)

    def test_zero_bytes(self) -> None:
        """T1.4: Zero size returns empty bytes without reading."""
        sock = MagicMock()
        assert recv_binary(sock, 0) == b""
        sock.recv.assert_not_called()


# ===========================================================================
# T2: send_request_binary
# ===========================================================================


class TestSendRequestBinary:
    def _make_server_socket(self, response_line: bytes, binary_data: bytes = b"") -> int:
        """Create a one-shot TCP server returning fixed response. Returns port."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        import threading

        def _serve() -> None:
            conn, _ = srv.accept()
            conn.recv(4096)  # consume request
            conn.sendall(response_line + binary_data)
            conn.close()
            srv.close()

        threading.Thread(target=_serve, daemon=True).start()
        return port

    def test_no_binary_size(self) -> None:
        """T2.1: Response without _binary_size returns (dict, None)."""
        resp = json.dumps({"result": {"ok": True}}).encode() + b"\n"
        port = self._make_server_socket(resp)
        result, binary = send_request_binary("127.0.0.1", port, {"method": "ping"})
        assert result["result"]["ok"] is True
        assert binary is None

    def test_binary_size_zero(self) -> None:
        """T2.2: _binary_size: 0 returns (dict, b"")."""
        resp = json.dumps({"result": {"_binary_size": 0}}).encode() + b"\n"
        port = self._make_server_socket(resp)
        result, binary = send_request_binary("127.0.0.1", port, {"method": "test"})
        assert binary == b""

    def test_binary_size_positive(self) -> None:
        """T2.3: _binary_size: N reads N bytes."""
        payload = b"ABCDE"
        resp = json.dumps({"result": {"_binary_size": 5}}).encode() + b"\n"
        port = self._make_server_socket(resp, payload)
        result, binary = send_request_binary("127.0.0.1", port, {"method": "test"})
        assert binary == b"ABCDE"
        assert len(binary) == 5

    def test_error_response(self) -> None:
        """T2.4: Error response with no _binary_size."""
        resp = json.dumps({"error": {"code": -1, "message": "fail"}}).encode() + b"\n"
        port = self._make_server_socket(resp)
        result, binary = send_request_binary("127.0.0.1", port, {"method": "test"})
        assert "error" in result
        assert binary is None

    def test_connection_refused(self) -> None:
        """T2.5: Connection refused raises OSError."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        with pytest.raises(OSError):
            send_request_binary("127.0.0.1", port, {"method": "test"}, timeout=0.5)


# ===========================================================================
# T3: file_read handler
# ===========================================================================


class TestFileReadHandler:
    def test_happy_path(self, tmp_path: Path) -> None:
        """T3.1: Read a valid file under temp_dir."""
        f = tmp_path / "tex.png"
        f.write_bytes(b"PNG_DATA_1234")
        state = _make_state(tmp_path)
        resp, keep_running = _handle_file_read(1, {"path": str(f)}, state)
        assert resp["result"]["size"] == 13
        assert resp["result"]["_binary_size"] == 13
        assert resp["result"]["_binary_path"] == str(f.resolve())
        assert keep_running is True

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        """T3.2: Path traversal via '..' is rejected."""
        state = _make_state(tmp_path)
        resp, _ = _handle_file_read(1, {"path": str(tmp_path / "../etc/passwd")}, state)
        assert resp["error"]["code"] == -32602

    def test_absolute_outside_rejected(self, tmp_path: Path) -> None:
        """T3.3: Absolute path outside temp_dir is rejected."""
        state = _make_state(tmp_path)
        resp, _ = _handle_file_read(1, {"path": "/tmp/other_file"}, state)
        assert resp["error"]["code"] == -32602

    def test_file_not_found(self, tmp_path: Path) -> None:
        """T3.4: Path inside temp_dir that doesn't exist."""
        state = _make_state(tmp_path)
        resp, _ = _handle_file_read(1, {"path": str(tmp_path / "nonexistent.bin")}, state)
        assert "error" in resp

    def test_temp_dir_none(self) -> None:
        """T3.5: state.temp_dir is None."""
        state = _make_state(None)
        resp, _ = _handle_file_read(1, {"path": "/foo"}, state)
        assert resp["error"]["code"] == -32002

    def test_registered_in_handlers(self) -> None:
        """T3.6: file_read is registered in HANDLERS."""
        assert "file_read" in HANDLERS

    def test_file_read_in_no_replay_methods(self) -> None:
        """T3.7: file_read is in _NO_REPLAY_METHODS registry."""
        from rdc.daemon_server import _NO_REPLAY_METHODS

        assert "file_read" in _NO_REPLAY_METHODS


# ===========================================================================
# T5: fetch_remote_file
# ===========================================================================


class TestFetchRemoteFile:
    def test_local_pid_positive(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T5.1: pid > 0 reads file locally."""
        f = tmp_path / "data.bin"
        f.write_bytes(b"local_data")
        session = _make_session(pid=1234)
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)
        result = helpers_mod.fetch_remote_file(str(f))
        assert result == b"local_data"

    def test_remote_pid_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T5.2: pid == 0 calls file_read via RPC."""
        session = _make_session(pid=0)
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)
        monkeypatch.setattr(
            helpers_mod,
            "send_request_binary",
            lambda *a, **kw: ({"result": {"size": 5, "_binary_size": 5}}, b"hello"),
        )
        monkeypatch.setattr(
            helpers_mod,
            "send_request",
            lambda *a, **kw: {"result": {"ok": True}},
        )
        result = helpers_mod.fetch_remote_file("/tmp/rdc-xxx/tex.png")
        assert result == b"hello"

    def test_remote_rpc_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T5.3: pid == 0, RPC returns error."""
        session = _make_session(pid=0)
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)
        monkeypatch.setattr(
            helpers_mod,
            "send_request_binary",
            lambda *a, **kw: ({"error": {"code": -1, "message": "fail"}}, None),
        )
        monkeypatch.setattr(
            helpers_mod,
            "send_request",
            lambda *a, **kw: {"result": {"ok": True}},
        )
        with pytest.raises(SystemExit):
            helpers_mod.fetch_remote_file("/tmp/rdc-xxx/tex.png")

    def test_remote_none_binary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T5.4: pid == 0, RPC returns None binary."""
        session = _make_session(pid=0)
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)
        monkeypatch.setattr(
            helpers_mod,
            "send_request_binary",
            lambda *a, **kw: ({"result": {"size": 5}}, None),
        )
        monkeypatch.setattr(
            helpers_mod,
            "send_request",
            lambda *a, **kw: {"result": {"ok": True}},
        )
        with pytest.raises(SystemExit):
            helpers_mod.fetch_remote_file("/tmp/rdc-xxx/tex.png")


# ===========================================================================
# T6: call_binary
# ===========================================================================


class TestCallBinary:
    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T6.1: Successful binary call."""
        monkeypatch.setattr(helpers_mod, "require_session", lambda: ("localhost", 9999, "tok"))
        monkeypatch.setattr(
            helpers_mod,
            "send_request_binary",
            lambda *a, **kw: ({"result": {"foo": 1}}, b"data"),
        )
        result, binary = helpers_mod.call_binary("test", {})
        assert result == {"foo": 1}
        assert binary == b"data"

    def test_error_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T6.2: Error response exits."""
        monkeypatch.setattr(helpers_mod, "require_session", lambda: ("localhost", 9999, "tok"))
        monkeypatch.setattr(
            helpers_mod,
            "send_request_binary",
            lambda *a, **kw: ({"error": {"code": -1, "message": "fail"}}, None),
        )
        with pytest.raises(SystemExit):
            helpers_mod.call_binary("test", {})

    def test_connection_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T6.3: Connection error exits."""
        monkeypatch.setattr(helpers_mod, "require_session", lambda: ("localhost", 9999, "tok"))

        def raise_os(*a: Any, **kw: Any) -> None:
            raise OSError("refused")

        monkeypatch.setattr(helpers_mod, "send_request_binary", raise_os)
        with pytest.raises(SystemExit):
            helpers_mod.call_binary("test", {})


# ===========================================================================
# T7: rdc rt --overlay (Split path)
# ===========================================================================


_OVERLAY_RESPONSE: dict[str, Any] = {
    "path": "/tmp/rdc-xxx/overlay.png",
    "size": 100,
    "overlay": "Wireframe",
    "eid": 10,
}


class TestRtOverlaySplit:
    def test_local_with_output(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T7.1: Local daemon writes file via fetch_remote_file."""
        out_file = tmp_path / "out.png"
        png_bytes = b"\x89PNG_local"
        src_file = tmp_path / "overlay.png"
        src_file.write_bytes(png_bytes)
        resp = {**_OVERLAY_RESPONSE, "path": str(src_file)}

        monkeypatch.setattr("rdc.commands.export.call", lambda *a, **kw: resp)
        monkeypatch.setattr("rdc.commands.export.load_session", lambda: _make_session(pid=1234))
        # fetch_remote_file with pid>0 reads local file
        monkeypatch.setattr(helpers_mod, "load_session", lambda: _make_session(pid=1234))

        runner = CliRunner()
        result = runner.invoke(rt_cmd, ["10", "--overlay", "wireframe", "-o", str(out_file)])
        assert result.exit_code == 0
        assert out_file.read_bytes() == png_bytes

    def test_remote_with_output(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T7.2: Remote daemon fetches file via RPC."""
        out_file = tmp_path / "out.png"
        png_bytes = b"\x89PNG_remote"

        monkeypatch.setattr("rdc.commands.export.call", lambda *a, **kw: dict(_OVERLAY_RESPONSE))
        monkeypatch.setattr("rdc.commands.export.fetch_remote_file", lambda p: png_bytes)

        runner = CliRunner()
        result = runner.invoke(rt_cmd, ["10", "--overlay", "wireframe", "-o", str(out_file)])
        assert result.exit_code == 0
        assert out_file.read_bytes() == png_bytes

    def test_local_no_output_prints_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T7.3: Local daemon without --output prints path."""
        monkeypatch.setattr("rdc.commands.export.call", lambda *a, **kw: dict(_OVERLAY_RESPONSE))
        monkeypatch.setattr("rdc.commands.export.load_session", lambda: _make_session(pid=1234))

        runner = CliRunner()
        result = runner.invoke(rt_cmd, ["10", "--overlay", "wireframe"])
        assert result.exit_code == 0
        assert _OVERLAY_RESPONSE["path"] in result.output

    def test_remote_no_output_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T7.4: Remote daemon without --output errors."""
        monkeypatch.setattr("rdc.commands.export.call", lambda *a, **kw: dict(_OVERLAY_RESPONSE))
        monkeypatch.setattr("rdc.commands.export.load_session", lambda: _make_session(pid=0))

        runner = CliRunner()
        result = runner.invoke(rt_cmd, ["10", "--overlay", "wireframe"])
        assert result.exit_code == 1
        assert "--output is required" in result.output


# ===========================================================================
# T8: rdc snapshot (Split path)
# ===========================================================================


_PIPELINE_RESPONSE = {"eid": 142, "row": {"stages": []}}
_SESSION_TUPLE = ("localhost", 9999, "tok")


class TestSnapshotSplit:
    def _setup_snapshot(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        pid: int,
        color_targets: int = 1,
        has_depth: bool = True,
    ) -> Path:
        out_dir = tmp_path / "snap"
        session = _make_session(pid=pid)

        # For fetch_remote_file (pid > 0 reads local, pid == 0 needs mock)
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)

        # Create temp PNG files for rt_export / rt_depth
        color_paths = []
        for i in range(color_targets):
            p = tmp_path / f"color{i}.png"
            p.write_bytes(b"\x89PNG_color" + str(i).encode())
            color_paths.append(str(p))

        depth_path = None
        if has_depth:
            dp = tmp_path / "depth.png"
            dp.write_bytes(b"\x89PNG_depth")
            depth_path = str(dp)

        def mock_send(host: str, port: int, payload: dict[str, Any], **kw: Any) -> dict[str, Any]:
            method = payload["method"]
            params = payload.get("params", {})
            if method == "shader_all":
                return {"result": {"eid": 142, "stages": []}}
            if method == "shader_disasm":
                return {"result": {"disasm": ""}}
            if method == "rt_export":
                idx = params.get("target", 0)
                if idx < color_targets:
                    return {"result": {"path": color_paths[idx], "size": 100}}
                return {"error": {"code": -1, "message": "out of range"}}
            if method == "rt_depth":
                if has_depth and depth_path:
                    return {"result": {"path": depth_path, "size": 100}}
                return {"error": {"code": -1, "message": "no depth"}}
            if method == "ping":
                return {"result": {"ok": True}}
            return {"result": {}}

        monkeypatch.setattr(helpers_mod, "send_request", mock_send)
        monkeypatch.setattr(helpers_mod, "require_session", lambda: _SESSION_TUPLE)
        monkeypatch.setattr("rdc.commands.snapshot.call", lambda *a, **kw: _PIPELINE_RESPONSE)

        return out_dir

    def test_local_daemon(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T8.1: Local daemon copies color and depth files."""
        out_dir = self._setup_snapshot(monkeypatch, tmp_path, pid=1234)
        runner = CliRunner()
        result = runner.invoke(snapshot_cmd, ["142", "-o", str(out_dir)])
        assert result.exit_code == 0
        assert (out_dir / "color0.png").exists()
        assert (out_dir / "depth.png").exists()

    def test_remote_daemon(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T8.2: Remote daemon uses fetch_remote_file."""
        out_dir = self._setup_snapshot(monkeypatch, tmp_path, pid=0)
        # For pid==0, fetch_remote_file calls call_binary. Mock it.
        monkeypatch.setattr(
            helpers_mod,
            "send_request_binary",
            lambda *a, **kw: ({"result": {"size": 10, "_binary_size": 10}}, b"\x89PNG_mock"),
        )
        runner = CliRunner()
        result = runner.invoke(snapshot_cmd, ["142", "-o", str(out_dir)])
        assert result.exit_code == 0
        assert (out_dir / "color0.png").exists()
        assert (out_dir / "depth.png").exists()

    def test_no_color_targets(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T8.3: rt_export returns None; no color files."""
        out_dir = self._setup_snapshot(monkeypatch, tmp_path, pid=1234, color_targets=0)
        runner = CliRunner()
        result = runner.invoke(snapshot_cmd, ["142", "-o", str(out_dir)])
        assert result.exit_code == 0
        assert not list(out_dir.glob("color*.png"))

    def test_no_depth(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T8.4: rt_depth returns None; no depth file."""
        out_dir = self._setup_snapshot(monkeypatch, tmp_path, pid=1234, has_depth=False)
        runner = CliRunner()
        result = runner.invoke(snapshot_cmd, ["142", "-o", str(out_dir)])
        assert result.exit_code == 0
        assert not (out_dir / "depth.png").exists()


# ===========================================================================
# T9: Security / edge cases
# ===========================================================================


class TestFileReadSecurity:
    def test_symlink_escape(self, tmp_path: Path) -> None:
        """T9.1: Symlink pointing outside temp_dir is rejected."""
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("secret")

        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        link = temp_dir / "escape"
        link.symlink_to(secret)

        state = _make_state(temp_dir)
        resp, _ = _handle_file_read(1, {"path": str(link)}, state)
        assert resp["error"]["code"] == -32602

    def test_empty_path(self, tmp_path: Path) -> None:
        """T9.2: Empty path param."""
        state = _make_state(tmp_path)
        resp, _ = _handle_file_read(1, {"path": ""}, state)
        assert "error" in resp


# ===========================================================================
# T10: _deliver_binary / rdc cat / rdc texture / rdc buffer (Split path)
# ===========================================================================


class TestDeliverBinarySplit:
    def _make_match(self, handler: str = "rt_export", args: dict[str, Any] | None = None) -> Any:
        match = MagicMock()
        match.handler = handler
        match.args = args or {"eid": 1, "target": 0}
        return match

    def test_local_with_output(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T10.1: Local daemon with -o uses shutil.move."""
        temp_file = tmp_path / "buf.bin"
        temp_file.write_bytes(b"local_binary")
        out_file = tmp_path / "out.bin"

        monkeypatch.setattr("rdc.commands.vfs.call", lambda *a, **kw: {"path": str(temp_file)})
        monkeypatch.setattr("rdc.commands.vfs._load_session", lambda: _make_session(pid=1234))
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: False)

        match = self._make_match()
        _deliver_binary("/test/path", match, False, str(out_file))
        assert out_file.exists()

    def test_remote_with_output(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T10.2: Remote daemon with -o uses fetch_remote_file."""
        out_file = tmp_path / "out.bin"
        monkeypatch.setattr(
            "rdc.commands.vfs.call", lambda *a, **kw: {"path": "/tmp/rdc-xxx/buf.bin"}
        )
        monkeypatch.setattr("rdc.commands.vfs._load_session", lambda: _make_session(pid=0))
        monkeypatch.setattr("rdc.commands.vfs.fetch_remote_file", lambda p: b"remote_binary")
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: False)

        match = self._make_match()
        _deliver_binary("/test/path", match, False, str(out_file))
        assert out_file.read_bytes() == b"remote_binary"

    def test_remote_pipe_mode(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T10.3: Remote daemon piped writes to stdout.buffer."""
        import io

        buf = io.BytesIO()
        monkeypatch.setattr(
            "rdc.commands.vfs.call", lambda *a, **kw: {"path": "/tmp/rdc-xxx/buf.bin"}
        )
        monkeypatch.setattr("rdc.commands.vfs._load_session", lambda: _make_session(pid=0))
        monkeypatch.setattr("rdc.commands.vfs.fetch_remote_file", lambda p: b"piped_data")
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: False)
        monkeypatch.setattr("sys.stdout", MagicMock(buffer=buf))

        match = self._make_match()
        _deliver_binary("/test/path", match, True, None)
        assert buf.getvalue() == b"piped_data"

    def test_no_path_in_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T10.6: Handler returns no 'path' key."""
        monkeypatch.setattr("rdc.commands.vfs.call", lambda *a, **kw: {"size": 42})
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: False)

        match = self._make_match()
        with pytest.raises(SystemExit):
            _deliver_binary("/test/path", match, True, None)
