# Feature: phase4b-shader-edit-replay

## Summary

Five new daemon handlers and five new CLI commands that implement the **ACT** step of
the agent debug loop: compile a modified shader, inject it as a replacement, re-replay
the capture to observe the effect, and cleanly restore the original state.

Together with Phase 4A (`debug pixel` / `debug vertex`), this completes the full
OBSERVE → NARROW → INSPECT → HYPOTHESIZE → **ACT** cycle in a single CLI session.

## Motivation

Phase 4A surfaces shader execution data (pixel colour, vertex registers, step trace).
The natural next step for an automated agent—or a human developer iterating on a
fix—is to apply a code change and immediately see whether the output changes.

Without programmatic shader replacement, the only workflow is:
1. Export the shader manually from the RenderDoc GUI.
2. Edit it in an external editor.
3. Re-open the GUI, import the modified shader, replay.

This is not scriptable and cannot be integrated into a CI pipeline. Phase 4B closes
that gap: a single `rdc shader-build` / `rdc shader-replace` pair lets an agent or
script apply a hypothesised fix, then call `rdc debug pixel` again to confirm the
output changed as expected.

## Design References

- `设计/命令总览.md` — shader-build, shader-replace, shader-restore are Phase 4B
- `规划/Roadmap.md` — Phase 4: Debug + Replay
- `工程/API-probe-v1.41.md` — verified API behaviour (probe script: `scripts/probe_phase4_api.py`)
- `调研/调研-Shader-Debug流程设计.md` — Phase 4 API probe results including replace cycle

## Scope

### Commands

| Command | Daemon method | RenderDoc API |
|---------|--------------|---------------|
| `rdc shader-encodings` | `shader_encodings` | `GetTargetShaderEncodings()` |
| `rdc shader-build <file> --stage <stage>` | `shader_build` | `BuildTargetShader(entry, encoding, source, flags, stage)` |
| `rdc shader-replace <eid> <stage> --with <id>` | `shader_replace` | `ReplaceResource(original, replacement)` + `SetFrameEvent` |
| `rdc shader-restore <eid> <stage>` | `shader_restore` | `RemoveReplacement(original)` |
| `rdc shader-restore-all` | `shader_restore_all` | `RemoveReplacement` all + `FreeTargetResource` all |

### In scope

- All five daemon handlers with full error handling
- All five CLI commands with `--json` output support
- `DaemonState` additions: `built_shaders`, `shader_replacements`
- Mock stubs for `BuildTargetShader`, `ReplaceResource`, `RemoveReplacement`,
  `FreeTargetResource`, `GetTargetShaderEncodings`
- Unit tests (~34 cases) and GPU integration tests

### Out of scope

- Phase 4C: overlay/mesh commands, VFS debug paths
- Shader cleanup on daemon shutdown (OS reclaims resources)
- SPIRV text assembly as build input (segfaults on `ReplaceResource` — verified in probe)
- `BuildCustomShader` (post-process overlays, different API surface)

## Design

### DaemonState additions

```python
built_shaders: dict[int, Any] = field(default_factory=dict)
# int(rid) → ResourceId returned by BuildTargetShader; freed by shader_restore_all

shader_replacements: dict[int, Any] = field(default_factory=dict)
# int(original_rid) → replacement ResourceId; RemoveReplacement uses original_rid key
```

Both fields are added to the existing `DaemonState` dataclass in `daemon_server.py`.

### Encoding name map (module-level constant)

```python
_ENCODING_NAMES: dict[int, str] = {
    0: "Unknown", 1: "DXBC", 2: "GLSL", 3: "SPIRV",
    4: "SPIRVAsm", 5: "HLSL", 6: "DXIL",
    7: "OpenGLSPIRV", 8: "OpenGLSPIRVAsm", 9: "Slang",
}
```

### Handler: `shader_encodings`

JSON-RPC method name: `shader_encodings`

Parameters: none

Algorithm:
1. Validate replay loaded; raise `-32002` if not.
2. Call `controller.GetTargetShaderEncodings()` → `list[int]`.
3. Map each value through `_ENCODING_NAMES` (fallback to `"Unknown"`).
4. Return encoding list sorted by value.

Response:
```json
{"encodings": [{"value": 2, "name": "GLSL"}, {"value": 3, "name": "SPIRV"}]}
```

Error codes:

| Code | Condition |
|------|-----------|
| `-32002` | No replay loaded |

### Handler: `shader_build`

JSON-RPC method name: `shader_build`

Parameters:
```json
{"stage": "ps", "entry": "main", "encoding": 2, "source": "<glsl source string>"}
```

`entry` defaults to `"main"`.
`encoding` defaults to `2` (GLSL) — the only encoding verified safe for `ReplaceResource`.

Algorithm:
1. Validate replay loaded; raise `-32002` if not.
2. Validate `stage` in `_STAGE_NAMES`; raise `-32602` if not.
3. Map `stage` string to `rd.ShaderStage` enum value.
4. Encode `source` to `bytes` (UTF-8).
5. Build empty `flags = rd.ShaderCompileFlags()`.
6. Call `rid, warnings = controller.BuildTargetShader(entry, encoding, source_bytes, flags, stage_enum)`.
7. Store `state.built_shaders[int(rid)] = rid`.
8. Return `{"shader_id": int(rid), "warnings": warnings}`.

Notes:
- `BuildTargetShader` returns a `(ResourceId, warnings_str)` tuple.
- Source must be passed as `bytes`, not `str`.
- An empty `warnings` string is normal for valid GLSL.
- On compile error, RenderDoc returns a null-like `ResourceId` and a non-empty `warnings`
  string. Check `int(rid) == 0` and raise `-32001` with the warnings as the message.

Response:
```json
{"shader_id": 5000000001, "warnings": ""}
```

Error codes:

| Code | Condition |
|------|-----------|
| `-32002` | No replay loaded |
| `-32602` | Unknown `stage` value |
| `-32001` | Compile failed (`int(rid) == 0`); message contains compiler warnings |

### Handler: `shader_replace`

JSON-RPC method name: `shader_replace`

Parameters:
```json
{"eid": 120, "stage": "ps", "shader_id": 5000000001}
```

Algorithm:
1. Validate replay loaded; raise `-32002` if not.
2. Validate `stage` in `_STAGE_NAMES`; raise `-32602` if not.
3. Look up `shader_id` in `state.built_shaders`; raise `-32001` ("unknown shader_id") if absent.
4. Call `controller.SetFrameEvent(eid, True)`.
5. Retrieve the original shader `ResourceId` bound at `(eid, stage)` via
   `controller.GetPipelineState()` → stage descriptor → shader resource ID.
6. Call `controller.ReplaceResource(original_rid, replacement_rid)`.
7. Store `state.shader_replacements[int(original_rid)] = original_rid`.
8. Invalidate EID cache: `state._eid_cache = -1`.
9. Return `{"ok": True, "original_id": int(original_rid)}`.

Notes:
- `ReplaceResource` affects every draw in the capture that uses `original_rid` as the
  shader, not just the draw at `eid`. This is the RenderDoc design; document in help text.
- `SetFrameEvent` is called before `GetPipelineState` to ensure the correct bound state
  is read.
- EID cache must be invalidated so the next `SetFrameEvent` call triggers a real replay.

Response:
```json
{"ok": true, "original_id": 3000000002}
```

Error codes:

| Code | Condition |
|------|-----------|
| `-32002` | No replay loaded, or `eid` out of range |
| `-32602` | Unknown `stage` value |
| `-32001` | `shader_id` not found in `built_shaders` |

### Handler: `shader_restore`

JSON-RPC method name: `shader_restore`

Parameters:
```json
{"eid": 120, "stage": "ps"}
```

Algorithm:
1. Validate replay loaded; raise `-32002` if not.
2. Validate `stage` in `_STAGE_NAMES`; raise `-32602` if not.
3. Call `controller.SetFrameEvent(eid, True)`.
4. Retrieve `original_rid` for `(eid, stage)` via `GetPipelineState()`.
5. If `int(original_rid)` not in `state.shader_replacements`, raise `-32001`
   ("no replacement active for this shader").
6. Call `controller.RemoveReplacement(original_rid)`.
7. Remove `int(original_rid)` from `state.shader_replacements`.
8. Invalidate EID cache: `state._eid_cache = -1`.
9. Return `{"ok": True}`.

Response:
```json
{"ok": true}
```

Error codes:

| Code | Condition |
|------|-----------|
| `-32002` | No replay loaded |
| `-32602` | Unknown `stage` value |
| `-32001` | No active replacement found for this shader |

### Handler: `shader_restore_all`

JSON-RPC method name: `shader_restore_all`

Parameters: none

Algorithm:
1. Validate replay loaded; raise `-32002` if not.
2. For each `original_rid` in `state.shader_replacements`:
   - Call `controller.RemoveReplacement(original_rid)`.
3. For each `rid` in `state.built_shaders`:
   - Call `controller.FreeTargetResource(rid)`.
4. Clear both dicts.
5. Invalidate EID cache: `state._eid_cache = -1`.
6. Return `{"ok": True, "restored": <replacement_count>, "freed": <built_count>}`.

Notes:
- `FreeTargetResource` must only be called for shaders in `built_shaders`, not for
  original capture resources.
- Remove all replacements before freeing built resources.

Response:
```json
{"ok": true, "restored": 1, "freed": 2}
```

Error codes:

| Code | Condition |
|------|-----------|
| `-32002` | No replay loaded |

## CLI Design

All commands live in `src/rdc/commands/shader_edit.py` as top-level Click commands
(no subgroup — consistent with existing `rdc` flat command namespace).

### `rdc shader-encodings`

```
rdc shader-encodings [--json]
```

Default output (one encoding per line):
```
GLSL
SPIRV
```

`--json` output:
```json
{"encodings": [{"value": 2, "name": "GLSL"}, {"value": 3, "name": "SPIRV"}]}
```

### `rdc shader-build <file>`

```
rdc shader-build <file>
    --stage STAGE
    [--entry ENTRY]
    [--encoding N]
    [--json]
    [-q / --quiet]
```

Options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--stage` | str | required | Shader stage: vs, ps, cs, gs, hs, ds |
| `--entry` | str | `"main"` | Entry point function name |
| `--encoding` | int | `2` (GLSL) | ShaderEncoding integer value |
| `--json` | flag | off | Full JSON output |
| `-q/--quiet` | flag | off | Print only the shader_id integer on success |

Default output:
```
shader_id	5000000001
warnings	(none)
```

`-q` output: `5000000001`

`--json` output:
```json
{"shader_id": 5000000001, "warnings": ""}
```

### `rdc shader-replace <eid> <stage>`

```
rdc shader-replace <eid> <stage> --with <shader_id> [--json]
```

Arguments:
- `eid` — event ID of the draw call
- `stage` — shader stage (vs, ps, cs, ...)

Required option: `--with <shader_id>` (integer returned by `shader-build`).

Default output:
```
ok		true
original_id	3000000002
```

Note: add a warning line to stderr: `warning: replacement affects all draws using this shader`.

`--json` output:
```json
{"ok": true, "original_id": 3000000002}
```

### `rdc shader-restore <eid> <stage>`

```
rdc shader-restore <eid> <stage> [--json]
```

Default output:
```
ok	true
```

`--json` output:
```json
{"ok": true}
```

### `rdc shader-restore-all`

```
rdc shader-restore-all [--json]
```

Default output:
```
ok		true
restored	1
freed		2
```

`--json` output:
```json
{"ok": true, "restored": 1, "freed": 2}
```

## Error Handling

### Error code reference

| Code | Name | Meaning |
|------|------|---------|
| `-32002` | No replay | No capture loaded in daemon |
| `-32001` | Shader error | Compile failed, unknown shader_id, or no active replacement |
| `-32602` | Invalid params | Unknown stage value |

### CLI exit codes

All daemon errors → exit code `1`, message printed to stderr as `error: <message>`.
Success → exit code `0`.

## Files to Create / Modify

### New files

| File | Description |
|------|-------------|
| `src/rdc/handlers/shader_edit.py` | 5 handlers + `_get_stage_shader_rid` helper |
| `src/rdc/commands/shader_edit.py` | 5 CLI commands |
| `tests/unit/test_shader_edit_handlers.py` | ~18 handler unit tests |
| `tests/unit/test_shader_edit_commands.py` | ~16 CLI unit tests |

### Modified files

| File | Change |
|------|--------|
| `src/rdc/daemon_server.py` | Add `built_shaders` + `shader_replacements` to `DaemonState`; import + register 5 handlers |
| `src/rdc/cli.py` | Import + register 5 commands |
| `tests/mocks/mock_renderdoc.py` | Add stubs: `BuildTargetShader`, `ReplaceResource`, `RemoveReplacement`, `FreeTargetResource`, `GetTargetShaderEncodings` |
| `tests/integration/test_daemon_handlers_real.py` | GPU integration tests for all 5 handlers |

## Estimated Size

| Component | Lines |
|-----------|-------|
| `src/rdc/handlers/shader_edit.py` | ~120 |
| `src/rdc/commands/shader_edit.py` | ~110 |
| `src/rdc/daemon_server.py` (additions) | ~8 |
| `src/rdc/cli.py` (additions) | ~6 |
| `tests/mocks/mock_renderdoc.py` (stubs) | ~30 |
| `tests/unit/test_shader_edit_handlers.py` | ~200 |
| `tests/unit/test_shader_edit_commands.py` | ~180 |
| GPU integration tests | ~60 |
| **Total** | **~714** |

## Not In Scope

- Phase 4C: overlay/mesh debug commands, VFS debug paths
- Shader cleanup on daemon shutdown (OS handles resource reclamation)
- SPIRV text assembly input (`SPIRVAsm` encoding) — segfaults on `ReplaceResource`, verified in probe
- `BuildCustomShader` for post-process overlays (different API surface, different use case)
- Breakpoints or partial replay (always run to completion)
- Multi-capture or cross-session shader sharing
