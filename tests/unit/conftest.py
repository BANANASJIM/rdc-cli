"""Shared helpers for unit tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState


def rpc_request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    token: str = "tok",
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 request dict for daemon handler tests."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {"_token": token, **(params or {})},
    }


def make_daemon_state(
    *,
    capture: str = "test.rdc",
    current_eid: int = 0,
    token: str = "tok",
    ctrl: Any | None = None,
    version: tuple[int, int] = (1, 41),
    api_name: str = "Vulkan",
    max_eid: int = 100,
    structured_file: Any | None = None,
    rd: Any | None = None,
    tmp_path: Path | None = None,
    pipe_state: Any | None = None,
    actions: list[Any] | None = None,
    is_remote: bool = False,
    **kwargs: Any,
) -> DaemonState:
    """Build a DaemonState for daemon handler tests.

    Args:
        capture: Capture filename.
        current_eid: Current event ID.
        token: Auth token.
        ctrl: Replay controller (SimpleNamespace or MockReplayController).
            If None, a minimal SimpleNamespace controller is created.
        version: RenderDoc version tuple for the adapter.
        api_name: Graphics API name.
        max_eid: Maximum event ID.
        structured_file: Structured file object. Defaults to empty SimpleNamespace.
        rd: Mock renderdoc module.
        tmp_path: Temp directory path.
        pipe_state: Pipeline state for the controller's GetPipelineState.
        actions: Action list for the controller's GetRootActions.
        is_remote: Whether this is a remote-mode state.
        **kwargs: Additional DaemonState attributes to set directly.
    """
    if ctrl is None:
        sf = structured_file or SimpleNamespace(chunks=[])
        ctrl = SimpleNamespace(
            GetRootActions=lambda: actions or [],
            GetResources=lambda: [],
            GetAPIProperties=lambda: SimpleNamespace(pipelineType=api_name),
            GetPipelineState=lambda: pipe_state or SimpleNamespace(),
            SetFrameEvent=lambda eid, force: None,
            GetStructuredFile=lambda: sf,
            GetDebugMessages=lambda: [],
            Shutdown=lambda: None,
        )

    state = DaemonState(capture=capture, current_eid=current_eid, token=token)
    state.adapter = RenderDocAdapter(controller=ctrl, version=version)
    state.api_name = api_name
    state.max_eid = max_eid
    if structured_file is not None:
        state.structured_file = structured_file
    if rd is not None:
        state.rd = rd
    if tmp_path is not None:
        state.temp_dir = tmp_path
    state.is_remote = is_remote
    for key, val in kwargs.items():
        setattr(state, key, val)
    return state


def patch_cli_session(
    monkeypatch: pytest.MonkeyPatch,
    response: dict[str, Any] | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 1,
    token: str = "tok",
) -> None:
    """Patch load_session and send_request for CLI command tests.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        response: Dict to wrap as ``{"result": response}`` and return from
            ``send_request``.  Pass ``None`` to simulate "no active session".
        host: Fake session host.
        port: Fake session port.
        token: Fake session token.
    """
    import rdc.commands._helpers as mod

    if response is None:
        monkeypatch.setattr(mod, "load_session", lambda: None)
        return

    session = type("S", (), {"host": host, "port": port, "token": token})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload, **_kw: {"result": response})


def assert_json_output(result: Any) -> dict[str, Any]:
    """Assert CLI result succeeded with valid JSON and return parsed dict.

    Args:
        result: ``click.testing.Result`` from ``CliRunner().invoke()``.

    Returns:
        Parsed JSON dict.
    """
    assert result.exit_code == 0
    data: dict[str, Any] = json.loads(result.output)
    return data


def assert_jsonl_output(
    result: Any,
    expected_count: int | None = None,
) -> list[dict[str, Any]]:
    """Assert CLI result succeeded with valid JSONL and return parsed list.

    Args:
        result: ``click.testing.Result`` from ``CliRunner().invoke()``.
        expected_count: If given, assert the number of JSONL lines matches.

    Returns:
        List of parsed JSON dicts, one per line.
    """
    assert result.exit_code == 0
    lines = [json.loads(ln) for ln in result.output.strip().splitlines()]
    if expected_count is not None:
        assert len(lines) == expected_count
    return lines
