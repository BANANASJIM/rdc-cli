"""Tests for Phase S1: Split Core (--listen/--connect/--proxy, pid==0 guards)."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from rdc.cli import main
from rdc.services import session_service
from rdc.session_state import SessionState  # noqa: I001

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(
    pid: int = 0,
    host: str = "10.0.0.1",
    port: int = 5555,
    token: str = "tok",
    capture: str = "test.rdc",
) -> SessionState:
    return SessionState(
        capture=capture,
        current_eid=0,
        opened_at="2026-01-01",
        host=host,
        port=port,
        token=token,
        pid=pid,
    )


def _setup_no_replay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)


# ===========================================================================
# T1: --proxy / --remote deprecation
# ===========================================================================


class TestProxyRemoteDeprecation:
    def test_proxy_passed_to_open_session(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()

        called_with: dict[str, Any] = {}

        def fake_open(cap: Any, *, remote_url: str | None = None) -> tuple[bool, str]:
            called_with["remote_url"] = remote_url
            return True, f"opened: {cap}"

        monkeypatch.setattr("rdc.commands.session.open_session", fake_open)
        runner = CliRunner()
        result = runner.invoke(main, ["open", str(capture), "--proxy", "host:9000"])
        assert result.exit_code == 0
        assert called_with["remote_url"] == "host:9000"

    def test_remote_triggers_deprecation_warning(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()
        monkeypatch.setattr(
            "rdc.commands.session.open_session",
            lambda *a, **kw: (True, "opened: c.rdc"),
        )
        runner = CliRunner()
        result = runner.invoke(main, ["open", str(capture), "--remote", "host:9000"])
        assert result.exit_code == 0
        assert "deprecated" in result.stderr

    def test_remote_hidden_proxy_visible_in_help(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """T1-3: --remote is hidden, --proxy is visible in help output."""
        _setup_no_replay(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["open", "--help"])
        assert "--proxy" in result.output
        assert "--remote" not in result.output

    def test_remote_value_forwards_to_proxy(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()

        called_with: dict[str, Any] = {}

        def fake_open(cap: Any, *, remote_url: str | None = None) -> tuple[bool, str]:
            called_with["remote_url"] = remote_url
            return True, f"opened: {cap}"

        monkeypatch.setattr("rdc.commands.session.open_session", fake_open)
        runner = CliRunner()
        result = runner.invoke(main, ["open", str(capture), "--remote", "host:9000"])
        assert result.exit_code == 0
        assert called_with["remote_url"] == "host:9000"


# ===========================================================================
# T2: --listen variants
# ===========================================================================


class TestListenOption:
    def test_listen_auto_port(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()

        def _fake_listen(cap: str, addr: str, **kw: Any) -> tuple[bool, dict[str, Any]]:
            return True, {
                "host": "0.0.0.0",
                "port": 12345,
                "token": "abc",
                "capture": cap,
            }

        monkeypatch.setattr("rdc.commands.session.listen_open_session", _fake_listen)
        runner = CliRunner()
        result = runner.invoke(main, ["open", str(capture), "--listen", ":0"])
        assert result.exit_code == 0
        assert "listening" in result.output
        assert "12345" in result.output
        assert "abc" in result.output

    def test_listen_with_addr_port(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()

        called_addr: list[str] = []

        def fake_listen(cap: str, addr: str, **kw: Any) -> tuple[bool, dict[str, Any]]:
            called_addr.append(addr)
            return True, {"host": "192.168.1.1", "port": 7777, "token": "xyz", "capture": cap}

        monkeypatch.setattr("rdc.commands.session.listen_open_session", fake_listen)
        runner = CliRunner()
        result = runner.invoke(main, ["open", str(capture), "--listen", "192.168.1.1:7777"])
        assert result.exit_code == 0
        assert called_addr == ["192.168.1.1:7777"]

    def test_listen_with_proxy(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()

        called_kw: dict[str, Any] = {}

        def fake_listen(cap: str, addr: str, **kw: Any) -> tuple[bool, dict[str, Any]]:
            called_kw.update(kw)
            return True, {"host": "0.0.0.0", "port": 8888, "token": "t", "capture": cap}

        monkeypatch.setattr("rdc.commands.session.listen_open_session", fake_listen)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["open", str(capture), "--listen", ":0", "--proxy", "remote:5000"],
        )
        assert result.exit_code == 0
        assert called_kw.get("remote_url") == "remote:5000"

    def test_listen_daemon_fails(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()

        monkeypatch.setattr(
            "rdc.commands.session.listen_open_session",
            lambda *a, **kw: (False, "error: daemon failed to start (timeout)"),
        )
        runner = CliRunner()
        result = runner.invoke(main, ["open", str(capture), "--listen", ":0"])
        assert result.exit_code == 1
        assert "daemon failed" in result.output

    def test_listen_file_not_found(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["open", "/nonexistent.rdc", "--listen", ":0"])
        assert result.exit_code == 1
        assert "file not found" in result.output

    def test_listen_mutually_exclusive_with_connect(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["open", "--connect", "host:1234", "--token", "tok", "--listen", ":0"]
        )
        assert result.exit_code == 1
        assert "mutually exclusive" in result.output

    def test_listen_invalid_port(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T2-7: --listen with non-numeric port produces clean error."""
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()
        runner = CliRunner()
        result = runner.invoke(main, ["open", str(capture), "--listen", "0.0.0.0:abc"])
        assert result.exit_code == 1
        assert "invalid port" in result.output

    def test_listen_port_in_use(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """T2-7: --listen when port is already bound produces error."""
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            bound_port = sock.getsockname()[1]

            def fake_listen(cap: str, addr: str, **kw: Any) -> tuple[bool, str]:
                msg = f"error: daemon failed to start (bind to 127.0.0.1:{bound_port} failed)"
                return False, msg

            monkeypatch.setattr("rdc.commands.session.listen_open_session", fake_listen)
            runner = CliRunner()
            result = runner.invoke(
                main, ["open", str(capture), "--listen", f"127.0.0.1:{bound_port}"]
            )
            assert result.exit_code == 1
            assert "daemon failed" in result.output

    def test_listen_outputs_connection_info(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()

        def _fake_listen(*a: Any, **kw: Any) -> tuple[bool, dict[str, Any]]:
            return True, {
                "host": "0.0.0.0",
                "port": 9999,
                "token": "secret123",
                "capture": "c.rdc",
            }

        monkeypatch.setattr("rdc.commands.session.listen_open_session", _fake_listen)
        runner = CliRunner()
        result = runner.invoke(main, ["open", str(capture), "--listen", ":0"])
        assert result.exit_code == 0
        assert "host: 0.0.0.0" in result.output
        assert "port: 9999" in result.output
        assert "token: secret123" in result.output


# ===========================================================================
# T3: --connect variants
# ===========================================================================


class TestConnectOption:
    def test_connect_success(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)

        monkeypatch.setattr(
            "rdc.commands.session.connect_session",
            lambda h, p, t: (True, f"connected: test.rdc at {h}:{p}"),
        )
        runner = CliRunner()
        result = runner.invoke(main, ["open", "--connect", "host:1234", "--token", "tok"])
        assert result.exit_code == 0
        assert "connected" in result.output
        assert "host:1234" in result.output

    def test_connect_requires_token(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["open", "--connect", "host:1234"])
        assert result.exit_code == 1
        assert "--token" in result.output

    def test_connect_mutually_exclusive_with_capture(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["open", "file.rdc", "--connect", "host:1234", "--token", "tok"]
        )
        assert result.exit_code == 1
        assert "mutually exclusive" in result.output

    def test_connect_mutually_exclusive_with_proxy(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["open", "--connect", "host:1234", "--token", "tok", "--proxy", "r:5000"]
        )
        assert result.exit_code == 1
        assert "mutually exclusive" in result.output

    def test_connect_daemon_unreachable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        monkeypatch.setattr(
            "rdc.commands.session.connect_session",
            lambda h, p, t: (False, f"error: cannot reach daemon at {h}:{p}: refused"),
        )
        runner = CliRunner()
        result = runner.invoke(main, ["open", "--connect", "host:1234", "--token", "tok"])
        assert result.exit_code == 1
        assert "cannot reach" in result.output

    def test_connect_invalid_format_no_port(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["open", "--connect", "hostonly", "--token", "tok"])
        assert result.exit_code == 1
        assert "HOST:PORT" in result.output

    def test_connect_invalid_port(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["open", "--connect", "host:abc", "--token", "tok"])
        assert result.exit_code == 1
        assert "invalid port" in result.output

    def test_connect_creates_pid0_session(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: {"result": {"capture": "remote.rdc", "current_eid": 0}},
        )
        runner = CliRunner()
        result = runner.invoke(main, ["open", "--connect", "host:1234", "--token", "tok"])
        assert result.exit_code == 0

        from rdc.session_state import load_session

        session = load_session()
        assert session is not None
        assert session.pid == 0
        assert session.host == "host"
        assert session.port == 1234

    def test_connect_existing_session_blocks(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """T3-7: --connect when active session exists returns error."""
        _setup_no_replay(monkeypatch, tmp_path)
        monkeypatch.setattr(
            "rdc.commands.session.connect_session",
            lambda h, p, t: (False, "error: active session exists, run `rdc close` first"),
        )
        runner = CliRunner()
        result = runner.invoke(main, ["open", "--connect", "host:1234", "--token", "tok"])
        assert result.exit_code == 1
        assert "active session exists" in result.output

    def test_connect_with_custom_session_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """T3-8: --connect with RDC_SESSION writes to custom-named session file."""
        _setup_no_replay(monkeypatch, tmp_path)
        monkeypatch.setenv("RDC_SESSION", "custom")
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: {"result": {"capture": "remote.rdc", "current_eid": 0}},
        )
        runner = CliRunner()
        result = runner.invoke(main, ["open", "--connect", "host:1234", "--token", "tok"])
        assert result.exit_code == 0
        expected = tmp_path / ".rdc" / "sessions" / "custom.json"
        assert expected.exists()


# ===========================================================================
# T4: optional capture argument
# ===========================================================================


class TestOptionalCapture:
    def test_no_capture_no_connect_errors(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["open"])
        assert result.exit_code == 1
        assert "CAPTURE" in result.output

    def test_capture_still_works(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()
        runner = CliRunner()
        result = runner.invoke(main, ["open", str(capture)])
        assert result.exit_code == 0
        assert "opened" in result.output


# ===========================================================================
# T5: pid==0 guards (service layer + helpers)
# ===========================================================================


class TestPid0Guards:
    def test_require_session_pid0_ping_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """pid==0 session with successful ping returns normally."""
        import rdc.commands._helpers as helpers_mod

        session = _make_session(pid=0)
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)
        monkeypatch.setattr(
            "rdc.daemon_client.send_request",
            lambda *a, **kw: {"result": {"ok": True}},
        )
        h, p, t = helpers_mod.require_session()
        assert (h, p, t) == (session.host, session.port, session.token)

    def test_require_session_pid0_ping_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """pid==0 session with failed ping cleans up and exits."""
        import rdc.commands._helpers as helpers_mod

        session = _make_session(pid=0)
        monkeypatch.setattr(helpers_mod, "load_session", lambda: session)

        def raise_conn(*a: Any, **kw: Any) -> None:
            raise ConnectionRefusedError

        monkeypatch.setattr("rdc.daemon_client.send_request", raise_conn)
        deleted: list[bool] = []
        monkeypatch.setattr(
            "rdc.session_state.delete_session",
            lambda: (deleted.append(True), True)[1],
        )
        with pytest.raises(SystemExit):
            helpers_mod.require_session()
        assert deleted

    def test_open_session_existing_pid0_live_blocks(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Existing pid==0 session that responds to ping blocks new open."""
        _setup_no_replay(monkeypatch, tmp_path)
        existing = _make_session(pid=0)
        monkeypatch.setattr(session_service, "load_session", lambda: existing)
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: {"result": {"ok": True}},
        )
        ok, msg = session_service.open_session("new.rdc")
        assert ok is False
        assert "active session exists" in msg

    def test_open_session_existing_pid0_dead_cleans(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Existing pid==0 session that fails ping gets cleaned before new open."""
        _setup_no_replay(monkeypatch, tmp_path)
        existing = _make_session(pid=0)

        load_called = [0]

        def tracked_load() -> SessionState | None:
            load_called[0] += 1
            if load_called[0] == 1:
                return existing
            return None

        monkeypatch.setattr(session_service, "load_session", tracked_load)

        def send_raises(*a: Any, **kw: Any) -> dict[str, Any]:
            raise ConnectionRefusedError

        monkeypatch.setattr(session_service, "send_request", send_raises)

        deleted: list[bool] = []
        monkeypatch.setattr(
            session_service,
            "delete_session",
            lambda: (deleted.append(True), True)[1],
        )

        mock_proc = MagicMock()
        mock_proc.pid = 999
        monkeypatch.setattr(session_service, "start_daemon", lambda *a, **kw: mock_proc)
        monkeypatch.setattr(session_service, "wait_for_ping", lambda *a, **kw: (True, ""))

        ok, msg = session_service.open_session("new.rdc")
        assert ok is True
        assert deleted

    def test_load_live_session_pid0_ping_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_load_live_session returns session when pid==0 and ping succeeds."""
        session = _make_session(pid=0)
        monkeypatch.setattr(session_service, "load_session", lambda: session)
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: {"result": {"ok": True}},
        )
        state, err = session_service._load_live_session()
        assert state is session
        assert err is None

    def test_load_live_session_pid0_ping_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_load_live_session cleans session when pid==0 and ping fails."""
        session = _make_session(pid=0)
        monkeypatch.setattr(session_service, "load_session", lambda: session)
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: (_ for _ in ()).throw(ConnectionRefusedError()),
        )
        deleted: list[bool] = []
        monkeypatch.setattr(
            session_service,
            "delete_session",
            lambda: (deleted.append(True), True)[1],
        )
        state, err = session_service._load_live_session()
        assert state is None
        assert "stale" in (err or "")
        assert deleted


# ===========================================================================
# T6: close --shutdown
# ===========================================================================


class TestCloseShutdown:
    def test_close_pid0_no_shutdown_just_deletes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        session = _make_session(pid=0)
        monkeypatch.setattr(session_service, "load_session", lambda: session)

        send_called: list[bool] = []
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: (send_called.append(True), {"result": {}})[1],
        )
        monkeypatch.setattr(session_service, "delete_session", lambda: True)

        ok, msg = session_service.close_session(force_shutdown=False)
        assert ok is True
        assert not send_called

    def test_close_pid0_with_shutdown_sends_rpc(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        session = _make_session(pid=0)
        monkeypatch.setattr(session_service, "load_session", lambda: session)

        send_called: list[bool] = []
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: (send_called.append(True), {"result": {}})[1],
        )
        monkeypatch.setattr(session_service, "delete_session", lambda: True)

        ok, msg = session_service.close_session(force_shutdown=True)
        assert ok is True
        assert send_called

    def test_close_pid0_shutdown_rpc_fails_still_deletes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        session = _make_session(pid=0)
        monkeypatch.setattr(session_service, "load_session", lambda: session)

        def raise_oserror(*a: Any, **kw: Any) -> None:
            raise OSError("connection refused")

        monkeypatch.setattr(session_service, "send_request", raise_oserror)
        deleted: list[bool] = []
        monkeypatch.setattr(
            session_service,
            "delete_session",
            lambda: (deleted.append(True), True)[1],
        )

        ok, msg = session_service.close_session(force_shutdown=True)
        assert ok is True
        assert deleted

    def test_close_cmd_shutdown_flag(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        called_kw: dict[str, Any] = {}

        def fake_close(**kw: Any) -> tuple[bool, str]:
            called_kw.update(kw)
            return True, "session closed"

        monkeypatch.setattr("rdc.commands.session.close_session", fake_close)
        runner = CliRunner()
        result = runner.invoke(main, ["close", "--shutdown"])
        assert result.exit_code == 0
        assert called_kw.get("force_shutdown") is True

    def test_close_cmd_no_shutdown_flag(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)

        called_kw: dict[str, Any] = {}

        def fake_close(**kw: Any) -> tuple[bool, str]:
            called_kw.update(kw)
            return True, "session closed"

        monkeypatch.setattr("rdc.commands.session.close_session", fake_close)
        runner = CliRunner()
        result = runner.invoke(main, ["close"])
        assert result.exit_code == 0
        assert called_kw.get("force_shutdown") is False


# ===========================================================================
# T7: regression — existing flows still work
# ===========================================================================


class TestRegression:
    def test_standard_open_close(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()
        runner = CliRunner()

        result = runner.invoke(main, ["open", str(capture)])
        assert result.exit_code == 0
        assert "opened" in result.output

        result = runner.invoke(main, ["close"])
        assert result.exit_code == 0
        assert "closed" in result.output

    def test_status_shows_pid0_daemon(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Status for pid==0 session displays daemon info with pid=0."""
        _setup_no_replay(monkeypatch, tmp_path)

        def _smart_send(*a: Any, **kw: Any) -> dict[str, Any]:
            payload = a[2] if len(a) > 2 else {}
            method = payload.get("method", "")
            if method == "ping":
                return {"result": {"ok": True}}
            return {"result": {"capture": "remote.rdc", "current_eid": 0}}

        monkeypatch.setattr(session_service, "send_request", _smart_send)
        runner = CliRunner()

        result = runner.invoke(
            main,
            ["open", "--connect", "10.0.0.1:5555", "--token", "tok"],
        )
        assert result.exit_code == 0

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "pid=0" in result.output

    def test_open_no_replay_warning_preserved(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """B23: no-replay mode warning still works after refactor."""
        _setup_no_replay(monkeypatch, tmp_path)
        capture = tmp_path / "c.rdc"
        capture.touch()
        runner = CliRunner()

        result = runner.invoke(main, ["open", str(capture)])
        assert result.exit_code == 0
        assert "no-replay mode" in result.output
        assert "warning" in result.stderr


# ===========================================================================
# Service layer: connect_session
# ===========================================================================


class TestConnectSessionService:
    def test_connect_session_success(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: {"result": {"capture": "remote.rdc", "current_eid": 0}},
        )
        ok, msg = session_service.connect_session("host", 1234, "tok")
        assert ok is True
        assert "connected" in msg

    def test_connect_session_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_conn(*a: Any, **kw: Any) -> None:
            raise ConnectionRefusedError("refused")

        monkeypatch.setattr(session_service, "send_request", raise_conn)
        ok, msg = session_service.connect_session("host", 1234, "tok")
        assert ok is False
        assert "cannot reach" in msg

    def test_connect_session_error_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: {"error": {"message": "bad token"}},
        )
        ok, msg = session_service.connect_session("host", 1234, "tok")
        assert ok is False
        assert "bad token" in msg


# ===========================================================================
# Service layer: _parse_listen_addr
# ===========================================================================


class TestParseListenAddr:
    def test_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(session_service, "pick_port", lambda: 11111)
        h, p = session_service._parse_listen_addr("")
        assert h == "0.0.0.0"
        assert p == 11111

    def test_addr_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(session_service, "pick_port", lambda: 22222)
        h, p = session_service._parse_listen_addr("192.168.1.1")
        assert h == "192.168.1.1"
        assert p == 22222

    def test_addr_and_port(self) -> None:
        h, p = session_service._parse_listen_addr("0.0.0.0:9999")
        assert h == "0.0.0.0"
        assert p == 9999

    def test_colon_port_only(self) -> None:
        h, p = session_service._parse_listen_addr(":7777")
        assert h == "0.0.0.0"
        assert p == 7777

    def test_colon_zero_auto_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(session_service, "pick_port", lambda: 33333)
        h, p = session_service._parse_listen_addr(":0")
        assert h == "0.0.0.0"
        assert p == 33333

    def test_non_numeric_port_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid port"):
            session_service._parse_listen_addr("0.0.0.0:abc")


# ===========================================================================
# Service layer: connect_session — existing session guard
# ===========================================================================


class TestConnectSessionExistingGuard:
    def test_connect_blocks_when_local_daemon_alive(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        existing = _make_session(pid=12345)
        monkeypatch.setattr(session_service, "load_session", lambda: existing)
        monkeypatch.setattr(session_service, "is_pid_alive", lambda pid: True)

        ok, msg = session_service.connect_session("host", 1234, "tok")
        assert ok is False
        assert "active session exists" in msg

    def test_connect_blocks_when_pid0_daemon_alive(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        existing = _make_session(pid=0)
        monkeypatch.setattr(session_service, "load_session", lambda: existing)
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: {"result": {"ok": True}},
        )

        ok, msg = session_service.connect_session("host", 1234, "tok")
        assert ok is False
        assert "active session exists" in msg

    def test_connect_cleans_stale_but_fails_if_unreachable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        existing = _make_session(pid=0)
        load_count = [0]

        def tracked_load() -> SessionState | None:
            load_count[0] += 1
            return existing if load_count[0] == 1 else None

        monkeypatch.setattr(session_service, "load_session", tracked_load)

        def send_raises(*a: Any, **kw: Any) -> dict[str, Any]:
            raise ConnectionRefusedError

        monkeypatch.setattr(session_service, "send_request", send_raises)
        monkeypatch.setattr(session_service, "delete_session", lambda: True)

        ok, msg = session_service.connect_session("host", 1234, "tok")
        assert ok is False
        assert "cannot reach" in msg


# ===========================================================================
# Service layer: listen_open_session
# ===========================================================================


class TestListenOpenSessionService:
    def test_listen_success(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        monkeypatch.setattr(session_service, "load_session", lambda: None)
        mock_proc = MagicMock()
        mock_proc.pid = 999
        monkeypatch.setattr(session_service, "start_daemon", lambda *a, **kw: mock_proc)
        monkeypatch.setattr(session_service, "wait_for_ping", lambda *a, **kw: (True, ""))

        ok, result = session_service.listen_open_session("c.rdc", "0.0.0.0:8888")
        assert ok is True
        assert isinstance(result, dict)
        assert result["host"] == "0.0.0.0"
        assert result["port"] == 8888

    def test_listen_daemon_fail(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        monkeypatch.setattr(session_service, "load_session", lambda: None)
        mock_proc = MagicMock()
        mock_proc.pid = 999
        mock_proc.kill.return_value = None
        mock_proc.communicate.return_value = ("", "bind failed")
        monkeypatch.setattr(session_service, "start_daemon", lambda *a, **kw: mock_proc)
        monkeypatch.setattr(session_service, "wait_for_ping", lambda *a, **kw: (False, "timeout"))

        ok, result = session_service.listen_open_session("c.rdc", "0.0.0.0:8888")
        assert ok is False
        assert "bind failed" in str(result)

    def test_listen_existing_pid0_live_blocks(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _setup_no_replay(monkeypatch, tmp_path)
        existing = _make_session(pid=0)
        monkeypatch.setattr(session_service, "load_session", lambda: existing)
        monkeypatch.setattr(
            session_service,
            "send_request",
            lambda *a, **kw: {"result": {"ok": True}},
        )
        ok, result = session_service.listen_open_session("c.rdc", "")
        assert ok is False
        assert "active session" in str(result)
