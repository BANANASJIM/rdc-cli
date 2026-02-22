# Feature: phase3c-ci-assertions

## Summary

Four new CLI assertion commands for CI pipelines: `assert-pixel`, `assert-clean`,
`assert-count`, and `assert-state`. All are pure CLI-side compositions of existing
JSON-RPC methods (`pixel_history`, `log`, `count`, `pipeline`). No new daemon
handlers are required. Each command exits 0 on pass, 1 on fail, and 2 on error
(communication failure or missing session), following the convention established by
`assert-image`.

A new `_assert_call` helper wraps JSON-RPC communication with exit-code 2 semantics
(distinct from `_helpers.call` which uses exit 1 for all errors). All four commands
live in a single module `assert_ci.py` to keep the assertion surface cohesive.

## Problem

CI scripts testing GPU rendering correctness currently lack ergonomic assertion
primitives. Teams must write ad-hoc Python or shell scripts to:

1. Verify a specific pixel has the expected RGBA value after rendering.
2. Confirm the capture log is free of high-severity warnings.
3. Assert that draw/dispatch/resource counts match expectations.
4. Check that pipeline state (blend enable, topology, depth write) matches expected
   values at a specific event.

These ad-hoc scripts are fragile, inconsistent in exit codes, and duplicate logic
already available through `rdc`'s daemon. The four assertion commands provide a
stable, scriptable interface with deterministic exit codes.

## Design References

- `设计/命令总览.md` -- assert-pixel, assert-clean, assert-count, assert-state
  are Phase 3C
- `设计/设计原则.md` -- exit code semantics: 0=pass, 1=fail, 2=error
- `规划/Roadmap.md` -- Phase 3C: CI Assertion

## Design

### Shared helper: `_assert_call`

All four commands share an `_assert_call()` function that wraps `load_session` +
`send_request` but uses exit code 2 (error) instead of 1 for session/RPC failures,
reserving exit 1 for assertion failures. This is distinct from `_helpers.call()`
(exit 1 on error) and `_daemon_call()` in `info.py` (also exit 1).

```python
def _assert_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """JSON-RPC call with exit(2) on any error."""
    session = load_session()
    if session is None:
        click.echo("error: no active session", err=True)
        sys.exit(2)
    payload = _request(method, 1, {"_token": session.token, **(params or {})}).to_dict()
    try:
        resp = send_request(session.host, session.port, payload)
    except Exception as exc:
        click.echo(f"error: daemon unreachable: {exc}", err=True)
        sys.exit(2)
    if "error" in resp:
        click.echo(f"error: {resp['error']['message']}", err=True)
        sys.exit(2)
    return resp["result"]
```

### Command 1: `rdc assert-pixel`

```
rdc assert-pixel <eid> <x> <y> --expect "R G B A" [--tolerance 0.01] [--target 0] [--json]
```

Composes `pixel_history` JSON-RPC method. Finds the last modification at the given
(x, y) where `passed == True`, extracts `post_mod` RGBA values, and compares each
channel against `--expect` within `--tolerance`.

Algorithm:
1. Parse `--expect` into 4 floats (space-separated string).
2. Call `pixel_history` with `{"eid": eid, "x": x, "y": y, "target": target}`.
3. From `result["modifications"]`, find the last entry where `passed == True`.
4. If no passing modification exists, exit 2 ("error: no passing modification found").
5. Extract `post_mod` RGBA: `(post_mod["r"], post_mod["g"], post_mod["b"], post_mod["a"])`.
6. Compare each channel: `|actual - expected| <= tolerance`.
7. If all channels match, exit 0. Otherwise exit 1 with mismatch details.

The `pixel_history` response format:
```json
{"modifications": [{"eid": int, "passed": bool, "post_mod": {"r": f, "g": f, "b": f, "a": f}, ...}]}
```

Text output:
- Pass: `pass: pixel (512, 384) = 0.5000 0.3000 0.1000 1.0000`
- Fail: `fail: pixel (512, 384) expected 0.5000 0.3000 0.1000 1.0000, got 0.6000 0.3000 0.1000 1.0000`

JSON output:
```json
{
  "pass": true,
  "expected": [0.5, 0.3, 0.1, 1.0],
  "actual": [0.5, 0.3, 0.1, 1.0],
  "tolerance": 0.01,
  "eid": 120,
  "x": 512,
  "y": 384
}
```

### Command 2: `rdc assert-clean`

```
rdc assert-clean [--min-severity HIGH] [--json]
```

Composes `log` JSON-RPC method. Asserts that the capture has no debug/validation
messages at or above the given severity threshold.

Severity rank map (lower rank = higher severity):
`HIGH=0, MEDIUM=1, LOW=2, INFO=3, UNKNOWN=4`.

Algorithm:
1. Call `log` with no extra params.
2. Assign rank to each message's `level` via the severity map.
3. Filter `result["messages"]` where `rank(level) <= rank(min_severity)`.
4. Exit 0 if no messages remain, exit 1 if any remain.

`--min-severity` default: `HIGH` (only HIGH messages cause failure).

The `log` response format:
```json
{"messages": [{"level": "HIGH", "eid": int, "message": str}]}
```

Text output:
- Pass: `pass: no messages at severity >= HIGH`
- Fail: `fail: 3 message(s) at severity >= HIGH` followed by each message on stderr.

JSON output:
```json
{
  "pass": true,
  "min_severity": "HIGH",
  "count": 0,
  "messages": []
}
```

### Command 3: `rdc assert-count`

```
rdc assert-count <what> --expect N [--op eq|gt|lt|ge|le] [--pass PASS] [--json]
```

Composes `count` JSON-RPC method. Asserts that a capture metric satisfies a numeric
comparison.

`what` choices: `draws`, `events`, `resources`, `triangles`, `passes`, `dispatches`,
`clears`. These match the existing `rdc count` command's targets.

`--op` defaults to `eq`. `--pass` filters by render pass name (forwarded to the
daemon's `pass` parameter).

Algorithm:
1. Call `count` with `{"what": what}`, optionally adding `"pass": PASS`.
2. Extract `result["value"]`.
3. Apply operator: `actual <op> expected`.
4. Exit 0 if true, exit 1 if false.

The `count` response format:
```json
{"value": int}
```

Text output:
- Pass: `pass: draws = 42 (expected eq 42)`
- Fail: `fail: draws = 38 (expected eq 42)`

JSON output:
```json
{
  "pass": true,
  "what": "draws",
  "actual": 42,
  "expected": 42,
  "op": "eq"
}
```

### Command 4: `rdc assert-state`

```
rdc assert-state <eid> <key-path> --expect <value> [--json]
```

Composes `pipeline` JSON-RPC method with a `section` parameter. Inspects a specific
pipeline state value at a given EID and asserts its equality to `--expect`.

Key-path format: `section.field[.subfield[.index[...]]]`.
Examples:
- `blend.blends.0.enabled` -- section=`blend`, path=`["blends","0","enabled"]`
- `topology.topology` -- section=`topology`, path=`["topology"]`
- `depth-stencil.depthEnable` -- section=`depth-stencil`, path=`["depthEnable"]`

Valid sections: `topology`, `viewport`, `scissor`, `blend`, `stencil`,
`rasterizer`, `depth-stencil`, `msaa`, `vbuffers`, `ibuffer`, `samplers`,
`push-constants`, `vinputs`, `vs`, `hs`, `ds`, `gs`, `ps`, `cs`.

Key-path parsing for hyphenated sections:

```python
_HYPHENATED_SECTIONS = {"depth-stencil", "push-constants"}

def _parse_key_path(key_path: str) -> tuple[str, list[str]]:
    for hs in _HYPHENATED_SECTIONS:
        if key_path == hs or key_path.startswith(hs + "."):
            rest = key_path[len(hs) + 1:] if len(key_path) > len(hs) else ""
            return hs, rest.split(".") if rest else []
    parts = key_path.split(".")
    return parts[0], parts[1:]
```

Path traversal:

```python
def _traverse_path(data: Any, path: list[str]) -> Any:
    for seg in path:
        if isinstance(data, list):
            try:
                data = data[int(seg)]
            except (ValueError, IndexError):
                click.echo(f"error: invalid path segment '{seg}'", err=True)
                sys.exit(2)
        elif isinstance(data, dict):
            if seg not in data:
                click.echo(f"error: key '{seg}' not found", err=True)
                sys.exit(2)
            data = data[seg]
        else:
            click.echo(f"error: cannot traverse into {type(data).__name__}", err=True)
            sys.exit(2)
    return data
```

Value normalization for comparison:

```python
def _normalize_value(v: Any) -> str:
    if isinstance(v, bool):
        return str(v).lower()
    return str(v)
```

Comparison is case-insensitive for boolean-like values (`true`/`false`/`True`/`False`),
exact string comparison otherwise.

Algorithm:
1. Parse key-path: split into `(section, field_path)`.
2. Validate section is in the known set; exit 2 if invalid.
3. Call `pipeline` with `{"eid": eid, "section": section}`.
4. Traverse the result using `_traverse_path(result, field_path)`.
5. Compare `_normalize_value(actual)` against `_normalize_value(expected_str)`.
   For expected values that look boolean (`true`/`false` case-insensitive), normalize
   both sides to lowercase.
6. Exit 0 if equal, exit 1 if not equal.

Text output:
- Pass: `pass: blend.blends.0.enabled = true`
- Fail: `fail: blend.blends.0.enabled = false (expected true)`

JSON output:
```json
{
  "pass": true,
  "eid": 120,
  "key_path": "blend.blends.0.enabled",
  "expected": "true",
  "actual": "true"
}
```

## Changes

### New files

| File | Description |
|------|-------------|
| `src/rdc/commands/assert_ci.py` | `_assert_call` + `_parse_key_path` + `_traverse_path` + `_normalize_value` + 4 Click commands |
| `tests/unit/test_assert_ci_commands.py` | ~45 unit tests |

### Modified files

| File | Change |
|------|--------|
| `src/rdc/cli.py` | Import + register 4 commands |
| `tests/integration/test_daemon_handlers_real.py` | GPU integration tests for assert commands |

## Scope

| Component | Lines |
|-----------|-------|
| `src/rdc/commands/assert_ci.py` | ~200 |
| `src/rdc/cli.py` (registration) | ~6 |
| `tests/unit/test_assert_ci_commands.py` | ~450 |
| GPU integration tests | ~60 |
| **Total** | **~716** |

### In scope

- Four assert commands with exit code semantics (0/1/2)
- `--json` flag on all four commands
- `_assert_call` shared helper with exit code 2 for errors
- `_parse_key_path` for hyphenated section support in `assert-state`
- `_traverse_path` for nested dict/list navigation in `assert-state`
- `_normalize_value` for boolean/numeric comparison normalization
- Unit tests (~45 cases) with monkeypatched `_assert_call`
- GPU integration tests in existing `test_daemon_handlers_real.py`

### Out of scope

- New daemon JSON-RPC methods (all commands compose existing methods)
- Regex or pattern matching in `assert-state` value comparison
- `assert-image` (already implemented in Phase 3A)
- CI pipeline YAML templates (user documentation, not in codebase)
- Tolerance modes beyond per-channel absolute in `assert-pixel`
- MSAA sample parameter for `assert-pixel` (can be added later)
