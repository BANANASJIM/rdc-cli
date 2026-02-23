"""Script execution handler: run arbitrary Python inside the daemon."""

from __future__ import annotations

import contextlib
import io
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import _error_response, _result_response
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _handle_script(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    """Execute a Python script with access to the live replay controller.

    Args:
        request_id: JSON-RPC request ID.
        params: Must contain "path"; optionally "args".
        state: Current daemon state.

    Returns:
        Tuple of (response_dict, keep_running).
    """
    if "path" not in params:
        return _error_response(request_id, -32602, "missing required param: path"), True

    path = Path(params["path"])
    if not path.exists():
        return _error_response(request_id, -32002, f"script not found: {path}"), True
    if not path.is_file():
        return _error_response(request_id, -32002, "script path is a directory"), True

    assert state.adapter is not None
    source = path.read_text("utf-8")

    try:
        code = compile(source, str(path), "exec")
    except SyntaxError as exc:
        return _error_response(
            request_id, -32002, f"syntax error: {exc.msg} at line {exc.lineno}"
        ), True

    script_globals: dict[str, Any] = {
        "controller": state.adapter.controller,
        "rd": state.rd,
        "adapter": state.adapter,
        "state": state,
        "args": params.get("args", {}),
    }

    out, err = io.StringIO(), io.StringIO()
    t0 = time.perf_counter()

    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            exec(code, script_globals)  # noqa: S102
    except BaseException as exc:  # noqa: BLE001
        return _error_response(
            request_id, -32002, f"script error: {type(exc).__name__}: {exc}"
        ), True

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    raw = script_globals.get("result")
    try:
        json.dumps(raw)
        return_value = raw
    except (TypeError, ValueError):
        return_value = str(raw)

    return _result_response(
        request_id,
        {
            "stdout": out.getvalue(),
            "stderr": err.getvalue(),
            "elapsed_ms": elapsed_ms,
            "return_value": return_value,
        },
    ), True


HANDLERS: dict[str, Handler] = {
    "script": _handle_script,
}
