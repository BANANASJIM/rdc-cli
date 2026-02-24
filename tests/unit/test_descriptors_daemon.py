"""Tests for the descriptors daemon handler."""

from __future__ import annotations

from types import SimpleNamespace

import mock_renderdoc as rd
from conftest import make_daemon_state
from mock_renderdoc import (
    AddressMode,
    Descriptor,
    DescriptorAccess,
    DescriptorType,
    MockPipeState,
    ResourceId,
    SamplerDescriptor,
    ShaderStage,
    UsedDescriptor,
)

from rdc.daemon_server import DaemonState, _handle_request


def _make_state_with_pipe(pipe: MockPipeState, **overrides: object) -> DaemonState:
    """Create DaemonState using the given pipe."""
    ctrl = SimpleNamespace(
        GetRootActions=lambda: [],
        GetResources=lambda: [],
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: SimpleNamespace(chunks=[]),
        GetPipelineState=lambda: pipe,
        GetTextures=lambda: [],
        GetBuffers=lambda: [],
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
    )
    return make_daemon_state(ctrl=ctrl, token="test-token", rd=rd, **overrides)  # type: ignore[arg-type]


def _call(state: DaemonState, method: str, **params: object) -> dict:
    params["_token"] = state.token
    req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp, _ = _handle_request(req, state)
    return resp


# ---------------------------------------------------------------------------
# test cases
# ---------------------------------------------------------------------------


def test_descriptors_happy_path() -> None:
    """2 ConstantBuffer descriptors (VS + PS) are returned correctly."""
    pipe = MockPipeState()
    pipe._used_descriptors = [
        UsedDescriptor(
            access=DescriptorAccess(
                stage=ShaderStage.Vertex,
                type=DescriptorType.ConstantBuffer,
                index=0,
                arrayElement=0,
            ),
            descriptor=Descriptor(resource=ResourceId(42), byteSize=256),
        ),
        UsedDescriptor(
            access=DescriptorAccess(
                stage=ShaderStage.Pixel,
                type=DescriptorType.ConstantBuffer,
                index=0,
                arrayElement=0,
            ),
            descriptor=Descriptor(resource=ResourceId(43), byteSize=128),
        ),
    ]
    state = _make_state_with_pipe(pipe)
    resp = _call(state, "descriptors", eid=5)

    result = resp["result"]
    assert result["eid"] == 5
    assert len(result["descriptors"]) == 2
    for entry in result["descriptors"]:
        expected = {
            "stage",
            "type",
            "index",
            "array_element",
            "resource_id",
            "format",
            "byte_size",
        }
        assert set(entry.keys()) >= expected
        assert entry["type"] == "ConstantBuffer"


def test_descriptors_mixed_types() -> None:
    """1 ConstantBuffer + 1 Image + 1 Sampler; sampler has sub-dict, others don't."""
    pipe = MockPipeState()
    pipe._used_descriptors = [
        UsedDescriptor(
            access=DescriptorAccess(
                stage=ShaderStage.Vertex,
                type=DescriptorType.ConstantBuffer,
                index=0,
                arrayElement=0,
            ),
            descriptor=Descriptor(resource=ResourceId(10), byteSize=64),
        ),
        UsedDescriptor(
            access=DescriptorAccess(
                stage=ShaderStage.Pixel,
                type=DescriptorType.Image,
                index=1,
                arrayElement=0,
            ),
            descriptor=Descriptor(resource=ResourceId(20), byteSize=0),
        ),
        UsedDescriptor(
            access=DescriptorAccess(
                stage=ShaderStage.Pixel,
                type=DescriptorType.Sampler,
                index=0,
                arrayElement=0,
            ),
            descriptor=Descriptor(resource=ResourceId(0), byteSize=0),
            sampler=SamplerDescriptor(
                addressU=AddressMode.ClampEdge,
                addressV=AddressMode.Wrap,
                addressW=AddressMode.Mirror,
                filter="Linear",
                compareFunction="",
                minLOD=0.0,
                maxLOD=1000.0,
                mipBias=0.0,
                maxAnisotropy=1.0,
            ),
        ),
    ]
    state = _make_state_with_pipe(pipe)
    resp = _call(state, "descriptors", eid=10)

    descriptors = resp["result"]["descriptors"]
    assert len(descriptors) == 3

    sampler_entries = [d for d in descriptors if d["type"] == "Sampler"]
    non_sampler_entries = [d for d in descriptors if d["type"] != "Sampler"]

    assert len(sampler_entries) == 1
    s = sampler_entries[0]["sampler"]
    assert set(s.keys()) >= {
        "address_u",
        "address_v",
        "address_w",
        "filter",
        "compare_function",
        "min_lod",
        "max_lod",
        "mip_bias",
        "max_anisotropy",
    }
    # Verify enum serialization uses bare names, not qualified (e.g. "Wrap" not "AddressMode.Wrap")
    assert s["address_u"] == "ClampEdge"
    assert s["address_v"] == "Wrap"
    assert s["address_w"] == "Mirror"

    for entry in non_sampler_entries:
        assert "sampler" not in entry


def test_descriptors_empty() -> None:
    """No used descriptors returns empty list."""
    pipe = MockPipeState()
    pipe._used_descriptors = []
    state = _make_state_with_pipe(pipe)
    resp = _call(state, "descriptors", eid=0)
    assert resp["result"]["descriptors"] == []


def test_descriptors_no_adapter() -> None:
    """adapter=None returns error -32002."""
    state = DaemonState(capture="test.rdc", current_eid=0, token="test-token")
    resp = _call(state, "descriptors", eid=5)
    assert resp["error"]["code"] == -32002


def test_descriptors_eid_out_of_range() -> None:
    """eid beyond max_eid returns error -32002."""
    pipe = MockPipeState()
    state = _make_state_with_pipe(pipe, max_eid=10)
    resp = _call(state, "descriptors", eid=999)
    assert resp["error"]["code"] == -32002
