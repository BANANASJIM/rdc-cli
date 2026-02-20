"""Sanity tests for mock renderdoc module."""

from __future__ import annotations

import sys
from pathlib import Path

# Make mock module importable
sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd  # noqa: E402


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
