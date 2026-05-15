# Test Plan: issue-224-cbuffer-export

## Scope

### In scope
- New daemon handler `cbuffer_raw` (unit + integration)
- New CLI command `rdc cbuffer` (unit: JSON mode, raw mode, error paths)
- `bufferBacked == False` error path for `cbuffer_raw`
- Optional: `_extract_value` int/uint coverage in `test_buffer_decode.py`

### Out of scope
- Existing `cbuffer_decode` handler correctness (covered by prior test suite)
- `rdc vbuffer` / `rdc ibuffer` (separate issue)
- D3D12 root-constant register-space mapping (cannot run on this Linux box; deferred to reporter verification)

## Test Matrix

| Layer | Test Type | File |
|-------|-----------|------|
| Unit | `cbuffer_raw` handler (mock) | `tests/unit/test_buffer_decode.py` (extend) |
| Unit | `rdc cbuffer` CLI command | `tests/unit/test_cbuffer_commands.py` (new) |
| Integration | real capture decoded + raw | `tests/integration/test_daemon_handlers_real.py` (extend) |

## Cases

### `cbuffer_raw` handler (extend `test_buffer_decode.py`)

- **Happy path**: mock `GetConstantBlock` returns a buffer-backed descriptor (`bufferBacked=True`,
  known `byteOffset`/`byteSize`); mock `GetBufferData` returns 16 known bytes.
  Assert response contains `{"path": "...", "size": 16}` and the temp file exists with the
  expected bytes.
- **bufferBacked=False**: mock `GetConstantBlock` returns `bufferBacked=False`.
  Assert the handler returns a JSON-RPC error (code -32602 or equivalent) with a message
  containing `"not buffer-backed"`.  Assert no temp file is created.
- **No adapter**: `state.adapter is None` → assert error -32002 (standard no-adapter guard).
- **Missing eid**: invalid `eid` → assert error from `SetFrameEvent`.

Mock anchor: `mock_renderdoc.py` `GetConstantBlock` (~line 1356), `GetBufferData`.

### `rdc cbuffer` CLI command (new `test_cbuffer_commands.py`)

Mirror structure of `tests/unit/test_mesh_commands.py` (monkeypatch `rdc.commands.cbuffer.call`).

- **JSON mode (default)**: monkeypatch `call("cbuffer_decode", ...)` returns
  `{"eid": 10, "set": 0, "binding": 0, "variables": [{"name": "mvp", "type": "mat4", "value": [...]}]}`.
  Invoke `rdc cbuffer 10 --stage ps --set 0 --binding 0`.
  Assert exit code 0, stdout is valid JSON matching the payload.
- **`--json` explicit flag**: same as above with `--json` flag; assert identical output.
- **`--raw -o file.bin`**: monkeypatch `call("cbuffer_raw", ...)` returns `{"path": "/tmp/cbuffer_10_0_0.bin", "size": 16}`;
  monkeypatch binary delivery (`_deliver_binary` / `fetch_remote_file`).
  Assert exit code 0, output file contains the expected bytes.
- **No session**: `call` raises connection error → assert exit code 1, message on stderr.
- **`--raw` without `-o`**: assert exit code non-zero with usage error on stderr.
- **EID omitted**: monkeypatch `complete_eid` returns `42`; assert the handler is called with `eid=42`.

### Integration (`test_daemon_handlers_real.py`, `@pytest.mark.gpu`)

Extend analogous to `test_cbuffer_decode_returns_data` (~line 1965), using a vkcube/Vulkan
capture with a known draw EID that has a buffer-backed cbuffer.

- **`cbuffer_raw` returns file**: call `cbuffer_raw` with valid `eid`/`set`/`binding`.
  Assert response contains `path` and `size > 0`; assert temp file exists and `size` matches
  `os.path.getsize(path)`.
- **`cbuffer_decode` + `cbuffer_raw` size agreement**: decoded `variables` total byte footprint
  is consistent with the raw `size`.

## Assertions (all tests)

- Exit code 0 on success, non-zero on error.
- JSON output: valid JSON, `variables` array present for decoded mode.
- Raw output: file written at `-o` path, byte count matches `size` from handler.
- Error messages go to stderr; stdout is empty on error.
- `bufferBacked=False` produces an error message containing `"not buffer-backed"` (case-insensitive).

## Coverage Gate

CI enforces ≥ 80% line coverage for `src/rdc/commands/cbuffer.py` and the new
`cbuffer_raw` code path in `src/rdc/handlers/buffer.py`.
