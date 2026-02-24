"""Tests for remote_core module."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from rdc.remote_core import (
    build_conn_url,
    connect_remote_server,
    enumerate_remote_targets,
    parse_url,
    remote_capture,
    warn_if_public,
)


class TestParseUrl:
    def test_host_only(self) -> None:
        assert parse_url("192.168.1.10") == ("192.168.1.10", 39920)

    def test_host_port(self) -> None:
        assert parse_url("192.168.1.10:12345") == ("192.168.1.10", 12345)

    def test_localhost(self) -> None:
        assert parse_url("localhost") == ("localhost", 39920)

    def test_ipv6_brackets(self) -> None:
        assert parse_url("[::1]:39920") == ("::1", 39920)

    def test_ipv6_brackets_no_port(self) -> None:
        assert parse_url("[::1]") == ("::1", 39920)

    def test_parse_url_invalid_port(self) -> None:
        with pytest.raises(ValueError, match="invalid port"):
            parse_url("host:abc")

    def test_parse_url_port_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="invalid port"):
            parse_url("host:99999")
        with pytest.raises(ValueError, match="invalid port"):
            parse_url("host:-1")
        with pytest.raises(ValueError, match="invalid port"):
            parse_url("host:0")

    def test_ipv6_unclosed_bracket_raises(self) -> None:
        with pytest.raises(ValueError, match="malformed IPv6"):
            parse_url("[::1")

    def test_ipv6_empty_brackets_raises(self) -> None:
        with pytest.raises(ValueError, match="empty IPv6"):
            parse_url("[]")

    def test_ipv6_trailing_garbage_raises(self) -> None:
        with pytest.raises(ValueError, match="unexpected content"):
            parse_url("[::1]abc")

    def test_bare_ipv6_raises(self) -> None:
        with pytest.raises(ValueError, match="must use brackets"):
            parse_url("::1")

    def test_bare_ipv6_long_raises(self) -> None:
        with pytest.raises(ValueError, match="must use brackets"):
            parse_url("fe80::1")


class TestBuildConnUrl:
    def test_ipv4(self) -> None:
        assert build_conn_url("192.168.1.1", 39920) == "192.168.1.1:39920"

    def test_hostname(self) -> None:
        assert build_conn_url("localhost", 39920) == "localhost:39920"

    def test_ipv6_re_brackets(self) -> None:
        assert build_conn_url("::1", 39920) == "[::1]:39920"

    def test_ipv6_long(self) -> None:
        assert build_conn_url("2001:db8::1", 8080) == "[2001:db8::1]:8080"


class TestWarnIfPublic:
    @pytest.mark.parametrize(
        "host",
        [
            "192.168.1.10",
            "10.0.0.1",
            "172.16.5.3",
            "127.0.0.1",
            "localhost",
            "::1",
            "fd12::1",
            "fe80::1",
        ],
    )
    def test_private_no_warning(self, host: str) -> None:
        assert warn_if_public(host) is None

    @pytest.mark.parametrize("host", ["8.8.8.8", "203.0.113.1", "example.com"])
    def test_public_warns(self, host: str) -> None:
        result = warn_if_public(host)
        assert result is not None
        assert "not a private IP" in result


class TestConnectRemoteServer:
    def test_success(self) -> None:
        rd = MagicMock()
        mock_remote = MagicMock()
        rd.CreateRemoteServerConnection.return_value = (0, mock_remote)
        result = connect_remote_server(rd, "192.168.1.10:39920")
        assert result is mock_remote
        rd.CreateRemoteServerConnection.assert_called_once_with("192.168.1.10:39920")

    def test_failure_code(self) -> None:
        rd = MagicMock()
        rd.CreateRemoteServerConnection.return_value = (1, None)
        with pytest.raises(RuntimeError, match="connection failed"):
            connect_remote_server(rd, "192.168.1.10:39920")

    def test_int_result_code(self) -> None:
        rd = MagicMock()
        rd.CreateRemoteServerConnection.return_value = (0, MagicMock())
        result = connect_remote_server(rd, "host")
        assert result is not None

    def test_result_details_success(self) -> None:
        """B32: ResultDetails where __ne__(0) returns False => success."""
        rd = MagicMock()
        mock_remote = MagicMock()
        result_obj = MagicMock()
        result_obj.__ne__ = lambda self, other: False
        rd.CreateRemoteServerConnection.return_value = (result_obj, mock_remote)
        assert connect_remote_server(rd, "host") is mock_remote

    def test_result_details_failure_with_message(self) -> None:
        """B32: ResultDetails with Message() => error includes message text."""
        rd = MagicMock()
        result_obj = MagicMock()
        result_obj.__ne__ = lambda self, other: True
        result_obj.Message.return_value = "Timeout"
        rd.CreateRemoteServerConnection.return_value = (result_obj, None)
        with pytest.raises(RuntimeError, match="Timeout"):
            connect_remote_server(rd, "host")

    def test_result_details_failure_no_message(self) -> None:
        """B32: ResultDetails without Message attr => graceful fallback."""

        class BareResult:
            def __ne__(self, other: object) -> bool:
                return True

        rd = MagicMock()
        rd.CreateRemoteServerConnection.return_value = (BareResult(), None)
        with pytest.raises(RuntimeError, match="connection failed"):
            connect_remote_server(rd, "host")


class TestEnumerateRemoteTargets:
    def test_returns_idents(self) -> None:
        rd = MagicMock()
        rd.EnumerateRemoteTargets.side_effect = [1, 2, 0]
        targets = enumerate_remote_targets(rd, "host:39920")
        assert targets == [1, 2]

    def test_empty(self) -> None:
        rd = MagicMock()
        rd.EnumerateRemoteTargets.return_value = 0
        assert enumerate_remote_targets(rd, "host:39920") == []

    def test_max_1000_limit(self) -> None:
        rd = MagicMock()
        # Always return non-zero to test upper bound
        call_count = 0

        def always_next(url: str, ident: int) -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        rd.EnumerateRemoteTargets.side_effect = always_next
        targets = enumerate_remote_targets(rd, "host:39920")
        assert len(targets) == 1000


class TestRemoteCapture:
    def test_success_remote_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.capture_core import CaptureResult

        rd = MagicMock()
        remote = MagicMock()
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=0, ident=42)

        cap_result = CaptureResult(success=True, path="/remote/cap.rdc", local=False)
        monkeypatch.setattr("rdc.remote_core.run_target_control_loop", lambda tc, **kw: cap_result)
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())

        tc = MagicMock()
        rd.CreateTargetControl.return_value = tc

        result = remote_capture(rd, remote, "host:39920", "/app", output="/tmp/out.rdc")
        assert result.success is True
        assert result.path == "/tmp/out.rdc"
        remote.CopyCaptureFromRemote.assert_called_once_with(
            "/remote/cap.rdc", "/tmp/out.rdc", None
        )
        tc.Shutdown.assert_called_once()

    def test_success_local_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """B33: local file is copied to output path when paths differ."""
        from rdc.capture_core import CaptureResult

        rd = MagicMock()
        remote = MagicMock()
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=0, ident=42)

        cap_result = CaptureResult(success=True, path="/local/cap.rdc", local=True)
        monkeypatch.setattr("rdc.remote_core.run_target_control_loop", lambda tc, **kw: cap_result)
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())
        monkeypatch.setattr("rdc.remote_core.shutil.copy2", lambda src, dst: None)

        tc = MagicMock()
        rd.CreateTargetControl.return_value = tc

        result = remote_capture(rd, remote, "host:39920", "/app", output="/tmp/out.rdc")
        assert result.success is True
        assert result.path == "/tmp/out.rdc"
        remote.CopyCaptureFromRemote.assert_not_called()

    def test_inject_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd = MagicMock()
        remote = MagicMock()
        result_obj = MagicMock()
        result_obj.__ne__ = lambda self, other: True
        result_obj.Message.return_value = "Access denied"
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=result_obj, ident=0)
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())

        result = remote_capture(rd, remote, "host", "/app", output="/tmp/out.rdc")
        assert not result.success
        assert "inject failed" in result.error

    def test_tc_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rd = MagicMock()
        remote = MagicMock()
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=0, ident=42)
        rd.CreateTargetControl.return_value = None
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())

        result = remote_capture(rd, remote, "host", "/app", output="/tmp/out.rdc")
        assert not result.success
        assert "failed to connect" in result.error
        assert result.ident == 42

    def test_passes_capture_options(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.capture_core import CaptureResult

        rd = MagicMock()
        remote = MagicMock()
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=0, ident=42)

        cap_result = CaptureResult(success=True, path="/remote/cap.rdc", local=False)
        monkeypatch.setattr("rdc.remote_core.run_target_control_loop", lambda tc, **kw: cap_result)

        captured_opts: list[Any] = []

        def fake_build(opts: dict[str, Any]) -> MagicMock:
            captured_opts.append(opts)
            return MagicMock()

        monkeypatch.setattr("rdc.remote_core.build_capture_options", fake_build)
        rd.CreateTargetControl.return_value = MagicMock()

        remote_capture(
            rd,
            remote,
            "host",
            "/app",
            output="/tmp/out.rdc",
            opts={"api_validation": True},
        )
        assert captured_opts[0] == {"api_validation": True}

    def test_copy_failure_sets_success_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.capture_core import CaptureResult

        rd = MagicMock()
        remote = MagicMock()
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=0, ident=42)
        remote.CopyCaptureFromRemote.side_effect = OSError("disk full")

        cap_result = CaptureResult(success=True, path="/remote/cap.rdc", local=False)
        monkeypatch.setattr("rdc.remote_core.run_target_control_loop", lambda tc, **kw: cap_result)
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())
        rd.CreateTargetControl.return_value = MagicMock()

        result = remote_capture(rd, remote, "host:39920", "/app", output="/tmp/out.rdc")
        assert result.success is False
        assert "transfer failed" in result.error
        assert result.path == "/remote/cap.rdc"
        assert result.local is False

    def test_tc_shutdown_called_on_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from rdc.capture_core import CaptureResult

        rd = MagicMock()
        remote = MagicMock()
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=0, ident=42)
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())

        cap_result = CaptureResult(success=False, error="timeout waiting for capture")
        monkeypatch.setattr("rdc.remote_core.run_target_control_loop", lambda tc, **kw: cap_result)

        tc = MagicMock()
        rd.CreateTargetControl.return_value = tc

        result = remote_capture(rd, remote, "host", "/app", output="/tmp/out.rdc")
        assert not result.success
        tc.Shutdown.assert_called_once()

    # --- B33 tests: local file copy to output ---

    def test_local_file_copied_to_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """B33: local=True with different path triggers shutil.copy2."""
        from rdc.capture_core import CaptureResult

        rd = MagicMock()
        remote = MagicMock()
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=0, ident=42)

        cap_result = CaptureResult(success=True, path="/tmp/src.rdc", local=True)
        monkeypatch.setattr("rdc.remote_core.run_target_control_loop", lambda tc, **kw: cap_result)
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())

        copy_calls: list[tuple[str, str]] = []
        monkeypatch.setattr("rdc.remote_core.shutil.copy2", lambda s, d: copy_calls.append((s, d)))
        rd.CreateTargetControl.return_value = MagicMock()

        result = remote_capture(rd, remote, "host", "/app", output="/tmp/dst.rdc")
        assert result.success is True
        assert result.path == "/tmp/dst.rdc"
        assert copy_calls == [("/tmp/src.rdc", "/tmp/dst.rdc")]

    def test_local_file_same_path_no_copy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """B33: local=True with same path skips copy."""
        from rdc.capture_core import CaptureResult

        rd = MagicMock()
        remote = MagicMock()
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=0, ident=42)

        cap_result = CaptureResult(success=True, path="/tmp/out.rdc", local=True)
        monkeypatch.setattr("rdc.remote_core.run_target_control_loop", lambda tc, **kw: cap_result)
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())

        copy_calls: list[tuple[str, str]] = []
        monkeypatch.setattr("rdc.remote_core.shutil.copy2", lambda s, d: copy_calls.append((s, d)))
        rd.CreateTargetControl.return_value = MagicMock()

        result = remote_capture(rd, remote, "host", "/app", output="/tmp/out.rdc")
        assert result.success is True
        assert result.path == "/tmp/out.rdc"
        assert copy_calls == []

    def test_local_copy_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """B33: shutil.copy2 raises OSError => success=False with error message."""
        from rdc.capture_core import CaptureResult

        rd = MagicMock()
        remote = MagicMock()
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=0, ident=42)

        cap_result = CaptureResult(success=True, path="/tmp/src.rdc", local=True)
        monkeypatch.setattr("rdc.remote_core.run_target_control_loop", lambda tc, **kw: cap_result)
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())

        def fail_copy(src: str, dst: str) -> None:
            raise OSError("disk full")

        monkeypatch.setattr("rdc.remote_core.shutil.copy2", fail_copy)
        rd.CreateTargetControl.return_value = MagicMock()

        result = remote_capture(rd, remote, "host", "/app", output="/tmp/dst.rdc")
        assert result.success is False
        assert "local copy failed" in result.error
        assert "disk full" in result.error

    # --- B35 tests: inject failure error message ---

    def test_inject_failure_result_details_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """B35: exec_result.result with Message() => human-readable error."""
        rd = MagicMock()
        remote = MagicMock()
        result_obj = MagicMock()
        result_obj.__ne__ = lambda self, other: True
        result_obj.Message.return_value = "Permission denied"
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=result_obj, ident=0)
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())

        result = remote_capture(rd, remote, "host", "/app", output="/tmp/out.rdc")
        assert not result.success
        assert "Permission denied" in result.error
        assert "repr" not in result.error.lower()

    def test_inject_failure_int_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """B35: exec_result.result is plain int => fallback 'code N' message."""
        rd = MagicMock()
        remote = MagicMock()
        remote.ExecuteAndInject.return_value = SimpleNamespace(result=2, ident=0)
        monkeypatch.setattr("rdc.remote_core.build_capture_options", lambda opts: MagicMock())

        result = remote_capture(rd, remote, "host", "/app", output="/tmp/out.rdc")
        assert not result.success
        assert "code 2" in result.error
