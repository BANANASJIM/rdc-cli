"""Tests for require_pipe and PipeError."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from rdc.daemon_server import DaemonState
from rdc.handlers._helpers import PipeError, require_pipe


class TestRequirePipe:
    def test_raises_pipe_error_no_adapter(self) -> None:
        """require_pipe raises PipeError when adapter is not loaded."""
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        with pytest.raises(PipeError) as exc_info:
            require_pipe({"eid": "1"}, state, 1)
        assert "error" in exc_info.value.response

    def test_raises_pipe_error_invalid_eid(self) -> None:
        """require_pipe raises PipeError when eid is out of range."""
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        ctrl = SimpleNamespace(
            SetFrameEvent=lambda eid, force: None,
            GetPipelineState=lambda: SimpleNamespace(),
        )
        from rdc.adapter import RenderDocAdapter

        state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
        state.max_eid = 10
        with pytest.raises(PipeError) as exc_info:
            require_pipe({"eid": "999"}, state, 1)
        resp = exc_info.value.response
        assert "error" in resp
        assert "out of range" in resp["error"]["message"]

    def test_success(self) -> None:
        """require_pipe returns (eid, pipe) on success."""
        state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
        mock_pipe = MagicMock()
        ctrl = SimpleNamespace(
            SetFrameEvent=lambda eid, force: None,
            GetPipelineState=lambda: mock_pipe,
        )
        from rdc.adapter import RenderDocAdapter

        state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
        state.max_eid = 100
        eid, pipe = require_pipe({"eid": "5"}, state, 1)
        assert eid == 5
        assert pipe is mock_pipe
