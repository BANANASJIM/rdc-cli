# Proposal: phase3a-script

## Summary

Add `rdc script <file.py>` — an escape-hatch command that executes an arbitrary
Python script inside the daemon process via `exec()`, with full access to the
live `renderdoc` module and `ReplayController`. stdout/stderr are captured and
returned over JSON-RPC.

## Motivation

The existing 62 JSON-RPC methods cover the most common RenderDoc queries, but
cannot enumerate every possible data shape an agent or power user might need.
When the structured commands fall short, the only alternative today is to
`rdc open` a capture in the RenderDoc GUI — a non-scriptable dead end.

`rdc script` closes this gap. Any valid `renderdoc` Python API call can be issued
from a one-off `.py` file, results read back through standard output. The agent
debug loop becomes: write a ten-line probe script → `rdc script probe.py` →
parse JSON response → done.

This is explicitly rated **Tier 1 Must-Have** in the Phase 3 agent-debug
analysis (`调研-Agent功能优先级分析.md`).

## Design

### Handler: `src/rdc/handlers/script.py`

Follows the standard HANDLERS-dict pattern used by all Phase 2 handler modules:

```python
HANDLERS: dict[str, Any] = {
    "script": _handle_script,
}
```

Registered in `daemon_server.py` by importing and merging into `_DISPATCH`.

### Execution model

```python
def _handle_script(request_id, params, state):
    path = Path(params["path"])
    # 1. Validate: path.exists(), path.is_file(), state.adapter is not None
    # 2. Read source: path.read_text("utf-8")
    # 3. Build globals namespace
    # 4. Redirect stdout/stderr → contextlib.redirect_stdout/redirect_stderr + StringIO
    # 5. Record start time
    # 6. exec(source, script_globals)
    # 7. Extract result variable if present
    # 8. Return {stdout, stderr, elapsed_ms, return_value}
```

### Script namespace

| Variable     | Type                  | Description                              |
|--------------|-----------------------|------------------------------------------|
| `controller` | SWIG `ReplayController` | Full RenderDoc replay API              |
| `rd`         | module                | `renderdoc` module (for constructing types) |
| `adapter`    | `RenderDocAdapter`    | Compatibility wrapper                    |
| `state`      | `DaemonState`         | All caches, temp dir, resource maps      |
| `args`       | `dict[str, str]`      | Key=value pairs from CLI `--arg`         |

### Error handling

SyntaxError is caught before `exec()` to produce a clear line-number message.
`BaseException` (not `Exception`) guards the `exec()` call to catch
`SystemExit` and `KeyboardInterrupt` that would otherwise terminate the daemon:

```python
try:
    compile(source, str(path), "exec")
except SyntaxError as exc:
    return _error_response(request_id, -32002,
        f"syntax error: {exc.msg} at line {exc.lineno}")
try:
    exec(code, script_globals)  # noqa: S102
except BaseException as exc:  # noqa: BLE001
    return _error_response(request_id, -32002,
        f"script error: {type(exc).__name__}: {exc}")
```

### `result` variable extraction

If the script assigns `result = <value>`, the handler tries to JSON-serialize it.
Non-serializable objects are coerced to `str()`:

```python
raw = script_globals.get("result")
try:
    json.dumps(raw)
    return_value = raw
except (TypeError, ValueError):
    return_value = str(raw)
```

If `result` is not assigned, `return_value` is `null`.

### JSON-RPC interface

**Method:** `"script"`

**Params:**
```json
{
    "_token": "<token>",
    "path": "/absolute/path/to/script.py",
    "args": {"key": "value"}
}
```
`args` is optional; defaults to `{}`.

**Success response:**
```json
{
    "result": {
        "stdout": "hello\n",
        "stderr": "",
        "elapsed_ms": 42,
        "return_value": {"count": 3}
    }
}
```

**Error responses:**

| Scenario           | Code    | Message                                    |
|--------------------|---------|--------------------------------------------|
| No replay loaded   | -32002  | `"no replay loaded"`                       |
| File not found     | -32002  | `"script not found: <path>"`               |
| Path is a directory| -32002  | `"script path is a directory"`             |
| SyntaxError        | -32002  | `"syntax error: <msg> at line <n>"`        |
| Runtime exception  | -32002  | `"script error: <Type>: <msg>"`            |

### CLI command: `src/rdc/commands/script.py`

```
rdc script <file.py> [--arg KEY=VALUE ...] [--json]
```

- `file.py`: `click.Path(exists=True, dir_okay=False, path_type=Path)` — Click
  validates existence; path is made absolute before sending to daemon.
- `--arg KEY=VALUE`: multiple option, parsed into `dict[str, str]`. Invalid
  format (missing `=`) → error to stderr, exit 2.
- `--json`: emit the raw JSON-RPC response object instead of formatted output.

**Default output:**
- `stdout` content printed to stdout (as-is, no extra newline if already present)
- `stderr` content printed to stderr
- Elapsed time printed to stderr: `# elapsed: 42 ms`
- If `return_value` is not null, printed to stderr: `# result: <value>`

### Security

Design doc mandate: **no sandbox**. This is a local developer tool, not a
multi-user server. Token auth on the daemon socket prevents unauthorized
invocation. The script runs with the daemon's full OS privileges.

Documented behavior:
- Only local file paths accepted (`Path.is_file()` validated).
- Daemon crash due to script = user's responsibility; recover with
  `rdc close && rdc open`.
- No path traversal protection needed (user trusts their own filesystem).

## Scope

| Component                                  | Lines |
|--------------------------------------------|-------|
| `src/rdc/handlers/script.py`               | ~80   |
| `src/rdc/commands/script.py`               | ~45   |
| `daemon_server.py` + `cli.py` registration | ~4    |
| Unit tests (handler + CLI)                 | ~120  |
| GPU integration test                       | ~30   |
| **Total**                                  | **~280** |

No VFS route: `rdc script` is a one-shot execution command, not a data
node — it does not belong in the VFS namespace.
