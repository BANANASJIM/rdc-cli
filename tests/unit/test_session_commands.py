from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from rdc.cli import main
from rdc.commands.session import _resolve_android_url
from rdc.remote_state import RemoteServerState, save_remote_state

_CURRENT_EID: dict[str, int] = {}


def _mock_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent real daemon spawn and RPC calls."""
    mock_proc = MagicMock()
    mock_proc.pid = 999
    monkeypatch.setattr(
        "rdc.services.session_service.start_daemon",
        lambda *a, **kw: mock_proc,
    )
    monkeypatch.setattr(
        "rdc.services.session_service.wait_for_ping",
        lambda *a, **kw: (True, ""),
    )
    monkeypatch.setattr(
        "rdc.services.session_service.is_pid_alive",
        lambda pid: True,
    )
    _CURRENT_EID.clear()
    _CURRENT_EID["eid"] = 0

    def _fake_send(host: str, port: int, payload: dict, **kw: object) -> dict:
        method = payload.get("method", "")
        if method == "ping":
            return {"result": {"ok": True}}
        if method == "status":
            return {"result": {"current_eid": _CURRENT_EID["eid"]}}
        if method == "goto":
            eid = payload.get("params", {}).get("eid", 0)
            _CURRENT_EID["eid"] = eid
            return {"result": {"current_eid": eid}}
        if method == "shutdown":
            return {"result": {"ok": True}}
        return {"result": {}}

    monkeypatch.setattr(
        "rdc.services.session_service.send_request",
        _fake_send,
    )


def _session_file(home: Path) -> Path:
    return home / ".rdc" / "sessions" / "default.json"


def test_open_status_goto_close_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    _mock_daemon(monkeypatch)
    capture_file = tmp_path / "capture.rdc"
    capture_file.touch()
    runner = CliRunner()

    result_open = runner.invoke(main, ["open", str(capture_file)])
    assert result_open.exit_code == 0
    assert _session_file(tmp_path).exists()

    result_status_1 = runner.invoke(main, ["status"])
    assert result_status_1.exit_code == 0
    assert "capture.rdc" in result_status_1.output
    assert "current_eid: 0" in result_status_1.output

    result_goto = runner.invoke(main, ["goto", "142"])
    assert result_goto.exit_code == 0

    result_status_2 = runner.invoke(main, ["status"])
    assert result_status_2.exit_code == 0
    assert "current_eid: 142" in result_status_2.output

    result_close = runner.invoke(main, ["close"])
    assert result_close.exit_code == 0
    assert not _session_file(tmp_path).exists()


def test_goto_without_session_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    runner = CliRunner()

    result = runner.invoke(main, ["goto", "1"])
    assert result.exit_code == 1


def test_close_without_session_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    runner = CliRunner()

    result = runner.invoke(main, ["close"])
    assert result.exit_code == 1


def test_goto_rejects_negative_eid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    _mock_daemon(monkeypatch)
    runner = CliRunner()

    runner.invoke(main, ["open", "capture.rdc"])
    result = runner.invoke(main, ["goto", "-1"])
    assert result.exit_code != 0


def test_status_shows_session_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """rdc status first line is 'session: <name>' matching active RDC_SESSION."""
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.setenv("RDC_SESSION", "mytest")
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    _mock_daemon(monkeypatch)
    capture_file = tmp_path / "capture.rdc"
    capture_file.touch()
    runner = CliRunner()

    runner.invoke(main, ["open", str(capture_file)])
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0] == "session: mytest"


def test_status_shows_default_session_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without --session, status first line is 'session: default'."""
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    _mock_daemon(monkeypatch)
    capture_file = tmp_path / "capture.rdc"
    capture_file.touch()
    runner = CliRunner()

    runner.invoke(main, ["open", str(capture_file)])
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0] == "session: default"


def test_require_session_cleans_stale_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    """B18: require_session() detects dead daemon PID and cleans up."""
    import rdc.commands._helpers as helpers_mod
    from rdc.session_state import SessionState

    session = SessionState(
        capture="test.rdc",
        current_eid=0,
        opened_at="2024-01-01",
        host="127.0.0.1",
        port=9999,
        token="tok",
        pid=99999,
    )
    monkeypatch.setattr(helpers_mod, "load_session", lambda: session)
    monkeypatch.setattr("rdc.session_state.is_pid_alive", lambda pid: False)
    deleted: list[bool] = []
    monkeypatch.setattr("rdc.session_state.delete_session", lambda: (deleted.append(True), True)[1])

    with pytest.raises(SystemExit):
        helpers_mod.require_session()
    assert deleted


def test_open_no_replay_mode_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """B23: open command warns when renderdoc is unavailable."""
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    _mock_daemon(monkeypatch)
    capture_file = tmp_path / "capture.rdc"
    capture_file.touch()
    runner = CliRunner()

    result = runner.invoke(main, ["open", str(capture_file)])
    assert result.exit_code == 0
    assert "no-replay mode" in result.output
    assert "warning" in result.stderr


# ---------------------------------------------------------------------------
# T4: Unit tests for _resolve_android_url
# ---------------------------------------------------------------------------


def _setup_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point data_dir to tmp_path/.rdc and return the path."""
    data = tmp_path / ".rdc"
    monkeypatch.setattr("rdc._platform.data_dir", lambda: data)
    return data


def test_resolve_android_url_with_serial(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup_data_dir(monkeypatch, tmp_path)
    save_remote_state(RemoteServerState(host="adb://DEV1", port=0, connected_at=1000.0))

    result = _resolve_android_url(serial="DEV1")
    assert result == "adb://DEV1"


def test_resolve_android_url_no_serial_uses_latest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _setup_data_dir(monkeypatch, tmp_path)
    save_remote_state(RemoteServerState(host="adb://OLD", port=0, connected_at=500.0))
    save_remote_state(RemoteServerState(host="adb://NEW", port=0, connected_at=2000.0))

    result = _resolve_android_url(serial=None)
    assert result == "adb://NEW"


def test_resolve_android_url_serial_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _setup_data_dir(monkeypatch, tmp_path)
    save_remote_state(RemoteServerState(host="adb://AAA", port=0, connected_at=1000.0))

    with pytest.raises(click.UsageError, match="ZZZ"):
        _resolve_android_url(serial="ZZZ")


def test_resolve_android_url_no_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = _setup_data_dir(monkeypatch, tmp_path)
    (data / "remote").mkdir(parents=True, exist_ok=True)

    with pytest.raises(click.UsageError):
        _resolve_android_url(serial=None)


def test_resolve_android_url_ignores_non_adb(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _setup_data_dir(monkeypatch, tmp_path)
    save_remote_state(RemoteServerState(host="192.168.1.10", port=8888, connected_at=9999.0))
    save_remote_state(RemoteServerState(host="adb://ABC123", port=0, connected_at=1000.0))

    result = _resolve_android_url(serial=None)
    assert result == "adb://ABC123"


# ---------------------------------------------------------------------------
# T5: Unit tests for --android / --serial CLI options
# ---------------------------------------------------------------------------


def _mock_daemon_capture(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Like _mock_daemon but records start_daemon kwargs."""
    recorded: dict[str, Any] = {"calls": []}
    mock_proc = MagicMock()
    mock_proc.pid = 999

    def _fake_start(*args: Any, **kwargs: Any) -> MagicMock:
        recorded["calls"].append({"args": args, "kwargs": kwargs})
        return mock_proc

    monkeypatch.setattr("rdc.services.session_service.start_daemon", _fake_start)
    monkeypatch.setattr(
        "rdc.services.session_service.wait_for_ping",
        lambda *a, **kw: (True, ""),
    )
    monkeypatch.setattr(
        "rdc.services.session_service.is_pid_alive",
        lambda pid: True,
    )

    def _fake_send(host: str, port: int, payload: dict[str, Any], **kw: object) -> dict[str, Any]:
        method = payload.get("method", "")
        if method == "ping":
            return {"result": {"ok": True}}
        if method == "status":
            return {"result": {"current_eid": 0}}
        if method == "shutdown":
            return {"result": {"ok": True}}
        return {"result": {}}

    monkeypatch.setattr("rdc.services.session_service.send_request", _fake_send)
    return recorded


def test_open_android_resolves_adb_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup_data_dir(monkeypatch, tmp_path)
    monkeypatch.delenv("RDC_SESSION", raising=False)
    save_remote_state(RemoteServerState(host="adb://ABC123", port=0, connected_at=1000.0))
    recorded = _mock_daemon_capture(monkeypatch)
    capture_file = tmp_path / "capture.rdc"
    capture_file.touch()

    result = CliRunner().invoke(main, ["open", str(capture_file), "--android"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    assert len(recorded["calls"]) == 1
    assert recorded["calls"][0]["kwargs"]["remote_url"] == "adb://ABC123"


def test_open_android_with_serial(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup_data_dir(monkeypatch, tmp_path)
    monkeypatch.delenv("RDC_SESSION", raising=False)
    save_remote_state(RemoteServerState(host="adb://AAA", port=0, connected_at=2000.0))
    save_remote_state(RemoteServerState(host="adb://BBB", port=0, connected_at=1000.0))
    recorded = _mock_daemon_capture(monkeypatch)
    capture_file = tmp_path / "capture.rdc"
    capture_file.touch()

    result = CliRunner().invoke(main, ["open", str(capture_file), "--android", "--serial", "BBB"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    assert recorded["calls"][0]["kwargs"]["remote_url"] == "adb://BBB"


def test_open_android_no_state_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = _setup_data_dir(monkeypatch, tmp_path)
    monkeypatch.delenv("RDC_SESSION", raising=False)
    (data / "remote").mkdir(parents=True, exist_ok=True)
    capture_file = tmp_path / "capture.rdc"
    capture_file.touch()

    result = CliRunner().invoke(main, ["open", str(capture_file), "--android"])
    assert result.exit_code != 0


def test_open_android_mutual_exclusion_proxy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _setup_data_dir(monkeypatch, tmp_path)
    monkeypatch.delenv("RDC_SESSION", raising=False)
    capture_file = tmp_path / "capture.rdc"
    capture_file.touch()

    result = CliRunner().invoke(
        main, ["open", str(capture_file), "--android", "--proxy", "localhost:1234"]
    )
    assert result.exit_code != 0


def test_open_android_mutual_exclusion_connect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _setup_data_dir(monkeypatch, tmp_path)
    monkeypatch.delenv("RDC_SESSION", raising=False)

    result = CliRunner().invoke(
        main,
        ["open", "--android", "--connect", "host:1234", "--token", "tok"],
    )
    assert result.exit_code != 0


def test_open_android_mutual_exclusion_listen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _setup_data_dir(monkeypatch, tmp_path)
    monkeypatch.delenv("RDC_SESSION", raising=False)
    save_remote_state(RemoteServerState(host="adb://ABC123", port=0, connected_at=1000.0))
    capture_file = tmp_path / "capture.rdc"
    capture_file.touch()

    result = CliRunner().invoke(main, ["open", str(capture_file), "--android", "--listen", ":0"])
    assert result.exit_code != 0


def test_open_serial_without_android_warns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup_data_dir(monkeypatch, tmp_path)
    monkeypatch.delenv("RDC_SESSION", raising=False)
    monkeypatch.setattr("rdc.services.session_service._renderdoc_available", lambda: False)
    _mock_daemon(monkeypatch)
    capture_file = tmp_path / "capture.rdc"
    capture_file.touch()

    result = CliRunner().invoke(main, ["open", str(capture_file), "--serial", "ABC123"])
    assert result.exit_code == 0
    assert "warning" in result.stderr.lower() or "ignored" in result.stderr.lower()
