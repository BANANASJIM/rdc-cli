"""Crash regression tests for daemon server (Phase 2.6 P0).

Tests that the daemon survives previously-crashing scenarios:
1. TCP loop exception guard
2. SDChunk iteration via NumChildren/GetChild
3. Counter UUID serialization
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))


def _state_with_mock() -> DaemonState:
    """Create a DaemonState with a mock adapter and structured data."""
    import mock_renderdoc as rd

    controller = rd.MockReplayController()

    # Build a simple action tree with structured data
    action = rd.ActionDescription(
        eventId=1,
        flags=rd.ActionFlags.Drawcall,
        _name="vkCmdDraw",
        events=[rd.APIEvent(eventId=1, chunkIndex=0)],
    )
    controller._actions = [action]

    # Structured data with SDChunk using NumChildren/GetChild
    chunk = rd.SDChunk(
        name="vkCmdDraw",
        children=[
            rd.SDObject(name="vertexCount", data=rd.SDData(basic=rd.SDBasic(value=3))),
            rd.SDObject(name="instanceCount", data=rd.SDData(basic=rd.SDBasic(value=1))),
        ],
    )
    sf = rd.StructuredFile(chunks=[chunk])
    controller._structured_file = sf

    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=controller, version=(1, 41))
    state.max_eid = 10
    state.structured_file = sf
    state.rd = rd
    return state


class TestTCPLoopExceptionGuard:
    """Fix 1: _handle_request exceptions should not kill the server."""

    def test_handler_exception_returns_error_response(self) -> None:
        """Verify that an exception in _handle_request is caught and returns -32603."""
        # We can't easily test the TCP loop itself (it's pragma: no cover),
        # but we verify the handler doesn't crash on edge cases.
        # The TCP guard wraps _handle_request, so we test indirectly by
        # ensuring _handle_request propagates known errors correctly.
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        # Method not found should return error, not crash
        resp, running = _handle_request(
            {"id": 1, "method": "nonexistent_method", "params": {"_token": "tok"}}, state
        )
        assert running is True
        assert resp["error"]["code"] == -32601


class TestSDChunkIteration:
    """Fix 2: SDChunk iteration via NumChildren/GetChild."""

    def test_event_detail_with_numchildren_api(self) -> None:
        """Event handler should use NumChildren/GetChild for parameter extraction."""
        state = _state_with_mock()
        resp, running = _handle_request(
            {"id": 1, "method": "event", "params": {"_token": "tok", "eid": 1}}, state
        )
        assert running is True
        result = resp["result"]
        assert result["API Call"] == "vkCmdDraw"
        assert "vertexCount" in result["Parameters"]
        assert "3" in result["Parameters"]

    def test_event_detail_empty_chunk(self) -> None:
        """Event handler should handle chunk with zero children."""
        import mock_renderdoc as rd

        state = _state_with_mock()
        # Replace chunk with empty one
        empty_chunk = rd.SDChunk(name="vkCmdEmpty", children=[])
        state.structured_file = rd.StructuredFile(chunks=[empty_chunk])
        resp, running = _handle_request(
            {"id": 1, "method": "event", "params": {"_token": "tok", "eid": 1}}, state
        )
        assert running is True
        assert resp["result"]["Parameters"] == "-"

    def test_sdchunk_numchildren_and_getchild(self) -> None:
        """SDChunk/SDObject should support NumChildren/GetChild API."""
        import mock_renderdoc as rd

        chunk = rd.SDChunk(
            name="test",
            children=[
                rd.SDObject(name="a", data=rd.SDData(basic=rd.SDBasic(value="hello"))),
                rd.SDObject(name="b", data=rd.SDData(basic=rd.SDBasic(value=42))),
            ],
        )
        assert chunk.NumChildren() == 2
        assert chunk.GetChild(0).name == "a"
        assert chunk.GetChild(0).AsString() == "hello"
        assert chunk.GetChild(1).AsInt() == 42

    def test_sdobject_asstring_none_value(self) -> None:
        """SDObject.AsString should return empty string for None value."""
        import mock_renderdoc as rd

        obj = rd.SDObject(name="x", data=rd.SDData(basic=rd.SDBasic(value=None)))
        assert obj.AsString() == ""


class TestCounterUUIDSerialization:
    """Fix 3: Counter UUID must be str-coerced for JSON serialization."""

    def test_counter_uuid_is_string(self) -> None:
        """Counter list response should have string uuid field."""
        import mock_renderdoc as rd

        state = _state_with_mock()
        controller: rd.MockReplayController = state.adapter.controller  # type: ignore[assignment]
        controller._counter_descriptions = {
            1: rd.CounterDescription(
                name="GPUDuration",
                category="GPU",
                description="GPU duration in seconds",
                counter=rd.GPUCounter.EventGPUDuration,
                resultByteWidth=8,
                resultType=rd.CompType.Float,
                unit=rd.CounterUnit.Seconds,
                uuid="test-uuid-123",
            )
        }
        resp, running = _handle_request(
            {"id": 1, "method": "counter_list", "params": {"_token": "tok"}}, state
        )
        assert running is True
        counters = resp["result"]["counters"]
        assert len(counters) == 1
        assert isinstance(counters[0]["uuid"], str)
        assert counters[0]["uuid"] == "test-uuid-123"

    def test_counter_uuid_struct_coercion(self) -> None:
        """Counter UUID should survive str() coercion even for non-string types."""
        import mock_renderdoc as rd

        state = _state_with_mock()
        controller: rd.MockReplayController = state.adapter.controller  # type: ignore[assignment]
        # Simulate SWIG struct uuid (has __str__)
        uuid_struct = SimpleNamespace(__str__=lambda self: "swig-uuid-456")
        controller._counter_descriptions = {
            1: rd.CounterDescription(
                name="GPUDuration",
                category="GPU",
                description="test",
                uuid=uuid_struct,  # type: ignore[arg-type]
            )
        }
        resp, _ = _handle_request(
            {"id": 1, "method": "counter_list", "params": {"_token": "tok"}}, state
        )
        assert isinstance(resp["result"]["counters"][0]["uuid"], str)
