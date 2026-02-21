# Test Plan: phase2.6-output-quality

## Scope

**In scope:**
- Unit tests for `_enum_name` and `_sanitize_size` helpers
- Handler integration tests for enum name rendering
- Handler integration tests for UINT_MAX sanitization
- Client timeout default value verification

**Out of scope:**
- GPU integration tests (no behavior change, only display format)
- CLI command tests (handlers called via existing commands unchanged)

## Test Matrix

| Layer | File | Cases |
|---|---|---|
| Unit | `test_daemon_output_quality.py` | helpers, handlers, client |

## Cases

### Helper: `_enum_name`
- enum-like object with `.name` attr → returns `.name` string
- plain string → returns unchanged
- plain int → returns unchanged
- empty string → returns unchanged
- None → returns None

### Helper: `_sanitize_size`
- normal int (4096) → returns 4096
- zero → returns 0
- `(1<<64)-1` (UINT_MAX) → returns `"-"`
- `(1<<64)-2` (just below) → returns value unchanged

### Client timeout
- `inspect.signature(send_request).parameters["timeout"].default == 30.0`

### `pipe_topology` handler
- topology field is plain name string (no dots, no angle brackets)

### `pipe_blend` handler
- blend factor fields (`srcColor`, `dstColor`, `colorOp`, `srcAlpha`, `dstAlpha`, `alphaOp`) are plain names

### `pipe_stencil` handler
- stencil op fields (`failOperation`, `depthFailOperation`, `passOperation`, `function`) are plain names

### `pipe_samplers` handler
- sampler fields (`addressU`, `addressV`, `addressW`, `filter`) are plain names

### `pipe_vbuffers` handler
- UINT_MAX `byteSize` → `"-"`
- Normal `byteSize` → integer

### `pipe_ibuffer` handler
- UINT_MAX `byteSize` → `"-"`
- Normal `byteSize` → integer

## Assertions

- All enum name fields: `assert "." not in str(field_value)` and `isinstance(field_value, str)`
- Sentinel: `assert resp["result"]["byteSize"] == "-"`
- Normal size: `assert resp["result"]["byteSize"] == <int>`
- Timeout: `assert sig.parameters["timeout"].default == 30.0`

## Risks & Rollback

- Low risk: helpers are pure functions with no side effects
- Rollback: revert `_enum_name`/`_sanitize_size` calls, restore `timeout=2.0`
