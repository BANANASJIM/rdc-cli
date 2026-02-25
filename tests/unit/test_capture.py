"""Tests for the rewritten capture command (Python API + renderdoccmd fallback)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import click
from click.testing import CliRunner

from rdc.commands.capture import capture_cmd


class DummyResult:
    def __init__(self, code: int) -> None:
        self.returncode = code


def _make_capture_result(
    *,
    success: bool = True,
    path: str = "/tmp/test.rdc",
    frame: int = 0,
    byte_size: int = 4096,
    api: str = "Vulkan",
    local: bool = True,
    ident: int = 0,
    pid: int = 0,
    error: str = "",
) -> Any:
    from rdc.capture_core import CaptureResult

    return CaptureResult(
        success=success,
        path=path,
        frame=frame,
        byte_size=byte_size,
        api=api,
        local=local,
        ident=ident,
        pid=pid,
        error=error,
    )


def test_python_api_success(monkeypatch: Any) -> None:
    """Python API path: successful capture prints path and exits 0."""
    monkeypatch.setattr("rdc.commands.capture.find_renderdoc", lambda: MagicMock())
    monkeypatch.setattr(
        "rdc.commands.capture.execute_and_capture",
        lambda *a, **kw: _make_capture_result(),
    )
    monkeypatch.setattr(
        "rdc.commands.capture.build_capture_options",
        lambda opts: MagicMock(),
    )

    result = CliRunner().invoke(capture_cmd, ["-o", "/tmp/test.rdc", "--", "/usr/bin/app"])
    assert result.exit_code == 0
    assert "/tmp/test.rdc" in result.output


def test_fallback_renderdoccmd(monkeypatch: Any) -> None:
    """When renderdoc module is unavailable, fall back to renderdoccmd."""
    monkeypatch.setattr("rdc.commands.capture.find_renderdoc", lambda: None)
    monkeypatch.setattr("rdc.commands.capture._find_renderdoccmd", lambda: "/usr/bin/renderdoccmd")
    captured_argv: list[list[str]] = []

    def fake_run(argv: list[str], check: bool = False) -> DummyResult:
        captured_argv.append(argv)
        return DummyResult(0)

    monkeypatch.setattr("subprocess.run", fake_run)

    result = CliRunner().invoke(capture_cmd, ["-o", "/tmp/out.rdc", "--", "/usr/bin/app"])
    assert result.exit_code == 0
    assert "warning" in result.output
    assert "falling back" in result.output
    assert captured_argv[0][0] == "/usr/bin/renderdoccmd"
    assert "/usr/bin/app" in captured_argv[0]


def test_list_apis(monkeypatch: Any) -> None:
    """--list-apis delegates to renderdoccmd."""
    captured_argv: list[list[str]] = []

    def fake_run(argv: list[str], check: bool = False) -> DummyResult:
        captured_argv.append(argv)
        return DummyResult(0)

    monkeypatch.setattr("rdc.commands.capture._find_renderdoccmd", lambda: "/usr/bin/renderdoccmd")
    monkeypatch.setattr("subprocess.run", fake_run)

    result = CliRunner().invoke(capture_cmd, ["--list-apis"])
    assert result.exit_code == 0
    assert captured_argv[0] == ["/usr/bin/renderdoccmd", "capture", "--list-apis"]


def test_json_output(monkeypatch: Any) -> None:
    """--json flag emits valid JSON with expected keys."""
    monkeypatch.setattr("rdc.commands.capture.find_renderdoc", lambda: MagicMock())
    monkeypatch.setattr(
        "rdc.commands.capture.execute_and_capture",
        lambda *a, **kw: _make_capture_result(),
    )
    monkeypatch.setattr(
        "rdc.commands.capture.build_capture_options",
        lambda opts: MagicMock(),
    )

    result = CliRunner().invoke(capture_cmd, ["--json", "--", "/usr/bin/app"])
    assert result.exit_code == 0
    for line in result.output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            data = json.loads(line)
            assert data["success"] is True
            assert "path" in data
            assert "api" in data
            break
    else:
        raise AssertionError("no JSON line found in output")


def test_all_options(monkeypatch: Any) -> None:
    """Verify CaptureOptions flags are forwarded to build_capture_options."""
    captured_opts: list[dict[str, Any]] = []

    def fake_build(opts: dict[str, Any]) -> MagicMock:
        captured_opts.append(opts)
        return MagicMock()

    monkeypatch.setattr("rdc.commands.capture.find_renderdoc", lambda: MagicMock())
    monkeypatch.setattr(
        "rdc.commands.capture.execute_and_capture",
        lambda *a, **kw: _make_capture_result(),
    )
    monkeypatch.setattr("rdc.commands.capture.build_capture_options", fake_build)

    result = CliRunner().invoke(
        capture_cmd,
        [
            "--api-validation",
            "--callstacks",
            "--hook-children",
            "--ref-all-resources",
            "--",
            "/usr/bin/app",
        ],
    )
    assert result.exit_code == 0
    assert captured_opts[0]["api_validation"] is True
    assert captured_opts[0]["callstacks"] is True
    assert captured_opts[0]["hook_children"] is True
    assert captured_opts[0]["ref_all_resources"] is True


def test_capture_trigger_mode(monkeypatch: Any) -> None:
    """--trigger flag passes trigger=True to execute_and_capture."""
    call_kwargs: list[dict[str, Any]] = []

    def fake_capture(*args: Any, **kwargs: Any) -> Any:
        call_kwargs.append(kwargs)
        return _make_capture_result(success=True, path="", ident=99999)

    monkeypatch.setattr("rdc.commands.capture.find_renderdoc", lambda: MagicMock())
    monkeypatch.setattr("rdc.commands.capture.execute_and_capture", fake_capture)
    monkeypatch.setattr(
        "rdc.commands.capture.build_capture_options",
        lambda opts: MagicMock(),
    )

    result = CliRunner().invoke(capture_cmd, ["--trigger", "--", "/usr/bin/app"])
    assert result.exit_code == 0
    assert call_kwargs[0]["trigger"] is True


def test_app_args_forwarded(monkeypatch: Any) -> None:
    """Application arguments after -- are forwarded to execute_and_capture."""
    call_kwargs: list[dict[str, Any]] = []

    def fake_capture(*args: Any, **kwargs: Any) -> Any:
        call_kwargs.append({"args": args, "kwargs": kwargs})
        return _make_capture_result()

    monkeypatch.setattr("rdc.commands.capture.find_renderdoc", lambda: MagicMock())
    monkeypatch.setattr("rdc.commands.capture.execute_and_capture", fake_capture)
    monkeypatch.setattr("rdc.commands.capture.build_capture_options", lambda opts: MagicMock())

    result = CliRunner().invoke(
        capture_cmd, ["--", "/usr/bin/app", "--width", "800", "--height", "600"]
    )
    assert result.exit_code == 0
    # app is 2nd positional arg (after rd), args= is keyword
    assert call_kwargs[0]["args"][1] == "/usr/bin/app"
    assert call_kwargs[0]["kwargs"]["args"] == "--width 800 --height 600"


def _setup_capture_with_terminate(monkeypatch: Any, **result_kw: Any) -> list[int]:
    """Common setup: mock capture + terminate_process, return list of terminated pids."""
    terminated: list[int] = []
    monkeypatch.setattr("rdc.commands.capture.find_renderdoc", lambda: MagicMock())
    monkeypatch.setattr(
        "rdc.commands.capture.execute_and_capture",
        lambda *a, **kw: _make_capture_result(**result_kw),
    )
    monkeypatch.setattr("rdc.commands.capture.build_capture_options", lambda opts: MagicMock())
    monkeypatch.setattr(
        "rdc.commands.capture.terminate_process", lambda pid: (terminated.append(pid), True)[1]
    )
    return terminated


def test_default_terminates_process(monkeypatch: Any) -> None:
    """By default, successful capture terminates the target process using its PID."""
    terminated = _setup_capture_with_terminate(
        monkeypatch, success=True, path="/tmp/t.rdc", pid=1234
    )
    result = CliRunner().invoke(capture_cmd, ["--", "/usr/bin/app"])
    assert result.exit_code == 0
    assert terminated == [1234]


def test_keep_alive_skips_termination(monkeypatch: Any) -> None:
    """--keep-alive prevents process termination."""
    terminated = _setup_capture_with_terminate(
        monkeypatch, success=True, path="/tmp/t.rdc", pid=1234
    )
    result = CliRunner().invoke(capture_cmd, ["--keep-alive", "--", "/usr/bin/app"])
    assert result.exit_code == 0
    assert terminated == []


def test_trigger_skips_termination(monkeypatch: Any) -> None:
    """--trigger mode does not terminate the process."""
    terminated = _setup_capture_with_terminate(monkeypatch, success=True, path="", pid=1234)
    result = CliRunner().invoke(capture_cmd, ["--trigger", "--", "/usr/bin/app"])
    assert result.exit_code == 0
    assert terminated == []


def test_failed_capture_timeout_terminates_process(monkeypatch: Any) -> None:
    """B26: failed capture with timeout still terminates the target process."""
    terminated = _setup_capture_with_terminate(
        monkeypatch, success=False, error="timeout waiting for capture", pid=5678
    )
    result = CliRunner().invoke(capture_cmd, ["--", "/usr/bin/app"])
    assert result.exit_code != 0
    assert terminated == [5678]


def test_failed_capture_disconnect_terminates_process(monkeypatch: Any) -> None:
    """B26: failed capture with disconnect still terminates the target process."""
    terminated = _setup_capture_with_terminate(
        monkeypatch, success=False, error="target disconnected", pid=9101
    )
    result = CliRunner().invoke(capture_cmd, ["--", "/usr/bin/app"])
    assert result.exit_code != 0
    assert terminated == [9101]


def test_failed_capture_zero_pid_no_termination(monkeypatch: Any) -> None:
    """B26: failed capture with pid=0 (no process launched) skips termination."""
    terminated = _setup_capture_with_terminate(
        monkeypatch, success=False, error="inject failed", pid=0
    )
    result = CliRunner().invoke(capture_cmd, ["--", "/usr/bin/app"])
    assert result.exit_code != 0
    assert terminated == []


def test_failed_capture_keep_alive_skips_termination(monkeypatch: Any) -> None:
    """B26: --keep-alive prevents termination even on failure."""
    terminated = _setup_capture_with_terminate(
        monkeypatch, success=False, error="timeout", pid=7777
    )
    result = CliRunner().invoke(capture_cmd, ["--keep-alive", "--", "/usr/bin/app"])
    assert result.exit_code != 0
    assert terminated == []


def test_capture_path_on_stdout(monkeypatch: Any) -> None:
    """B24: capture path must appear on stdout for machine parsing."""
    monkeypatch.setattr("rdc.commands.capture.find_renderdoc", lambda: MagicMock())
    monkeypatch.setattr(
        "rdc.commands.capture.execute_and_capture",
        lambda *a, **kw: _make_capture_result(path="/tmp/captured.rdc"),
    )
    monkeypatch.setattr("rdc.commands.capture.build_capture_options", lambda opts: MagicMock())

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    _orig_echo = click.echo

    def _spy_echo(message: Any = None, err: bool = False, **kw: Any) -> Any:
        (stderr_lines if err else stdout_lines).append(str(message))
        return _orig_echo(message, err=err, **kw)

    monkeypatch.setattr("rdc.commands.capture.click.echo", _spy_echo)

    result = CliRunner().invoke(capture_cmd, ["--", "/usr/bin/app"])
    assert result.exit_code == 0
    assert any("/tmp/captured.rdc" in s for s in stdout_lines)
    assert all("next:" not in s for s in stdout_lines)


def test_fallback_capture_path_on_stdout(monkeypatch: Any) -> None:
    """B24: fallback renderdoccmd path also emits capture path to stdout."""
    monkeypatch.setattr("rdc.commands.capture.find_renderdoc", lambda: None)
    monkeypatch.setattr("rdc.commands.capture._find_renderdoccmd", lambda: "/usr/bin/renderdoccmd")

    def fake_run(argv: list[str], check: bool = False) -> DummyResult:
        return DummyResult(0)

    monkeypatch.setattr("subprocess.run", fake_run)

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    _orig_echo = click.echo

    def _spy_echo(message: Any = None, err: bool = False, **kw: Any) -> Any:
        (stderr_lines if err else stdout_lines).append(str(message))
        return _orig_echo(message, err=err, **kw)

    monkeypatch.setattr("rdc.commands.capture.click.echo", _spy_echo)

    result = CliRunner().invoke(capture_cmd, ["-o", "/tmp/out.rdc", "--", "/usr/bin/app"])
    assert result.exit_code == 0
    expected_path = str(Path("/tmp/out.rdc"))
    assert any(expected_path in s for s in stdout_lines)
    assert all("next:" not in s for s in stdout_lines)


def test_missing_executable() -> None:
    """No arguments after -- raises usage error."""
    result = CliRunner().invoke(capture_cmd, [])
    assert result.exit_code != 0
    assert "EXECUTABLE" in result.output


def test_split_mode_calls_daemon(monkeypatch: Any, tmp_path: Path) -> None:
    """Split-mode session routes capture through JSON-RPC."""
    monkeypatch.setattr("rdc.commands.capture.split_session_active", lambda: True)
    monkeypatch.chdir(tmp_path)
    captured: dict[str, Any] = {}

    def fake_call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        captured["method"] = method
        captured["payload"] = payload
        return {
            "success": True,
            "path": "/tmp/rpc.rdc",
            "frame": 0,
            "byte_size": 0,
            "api": "Vulkan",
            "local": True,
            "ident": 0,
            "pid": 0,
            "error": "",
            "remote_path": "",
        }

    monkeypatch.setattr("rdc.commands.capture.call", fake_call)
    monkeypatch.setattr("rdc.commands.capture.fetch_remote_file", lambda path: b"rdc")

    result = CliRunner().invoke(
        capture_cmd,
        ["--api-validation", "--", "/usr/bin/app", "--width", "800"],
    )
    assert result.exit_code == 0
    assert captured["method"] == "capture_run"
    assert captured["payload"]["opts"] == {"api_validation": True}
    assert "--width" in captured["payload"]["args"]
    assert (tmp_path / "rpc.rdc").exists()
