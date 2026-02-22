"""Tests for daemon debug_pixel and debug_vertex handlers."""

from __future__ import annotations

import sys
from pathlib import Path

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as rd  # noqa: E402


def _make_var(
    name: str = "x",
    var_type: str = "float",
    rows: int = 1,
    columns: int = 4,
    f32v: list[float] | None = None,
    u32v: list[int] | None = None,
    s32v: list[int] | None = None,
) -> rd.ShaderVariable:
    val = rd.ShaderValue(
        f32v=(f32v or [0.0] * 16),
        u32v=(u32v or [0] * 16),
        s32v=(s32v or [0] * 16),
    )
    return rd.ShaderVariable(name=name, type=var_type, rows=rows, columns=columns, value=val)


def _make_change(
    name: str = "x",
    var_type: str = "float",
    before_f32: list[float] | None = None,
    after_f32: list[float] | None = None,
) -> rd.ShaderVariableChange:
    return rd.ShaderVariableChange(
        before=_make_var(name, var_type, f32v=before_f32),
        after=_make_var(name, var_type, f32v=after_f32),
    )


def _make_debug_state(
    step: int = 0,
    inst: int = 0,
    changes: list[rd.ShaderVariableChange] | None = None,
) -> rd.ShaderDebugState:
    return rd.ShaderDebugState(
        stepIndex=step,
        nextInstruction=inst,
        changes=changes or [],
    )


def _make_trace(
    debugger: object | None = None,
    stage: rd.ShaderStage = rd.ShaderStage.Pixel,
    inst_info: list[rd.InstructionSourceInfo] | None = None,
    source_files: list[rd.SourceFile] | None = None,
) -> rd.ShaderDebugTrace:
    return rd.ShaderDebugTrace(
        debugger=debugger,
        stage=stage,
        instInfo=inst_info or [],
        sourceFiles=source_files or [],
    )


def _make_state(
    ctrl: rd.MockReplayController | None = None,
) -> DaemonState:
    if ctrl is None:
        ctrl = rd.MockReplayController()
    ctrl._actions = [
        rd.ActionDescription(eventId=100, flags=rd.ActionFlags.Drawcall, _name="vkCmdDraw"),
    ]
    state = DaemonState(capture="test.rdc", current_eid=100, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.max_eid = 100
    state.rd = rd
    return state


def _req(method: str, params: dict | None = None) -> dict:
    p = {"_token": "tok"}
    if params:
        p.update(params)
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": p}


# ---------------------------------------------------------------------------
# debug_pixel happy path
# ---------------------------------------------------------------------------


def test_debug_pixel_happy_path() -> None:
    """3-step trace returns correct structure."""
    ctrl = rd.MockReplayController()
    debugger = object()
    change0 = _make_change("fragCoord", "float", [0.0] * 16, [320.0, 240.0, 0.5, 1.0] + [0.0] * 12)
    change2 = _make_change("outColor", "float", [0.0] * 16, [1.0, 0.0, 0.0, 1.0] + [0.0] * 12)

    states = [
        _make_debug_state(step=0, inst=0, changes=[change0]),
        _make_debug_state(step=1, inst=1),
        _make_debug_state(step=2, inst=2, changes=[change2]),
    ]

    trace = _make_trace(debugger=debugger, stage=rd.ShaderStage.Pixel)
    ctrl._debug_pixel_map[(320, 240)] = trace
    ctrl._debug_states[id(debugger)] = [states]

    state = _make_state(ctrl)
    resp, running = _handle_request(_req("debug_pixel", {"eid": 100, "x": 320, "y": 240}), state)

    assert running
    r = resp["result"]
    assert r["eid"] == 100
    assert r["stage"] == "ps"
    assert r["total_steps"] == 3
    assert len(r["trace"]) == 3
    assert r["trace"][0]["step"] == 0
    assert r["trace"][0]["changes"][0]["name"] == "fragCoord"
    assert r["trace"][0]["changes"][0]["after"][:4] == [320.0, 240.0, 0.5, 1.0]
    # inputs = first step changes, outputs = last step changes
    assert len(r["inputs"]) == 1
    assert r["inputs"][0]["name"] == "fragCoord"
    assert len(r["outputs"]) == 1
    assert r["outputs"][0]["name"] == "outColor"


def test_debug_pixel_missing_eid() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("debug_pixel", {"x": 0, "y": 0}), state)
    assert resp["error"]["code"] == -32602
    assert "eid" in resp["error"]["message"]


def test_debug_pixel_missing_x() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("debug_pixel", {"eid": 100, "y": 0}), state)
    assert resp["error"]["code"] == -32602
    assert "x" in resp["error"]["message"]


def test_debug_pixel_missing_y() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("debug_pixel", {"eid": 100, "x": 0}), state)
    assert resp["error"]["code"] == -32602
    assert "y" in resp["error"]["message"]


def test_debug_pixel_no_fragment() -> None:
    """Empty trace (no debugger) returns -32007."""
    state = _make_state()
    resp, running = _handle_request(_req("debug_pixel", {"eid": 100, "x": 0, "y": 0}), state)
    assert running
    assert resp["error"]["code"] == -32007
    assert "no fragment" in resp["error"]["message"]


def test_debug_pixel_no_adapter() -> None:
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("debug_pixel", {"eid": 100, "x": 0, "y": 0}), state)
    assert resp["error"]["code"] == -32002


def test_debug_pixel_eid_out_of_range() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("debug_pixel", {"eid": 9999, "x": 0, "y": 0}), state)
    assert resp["error"]["code"] == -32002


def test_debug_pixel_multiple_batches() -> None:
    """ContinueDebug returning multiple batches accumulates all steps."""
    ctrl = rd.MockReplayController()
    debugger = object()
    batch1 = [_make_debug_state(step=0, inst=0), _make_debug_state(step=1, inst=1)]
    batch2 = [_make_debug_state(step=2, inst=2)]

    trace = _make_trace(debugger=debugger)
    ctrl._debug_pixel_map[(10, 20)] = trace
    ctrl._debug_states[id(debugger)] = [batch1, batch2]

    state = _make_state(ctrl)
    resp, _ = _handle_request(_req("debug_pixel", {"eid": 100, "x": 10, "y": 20}), state)
    r = resp["result"]
    assert r["total_steps"] == 3


def test_debug_pixel_source_mapping() -> None:
    """Steps with instInfo and sourceFiles populate file/line."""
    ctrl = rd.MockReplayController()
    debugger = object()

    inst_info = [
        rd.InstructionSourceInfo(
            instruction=0,
            lineInfo=rd.LineColumnInfo(fileIndex=0, lineStart=42),
        ),
    ]
    source_files = [rd.SourceFile(filename="shader.frag", contents="void main() {}")]

    trace = _make_trace(
        debugger=debugger,
        inst_info=inst_info,
        source_files=source_files,
    )
    ctrl._debug_pixel_map[(5, 5)] = trace
    ctrl._debug_states[id(debugger)] = [[_make_debug_state(step=0, inst=0)]]

    state = _make_state(ctrl)
    resp, _ = _handle_request(_req("debug_pixel", {"eid": 100, "x": 5, "y": 5}), state)
    step = resp["result"]["trace"][0]
    assert step["file"] == "shader.frag"
    assert step["line"] == 42


def test_debug_pixel_sample_param() -> None:
    """sample param is forwarded to DebugPixelInputs."""
    ctrl = rd.MockReplayController()
    debugger = object()
    trace = _make_trace(debugger=debugger)
    ctrl._debug_pixel_map[(0, 0)] = trace
    ctrl._debug_states[id(debugger)] = [[_make_debug_state()]]

    state = _make_state(ctrl)
    resp, _ = _handle_request(_req("debug_pixel", {"eid": 100, "x": 0, "y": 0, "sample": 2}), state)
    assert "result" in resp


# ---------------------------------------------------------------------------
# debug_vertex
# ---------------------------------------------------------------------------


def test_debug_vertex_happy_path() -> None:
    """Vertex debug returns VS trace."""
    ctrl = rd.MockReplayController()
    debugger = object()
    change = _make_change("position", "float", [0.0] * 16, [1.0, 2.0, 3.0, 1.0] + [0.0] * 12)

    trace = _make_trace(debugger=debugger, stage=rd.ShaderStage.Vertex)
    ctrl._debug_vertex_map[0] = trace
    ctrl._debug_states[id(debugger)] = [
        [
            _make_debug_state(step=0, inst=0, changes=[change]),
        ]
    ]

    state = _make_state(ctrl)
    resp, running = _handle_request(_req("debug_vertex", {"eid": 100, "vtx_id": 0}), state)
    assert running
    r = resp["result"]
    assert r["stage"] == "vs"
    assert r["total_steps"] == 1
    assert r["trace"][0]["changes"][0]["name"] == "position"


def test_debug_vertex_missing_eid() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("debug_vertex", {"vtx_id": 0}), state)
    assert resp["error"]["code"] == -32602
    assert "eid" in resp["error"]["message"]


def test_debug_vertex_missing_vtx_id() -> None:
    state = _make_state()
    resp, _ = _handle_request(_req("debug_vertex", {"eid": 100}), state)
    assert resp["error"]["code"] == -32602
    assert "vtx_id" in resp["error"]["message"]


def test_debug_vertex_no_adapter() -> None:
    state = DaemonState(capture="test.rdc", current_eid=0, token="tok")
    resp, _ = _handle_request(_req("debug_vertex", {"eid": 100, "vtx_id": 0}), state)
    assert resp["error"]["code"] == -32002


def test_debug_vertex_no_trace() -> None:
    """Vertex not available returns -32007."""
    state = _make_state()
    resp, _ = _handle_request(_req("debug_vertex", {"eid": 100, "vtx_id": 99}), state)
    assert resp["error"]["code"] == -32007


def test_debug_vertex_instance_forwarded() -> None:
    """instance/idx/view params are accepted without error."""
    ctrl = rd.MockReplayController()
    debugger = object()
    trace = _make_trace(debugger=debugger, stage=rd.ShaderStage.Vertex)
    ctrl._debug_vertex_map[0] = trace
    ctrl._debug_states[id(debugger)] = [[_make_debug_state()]]

    state = _make_state(ctrl)
    resp, _ = _handle_request(
        _req("debug_vertex", {"eid": 100, "vtx_id": 0, "instance": 1, "idx": 2, "view": 3}),
        state,
    )
    assert "result" in resp
    assert resp["result"]["total_steps"] == 1


# ---------------------------------------------------------------------------
# Variable formatting
# ---------------------------------------------------------------------------


def test_format_var_value_float_vec4() -> None:
    """Float vec4 extracts 4 values from f32v."""
    from rdc.handlers.debug import _format_var_value

    var = _make_var("v", "float", rows=1, columns=4, f32v=[1.0, 2.0, 3.0, 4.0] + [0.0] * 12)
    result = _format_var_value(var)
    assert result == [1.0, 2.0, 3.0, 4.0]


def test_format_var_value_uint_scalar() -> None:
    """Uint scalar extracts 1 value from u32v."""
    from rdc.handlers.debug import _format_var_value

    var = _make_var("u", "uint", rows=1, columns=1, u32v=[42] + [0] * 15)
    result = _format_var_value(var)
    assert result == [42]


def test_format_var_value_sint() -> None:
    """Signed int scalar extracts from s32v."""
    from rdc.handlers.debug import _format_var_value

    var = _make_var("i", "sint", rows=1, columns=1, s32v=[-7] + [0] * 15)
    result = _format_var_value(var)
    assert result == [-7]


def test_format_var_value_none() -> None:
    """None value returns zeros."""
    from rdc.handlers.debug import _format_var_value

    var = rd.ShaderVariable(name="n", type="float", rows=1, columns=2, value=None)
    result = _format_var_value(var)
    assert result == [0.0, 0.0]


# ---------------------------------------------------------------------------
# FreeTrace called even on error
# ---------------------------------------------------------------------------


def test_free_trace_called_on_exception() -> None:
    """FreeTrace is called even if ContinueDebug raises."""
    ctrl = rd.MockReplayController()
    debugger = object()
    trace = _make_trace(debugger=debugger)
    ctrl._debug_pixel_map[(0, 0)] = trace

    free_calls: list[object] = []
    original_free = ctrl.FreeTrace

    def tracking_free(t: object) -> None:
        free_calls.append(t)
        original_free(t)

    ctrl.FreeTrace = tracking_free  # type: ignore[assignment]

    def exploding_continue(dbg: object) -> list:
        raise RuntimeError("boom")

    ctrl.ContinueDebug = exploding_continue  # type: ignore[assignment]

    state = _make_state(ctrl)
    # The handler will catch the exception in _run_debug_loop's finally block
    # but the outer handler may propagate it; either way FreeTrace must be called
    try:
        _handle_request(_req("debug_pixel", {"eid": 100, "x": 0, "y": 0}), state)
    except RuntimeError:
        pass
    assert len(free_calls) == 1


def test_free_trace_called_on_success() -> None:
    """FreeTrace is called after successful debug loop."""
    ctrl = rd.MockReplayController()
    debugger = object()
    trace = _make_trace(debugger=debugger)
    ctrl._debug_pixel_map[(1, 1)] = trace
    ctrl._debug_states[id(debugger)] = [[_make_debug_state()]]

    free_calls: list[object] = []

    def tracking_free(t: object) -> None:
        free_calls.append(t)

    ctrl.FreeTrace = tracking_free  # type: ignore[assignment]

    state = _make_state(ctrl)
    resp, _ = _handle_request(_req("debug_pixel", {"eid": 100, "x": 1, "y": 1}), state)
    assert "result" in resp
    assert len(free_calls) == 1
