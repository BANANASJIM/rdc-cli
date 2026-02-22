"""Unit tests for shader edit-replay handlers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))
import mock_renderdoc as rd  # noqa: E402


def _make_state(ctrl: rd.MockReplayController) -> DaemonState:
    adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    state.adapter = adapter
    state.max_eid = 1000
    state.rd = rd
    return state


def _req(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": 1,
        "method": method,
        "params": {"_token": "tok", **(params or {})},
    }


# ── shader_encodings ──────────────────────────────────────────────────


class TestShaderEncodings:
    def test_happy(self) -> None:
        ctrl = rd.MockReplayController()
        state = _make_state(ctrl)
        resp, running = _handle_request(_req("shader_encodings"), state)
        assert running is True
        encodings = resp["result"]["encodings"]
        assert len(encodings) == 2
        assert encodings[0] == {"value": 2, "name": "GLSL"}
        assert encodings[1] == {"value": 3, "name": "SPIRV"}

    def test_no_adapter(self) -> None:
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(_req("shader_encodings"), state)
        assert resp["error"]["code"] == -32002


# ── shader_build ──────────────────────────────────────────────────────


class TestShaderBuild:
    def test_happy(self) -> None:
        ctrl = rd.MockReplayController()
        state = _make_state(ctrl)
        resp, _ = _handle_request(
            _req("shader_build", {"stage": "ps", "source": "void main(){}"}), state
        )
        result = resp["result"]
        assert result["shader_id"] == 1000
        assert result["warnings"] == ""
        assert 1000 in state.built_shaders

    def test_compile_error(self) -> None:
        ctrl = rd.MockReplayController()
        # Override BuildTargetShader to return ResourceId(0)
        ctrl.BuildTargetShader = lambda entry, enc, src, flags, stage: (  # type: ignore[assignment]
            rd.ResourceId(0),
            "syntax error",
        )
        state = _make_state(ctrl)
        resp, _ = _handle_request(_req("shader_build", {"stage": "ps", "source": "bad"}), state)
        assert resp["error"]["code"] == -32001
        assert "syntax error" in resp["error"]["message"]

    def test_no_adapter(self) -> None:
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(_req("shader_build", {"stage": "ps", "source": "x"}), state)
        assert resp["error"]["code"] == -32002

    def test_invalid_stage(self) -> None:
        ctrl = rd.MockReplayController()
        state = _make_state(ctrl)
        resp, _ = _handle_request(_req("shader_build", {"stage": "invalid", "source": "x"}), state)
        assert resp["error"]["code"] == -32602

    def test_unknown_encoding(self) -> None:
        ctrl = rd.MockReplayController()
        state = _make_state(ctrl)
        resp, _ = _handle_request(
            _req("shader_build", {"stage": "ps", "source": "x", "encoding": "INVALID"}),
            state,
        )
        assert resp["error"]["code"] == -32602
        assert "unknown encoding" in resp["error"]["message"]

    def test_missing_source(self) -> None:
        ctrl = rd.MockReplayController()
        state = _make_state(ctrl)
        resp, _ = _handle_request(_req("shader_build", {"stage": "ps"}), state)
        assert resp["error"]["code"] == -32602
        assert "source" in resp["error"]["message"]

    def test_default_entry(self) -> None:
        ctrl = rd.MockReplayController()
        calls: list[str] = []
        original = ctrl.BuildTargetShader

        def tracking_build(entry: str, *args: Any) -> Any:
            calls.append(entry)
            return original(entry, *args)

        ctrl.BuildTargetShader = tracking_build  # type: ignore[assignment]
        state = _make_state(ctrl)
        _handle_request(_req("shader_build", {"stage": "ps", "source": "void main(){}"}), state)
        assert calls[0] == "main"


# ── shader_replace ────────────────────────────────────────────────────


class TestShaderReplace:
    def _setup_state(self) -> tuple[rd.MockReplayController, DaemonState]:
        ctrl = rd.MockReplayController()
        ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = rd.ResourceId(500)
        state = _make_state(ctrl)
        # Pre-build a shader
        state.built_shaders[1000] = rd.ResourceId(1000)
        return ctrl, state

    def test_happy(self) -> None:
        ctrl, state = self._setup_state()
        resp, _ = _handle_request(
            _req("shader_replace", {"eid": 10, "stage": "ps", "shader_id": 1000}), state
        )
        result = resp["result"]
        assert result["ok"] is True
        assert result["original_id"] == 500
        assert 500 in state.shader_replacements

    def test_missing_shader_id(self) -> None:
        ctrl, state = self._setup_state()
        resp, _ = _handle_request(_req("shader_replace", {"eid": 10, "stage": "ps"}), state)
        assert resp["error"]["code"] == -32602
        assert "shader_id" in resp["error"]["message"]

    def test_missing_eid(self) -> None:
        ctrl, state = self._setup_state()
        resp, _ = _handle_request(_req("shader_replace", {"stage": "ps", "shader_id": 1000}), state)
        assert resp["error"]["code"] == -32602
        assert "eid" in resp["error"]["message"]

    def test_unknown_shader(self) -> None:
        ctrl, state = self._setup_state()
        resp, _ = _handle_request(
            _req("shader_replace", {"eid": 10, "stage": "ps", "shader_id": 9999}), state
        )
        assert resp["error"]["code"] == -32001

    def test_no_shader_bound(self) -> None:
        ctrl = rd.MockReplayController()
        # No shader set at ps stage (defaults to ResourceId(0))
        state = _make_state(ctrl)
        state.built_shaders[1000] = rd.ResourceId(1000)
        resp, _ = _handle_request(
            _req("shader_replace", {"eid": 10, "stage": "ps", "shader_id": 1000}), state
        )
        assert resp["error"]["code"] == -32001
        assert "no shader bound" in resp["error"]["message"]

    def test_no_adapter(self) -> None:
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(
            _req("shader_replace", {"eid": 10, "stage": "ps", "shader_id": 1}), state
        )
        assert resp["error"]["code"] == -32002

    def test_cache_invalidation(self) -> None:
        ctrl, state = self._setup_state()
        state._eid_cache = 10
        _handle_request(
            _req("shader_replace", {"eid": 10, "stage": "ps", "shader_id": 1000}), state
        )
        assert state._eid_cache == -1


# ── shader_restore ────────────────────────────────────────────────────


class TestShaderRestore:
    def _setup_state(self) -> tuple[rd.MockReplayController, DaemonState]:
        ctrl = rd.MockReplayController()
        ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = rd.ResourceId(500)
        state = _make_state(ctrl)
        state.shader_replacements[500] = rd.ResourceId(500)
        return ctrl, state

    def test_happy(self) -> None:
        ctrl, state = self._setup_state()
        resp, _ = _handle_request(_req("shader_restore", {"eid": 10, "stage": "ps"}), state)
        assert resp["result"]["ok"] is True
        assert 500 not in state.shader_replacements

    def test_missing_eid(self) -> None:
        ctrl, state = self._setup_state()
        resp, _ = _handle_request(_req("shader_restore", {"stage": "ps"}), state)
        assert resp["error"]["code"] == -32602
        assert "eid" in resp["error"]["message"]

    def test_no_replacement(self) -> None:
        ctrl = rd.MockReplayController()
        ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = rd.ResourceId(500)
        state = _make_state(ctrl)
        # No replacement active
        resp, _ = _handle_request(_req("shader_restore", {"eid": 10, "stage": "ps"}), state)
        assert resp["error"]["code"] == -32001

    def test_no_adapter(self) -> None:
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(_req("shader_restore", {"eid": 10, "stage": "ps"}), state)
        assert resp["error"]["code"] == -32002


# ── shader_restore_all ────────────────────────────────────────────────


class TestShaderRestoreAll:
    def test_happy(self) -> None:
        ctrl = rd.MockReplayController()
        state = _make_state(ctrl)
        state.shader_replacements[500] = rd.ResourceId(500)
        state.shader_replacements[600] = rd.ResourceId(600)
        state.built_shaders[1000] = rd.ResourceId(1000)
        state.built_shaders[1001] = rd.ResourceId(1001)

        resp, _ = _handle_request(_req("shader_restore_all"), state)
        result = resp["result"]
        assert result["ok"] is True
        assert result["restored"] == 2
        assert result["freed"] == 2
        assert len(state.shader_replacements) == 0
        assert len(state.built_shaders) == 0

    def test_empty(self) -> None:
        ctrl = rd.MockReplayController()
        state = _make_state(ctrl)
        resp, _ = _handle_request(_req("shader_restore_all"), state)
        result = resp["result"]
        assert result["ok"] is True
        assert result["restored"] == 0
        assert result["freed"] == 0

    def test_free_called(self) -> None:
        ctrl = rd.MockReplayController()
        state = _make_state(ctrl)
        state.built_shaders[1000] = rd.ResourceId(1000)
        state.built_shaders[1001] = rd.ResourceId(1001)

        _handle_request(_req("shader_restore_all"), state)
        assert 1000 in ctrl._freed
        assert 1001 in ctrl._freed


# ── shutdown cleans shader resources ─────────────────────────────────


class TestShutdownCleansShaders:
    def test_shutdown_cleans_replacements_and_built(self) -> None:
        ctrl = rd.MockReplayController()
        state = _make_state(ctrl)
        state.shader_replacements[500] = rd.ResourceId(500)
        state.shader_replacements[600] = rd.ResourceId(600)
        state.built_shaders[1000] = rd.ResourceId(1000)
        state.built_shaders[1001] = rd.ResourceId(1001)

        resp, running = _handle_request(_req("shutdown"), state)
        assert running is False
        assert resp["result"]["ok"] is True
        assert len(state.shader_replacements) == 0
        assert len(state.built_shaders) == 0
        assert 1000 in ctrl._freed
        assert 1001 in ctrl._freed
