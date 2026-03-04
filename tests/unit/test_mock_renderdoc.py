"""Sanity tests for mock renderdoc module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

# Make mock module importable
import mock_renderdoc as rd
import pytest


@pytest.fixture
def mock_ctrl() -> rd.MockReplayController:
    return rd.MockReplayController()


def test_capture_lifecycle() -> None:
    """Full lifecycle: init → open file → open capture → query → shutdown."""
    rd.InitialiseReplay(rd.GlobalEnvironment(), [])

    cap = rd.OpenCaptureFile()
    result = cap.OpenFile("test.rdc", "", None)
    assert result == rd.ResultCode.Succeeded
    assert cap.LocalReplaySupport() == rd.ReplaySupport.Supported

    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    assert result == rd.ResultCode.Succeeded

    # Basic queries
    assert controller.GetRootActions() == []
    assert controller.GetResources() == []
    props = controller.GetAPIProperties()
    assert props.pipelineType == "Vulkan"

    # Pipeline state
    pipe_state = controller.GetPipelineState()
    assert pipe_state.IsCaptureVK() is True
    assert pipe_state.GetShader(rd.ShaderStage.Vertex) == rd.ResourceId.Null()

    # Shutdown
    controller.Shutdown()
    assert controller._shutdown_called is True
    cap.Shutdown()
    assert cap._shutdown_called is True


def test_action_description() -> None:
    action = rd.ActionDescription(
        eventId=42,
        flags=rd.ActionFlags.Drawcall | rd.ActionFlags.Indexed,
        numIndices=3600,
        numInstances=1,
        _name="GBuffer/Floor",
    )
    assert action.GetName(None) == "GBuffer/Floor"
    assert action.flags & rd.ActionFlags.Drawcall
    assert action.flags & rd.ActionFlags.Indexed
    assert action.numIndices == 3600


def test_resource_id_equality() -> None:
    a = rd.ResourceId(42)
    b = rd.ResourceId(42)
    c = rd.ResourceId(0)
    assert a == b
    assert a != c
    assert c == rd.ResourceId.Null()


def test_version_string() -> None:
    assert rd.GetVersionString() == "v1.41"
    assert rd.GetCommitHash() == "abc123"


# ---------------------------------------------------------------------------
# T1 — ResourceId has no .value attribute
# ---------------------------------------------------------------------------


def test_resource_id_no_value_attribute() -> None:
    rid = rd.ResourceId(42)
    with pytest.raises(AttributeError):
        _ = rid.value  # type: ignore[attr-defined]


def test_resource_id_int_works() -> None:
    assert int(rd.ResourceId(42)) == 42


# ---------------------------------------------------------------------------
# T2 — SaveTexture configurable failure
# ---------------------------------------------------------------------------


def test_save_texture_success_by_default(
    mock_ctrl: rd.MockReplayController,
    tmp_path: Path,
) -> None:
    texsave = MagicMock()
    texsave.resourceId = rd.ResourceId(1)
    assert mock_ctrl.SaveTexture(texsave, str(tmp_path / "out.png")) is True


def test_save_texture_failure_when_flag_set(mock_ctrl: rd.MockReplayController) -> None:
    mock_ctrl._save_texture_fails = True
    texsave = MagicMock()
    texsave.resourceId = rd.ResourceId(1)
    assert mock_ctrl.SaveTexture(texsave, "/tmp/out.png") is False


# ---------------------------------------------------------------------------
# T3 — GetTextureData / GetBufferData per-resource
# ---------------------------------------------------------------------------


def test_get_texture_data_default(mock_ctrl: rd.MockReplayController) -> None:
    data = mock_ctrl.GetTextureData(rd.ResourceId(99), MagicMock())
    assert isinstance(data, bytes) and len(data) > 0


def test_get_texture_data_configurable(mock_ctrl: rd.MockReplayController) -> None:
    mock_ctrl._texture_data[5] = b"custom"
    assert mock_ctrl.GetTextureData(rd.ResourceId(5), MagicMock()) == b"custom"


def test_get_texture_data_raises_on_error_id(mock_ctrl: rd.MockReplayController) -> None:
    mock_ctrl._raise_on_texture_id.add(7)
    with pytest.raises(RuntimeError):
        mock_ctrl.GetTextureData(rd.ResourceId(7), MagicMock())


# ---------------------------------------------------------------------------
# T4 — ContinueDebug index-based (not consumable)
# ---------------------------------------------------------------------------


def test_continue_debug_index_based(mock_ctrl: rd.MockReplayController) -> None:
    debugger = object()
    state1 = rd.ShaderDebugState(stepIndex=0)
    state2 = rd.ShaderDebugState(stepIndex=1)
    mock_ctrl._debug_states[id(debugger)] = [[state1], [state2]]

    assert mock_ctrl.ContinueDebug(debugger) == [state1]
    assert mock_ctrl.ContinueDebug(debugger) == [state2]
    assert mock_ctrl.ContinueDebug(debugger) == []
    assert mock_ctrl.ContinueDebug(debugger) == []


# ---------------------------------------------------------------------------
# T5 — FreeTrace double-free detection
# ---------------------------------------------------------------------------


def test_free_trace_records_freed(mock_ctrl: rd.MockReplayController) -> None:
    trace = MagicMock()
    mock_ctrl.FreeTrace(trace)
    assert id(trace) in mock_ctrl._freed_traces


def test_free_trace_double_free_raises(mock_ctrl: rd.MockReplayController) -> None:
    trace = MagicMock()
    mock_ctrl.FreeTrace(trace)
    with pytest.raises(RuntimeError, match="double-free"):
        mock_ctrl.FreeTrace(trace)


# ---------------------------------------------------------------------------
# T6 — MockPipeState mutable reference via per-eid _pipe_states
# ---------------------------------------------------------------------------


def test_pipe_state_per_eid_switching() -> None:
    """SetFrameEvent switches _pipe_state when per-eid states are configured."""
    ctrl = rd.MockReplayController()
    ps1 = rd.MockPipeState()
    ps1._shaders[rd.ShaderStage.Vertex] = rd.ResourceId(100)
    ps2 = rd.MockPipeState()
    ps2._shaders[rd.ShaderStage.Vertex] = rd.ResourceId(200)
    ctrl._pipe_states = {10: ps1, 20: ps2}

    ctrl.SetFrameEvent(10, True)
    state = ctrl.GetPipelineState()
    assert int(state.GetShader(rd.ShaderStage.Vertex)) == 100
    assert state is ps1

    ctrl.SetFrameEvent(20, True)
    state = ctrl.GetPipelineState()
    assert int(state.GetShader(rd.ShaderStage.Vertex)) == 200
    assert state is ps2


def test_pipe_state_fallback_when_no_per_eid() -> None:
    """SetFrameEvent keeps default _pipe_state when eid not in _pipe_states."""
    ctrl = rd.MockReplayController()
    default = ctrl._pipe_state
    ctrl.SetFrameEvent(99, True)
    assert ctrl.GetPipelineState() is default


def test_pipe_state_backward_compat_direct_write() -> None:
    """Direct writes to ctrl._pipe_state still work (backward compat)."""
    ctrl = rd.MockReplayController()
    ctrl._pipe_state._shaders[rd.ShaderStage.Pixel] = rd.ResourceId(42)
    assert int(ctrl.GetPipelineState().GetShader(rd.ShaderStage.Pixel)) == 42


# ---------------------------------------------------------------------------
# T7 — GetCallstack per-eid via _callstacks dict
# ---------------------------------------------------------------------------


def test_get_callstack_empty_by_default(mock_ctrl: rd.MockReplayController) -> None:
    """GetCallstack returns empty list when no callstacks configured."""
    assert mock_ctrl.GetCallstack(0) == []


def test_get_callstack_per_eid(mock_ctrl: rd.MockReplayController) -> None:
    """GetCallstack returns configured callstack for a given eid."""
    mock_ctrl._callstacks = {
        0: [0x1000, 0x2000, 0x3000],
        11: [0x4000, 0x5000],
    }
    assert mock_ctrl.GetCallstack(0) == [0x1000, 0x2000, 0x3000]
    assert mock_ctrl.GetCallstack(11) == [0x4000, 0x5000]
    assert mock_ctrl.GetCallstack(99) == []
