# OpenSpec: issue-224-cbuffer-export

## Summary

Expose `rdc cbuffer` as a first-class CLI command with decoded JSON output and optional
raw binary export (`--raw`).

## Context and Motivation

OpenSpec phase2-buffer-decode (archived 2026-02-19) originally planned three CLI commands:
`rdc cbuffer`, `rdc vbuffer`, and `rdc ibuffer`. The daemon handler `cbuffer_decode` and its
VFS route shipped in that phase. The CLI half — `rdc cbuffer` — was never implemented.
This change completes that unshipped work.

GitHub issue #224 (part 2) tracks the gap. Users who rely on `rdc buffer --raw` for raw bytes
have no ergonomic path to decoded constant-buffer variables without constructing VFS paths
manually.

**Scope note:** The archived phase2-buffer-decode plan envisioned `rdc cbuffer` as a thin VFS
`cat` wrapper; this change implements a richer direct command with decoded JSON output, a new
`cbuffer_raw` handler, and a new VFS `leaf_bin` route — reviewers should not expect a pure VFS
wrapper.

## Design

### New command: `rdc cbuffer`

```
rdc cbuffer [EID] --stage [vs|hs|ds|gs|ps|cs] --set N --binding N [--json] [--raw -o file.bin]
```

- `EID`: optional; resolved via `complete_eid` if omitted (matches existing `rdc buffer` pattern).
- `--stage`: default `ps`.
- `--set`: default `0`.
- `--binding`: default `0`.
- `--json`: emit decoded variables as JSON (default output mode).
- `--raw -o file.bin`: export the raw constant-buffer bytes to a file.

### Decoded path

Calls the existing `cbuffer_decode` daemon handler unchanged.  Returns
`{"eid", "set", "binding", "variables": [{name, type, value}, ...]}` and writes it via
`write_json`.  No daemon changes required for this path.

### Raw path

Adds a new `cbuffer_raw` daemon handler in `handlers/buffer.py`.  The handler repeats the
reflection lookup (`fixedBindSetOrSpace` / `fixedBindNumber`), obtains
`GetConstantBlock(...).descriptor`, calls `controller.GetBufferData(resource, byteOffset,
byteSize)`, writes the bytes to `state.temp_dir/cbuffer_<eid>_<set>_<binding>.bin`, and
returns `{"path", "size"}`.

The handler is exposed as a VFS `leaf_bin` route at
`/draws/<eid>/cbuffer/<set>/<binding>/data` in `vfs/router.py`, mirroring the way `buf_raw`
is wired at `/buffers/<id>/data`.  The CLI calls
`_export_vfs_path(f"/draws/{eid}/cbuffer/{set}/{binding}/data", output, raw)` (from
`commands/export.py`), which follows the same `vfs_ls` + `resolve_path` → `_deliver_binary`
flow used by `rdc buffer --raw`.  `_deliver_binary` (vfs.py:216) is the final delivery
step — it calls `call(match.handler, match.args)` through the VFS resolve layer; it is NOT
a standalone "call handler, get path, write bytes" helper invoked directly.

The `hasattr(pipe_state, "GetConstantBlock")` guard present in `cbuffer_decode` is preserved
in `cbuffer_raw` for RenderDoc version drift safety.

### New source file

`src/rdc/commands/cbuffer.py` — registered in `src/rdc/cli.py` adjacent to `buffer_cmd`
(~line 138).

## Risks

### Non-buffer-backed constant buffers

`ConstantBlock.bufferBacked == False` for push constants (Vulkan) and D3D12 root constants.
These have no backing buffer resource; `GetBufferData` would operate on a null resource.

Defined behavior: `--raw` MUST return a JSON-RPC error with a descriptive message
(e.g. `"cbuffer is not buffer-backed (push constant or root constant)"`) rather than crash
or silently return zero bytes.  Decoded `--json` output is unaffected and continues to work
via `GetCBufferVariableContents`.

### D3D12 root constants / register spaces

The `fixedBindSetOrSpace` / `fixedBindNumber` mapping for D3D12 root constants cannot be
verified on this Linux development machine.  The Vulkan (vkcube) integration test exercises
the buffer-backed path only.  Behavior on D3D12 root-constant captures is verified by
reporter @Misaka-Mikoto-Tech on real D3D12 hardware after the PR ships.

### `_extract_value` type coverage (optional improvement)

The existing `_extract_value` helper (`buffer.py:163-173`) handles only `f32v` members;
integer and unsigned-integer shader variables degrade silently.  `_flatten_shader_var`
in `handlers/_helpers.py` already handles `u32v`/`s32v` and is used by `shader_constants`.
Switching `cbuffer_decode` to use `_flatten_shader_var` is an optional polish step; it does
not block this change but is tracked as a separate optional task.
