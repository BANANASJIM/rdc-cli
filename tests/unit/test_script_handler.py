"""Tests for daemon script handler."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request


def _make_state() -> DaemonState:
    controller = SimpleNamespace(
        GetRootActions=lambda: [],
        GetResources=lambda: [],
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        GetPipelineState=lambda: SimpleNamespace(),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: SimpleNamespace(chunks=[]),
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
    )
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=controller, version=(1, 41))
    state.api_name = "Vulkan"
    state.max_eid = 10
    return state


def _req(method: str, **params: Any) -> dict[str, Any]:
    p: dict[str, Any] = {"_token": "tok"}
    p.update(params)
    return {"id": 1, "method": method, "params": p}


def _write_script(tmp_path: Path, content: str, name: str = "script.py") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestScriptHappyPaths:
    def test_print_and_result(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, 'print("hello")\nresult = 42')
        resp, keep = _handle_request(_req("script", path=str(script)), _make_state())
        assert keep is True
        r = resp["result"]
        assert r["stdout"] == "hello\n"
        assert r["return_value"] == 42
        assert r["elapsed_ms"] >= 0
        assert r["stderr"] == ""

    def test_stderr_capture(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, 'import sys; sys.stderr.write("warn\\n")')
        resp, _ = _handle_request(_req("script", path=str(script)), _make_state())
        r = resp["result"]
        assert r["stderr"] == "warn\n"
        assert r["stdout"] == ""

    def test_no_result_variable(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, 'print("only stdout")')
        resp, _ = _handle_request(_req("script", path=str(script)), _make_state())
        assert resp["result"]["return_value"] is None

    def test_non_serializable_result(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, "result = object()")
        resp, _ = _handle_request(_req("script", path=str(script)), _make_state())
        rv = resp["result"]["return_value"]
        assert isinstance(rv, str)
        assert len(rv) > 0

    def test_dict_list_result(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, 'result = {"k": [1, 2]}')
        resp, _ = _handle_request(_req("script", path=str(script)), _make_state())
        assert resp["result"]["return_value"] == {"k": [1, 2]}

    def test_empty_script(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, "")
        resp, _ = _handle_request(_req("script", path=str(script)), _make_state())
        r = resp["result"]
        assert r["stdout"] == ""
        assert r["stderr"] == ""
        assert r["return_value"] is None

    def test_args_forwarded(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, 'print(args["mode"])\nresult = args["mode"]')
        resp, _ = _handle_request(
            _req("script", path=str(script), args={"mode": "fast"}),
            _make_state(),
        )
        assert resp["result"]["stdout"] == "fast\n"
        assert resp["result"]["return_value"] == "fast"


class TestScriptMissingParams:
    def test_script_missing_path(self) -> None:
        resp, keep = _handle_request(_req("script"), _make_state())
        assert keep is True
        assert resp["error"]["code"] == -32602
        assert "path" in resp["error"]["message"]


class TestScriptErrorPaths:
    def test_no_replay_loaded(self, tmp_path: Path) -> None:
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        script = _write_script(tmp_path, "result = 1")
        resp, keep = _handle_request(_req("script", path=str(script)), state)
        assert keep is True
        assert resp["error"]["code"] == -32002
        assert resp["error"]["message"] == "no replay loaded"

    def test_file_not_found(self) -> None:
        resp, keep = _handle_request(_req("script", path="/nonexistent/path.py"), _make_state())
        assert keep is True
        assert resp["error"]["code"] == -32002
        assert "script not found" in resp["error"]["message"]

    def test_path_is_directory(self, tmp_path: Path) -> None:
        resp, keep = _handle_request(_req("script", path=str(tmp_path)), _make_state())
        assert keep is True
        assert resp["error"]["code"] == -32002
        assert resp["error"]["message"] == "script path is a directory"

    def test_syntax_error(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, "def foo(:")
        resp, keep = _handle_request(_req("script", path=str(script)), _make_state())
        assert keep is True
        assert resp["error"]["code"] == -32002
        assert resp["error"]["message"].startswith("syntax error:")
        assert "1" in resp["error"]["message"]

    def test_runtime_error(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, 'raise ValueError("bad input")')
        resp, keep = _handle_request(_req("script", path=str(script)), _make_state())
        assert keep is True
        assert resp["error"]["code"] == -32002
        assert "script error: ValueError: bad input" in resp["error"]["message"]

    def test_system_exit(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, "import sys; sys.exit(0)")
        resp, keep = _handle_request(_req("script", path=str(script)), _make_state())
        assert keep is True
        assert resp["error"]["code"] == -32002
        assert "script error: SystemExit: 0" in resp["error"]["message"]

    def test_keyboard_interrupt(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, "raise KeyboardInterrupt()")
        resp, keep = _handle_request(_req("script", path=str(script)), _make_state())
        assert keep is True
        assert resp["error"]["code"] == -32002
        assert "KeyboardInterrupt" in resp["error"]["message"]


class TestScriptIsolation:
    def test_stdout_restored(self, tmp_path: Path) -> None:
        original_stdout = sys.stdout
        script = _write_script(tmp_path, 'print("captured")')
        _handle_request(_req("script", path=str(script)), _make_state())
        assert sys.stdout is original_stdout

    def test_stdout_restored_on_error(self, tmp_path: Path) -> None:
        original_stdout = sys.stdout
        script = _write_script(tmp_path, 'raise RuntimeError("boom")')
        _handle_request(_req("script", path=str(script)), _make_state())
        assert sys.stdout is original_stdout

    def test_independent_globals(self, tmp_path: Path) -> None:
        script1 = _write_script(tmp_path, "result = 111", "s1.py")
        script2 = _write_script(tmp_path, "result = 222", "s2.py")
        state = _make_state()
        resp1, _ = _handle_request(_req("script", path=str(script1)), state)
        resp2, _ = _handle_request(_req("script", path=str(script2)), state)
        assert resp1["result"]["return_value"] == 111
        assert resp2["result"]["return_value"] == 222
