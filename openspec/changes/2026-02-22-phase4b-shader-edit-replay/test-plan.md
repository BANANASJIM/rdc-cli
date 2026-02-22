# Test Plan — Phase 4B: Shader Edit-Replay

## Scope

### In scope
- `shader_encodings` handler: returns encoding list, no adapter error
- `shader_build` handler: happy path, compilation failure (null ResourceId), invalid stage, no adapter
- `shader_replace` handler: happy path, built shader not found, no shader bound at stage,
  no adapter, `_eid_cache` invalidation after replace
- `shader_restore` handler: happy path, no replacement active, no adapter
- `shader_restore_all` handler: happy path (removes all replacements + frees all built shaders),
  no active replacements (returns count=0), `FreeTargetResource` call verification
- `shader-encodings` CLI: default line output, `--json`
- `shader-build` CLI: happy path (outputs shader_id), `--quiet`, `--json`, file not found
- `shader-replace` CLI: happy path confirmation output
- `shader-restore` CLI: happy path
- `shader-restore-all` CLI: happy path with count output
- Help text for all 5 commands
- GPU integration tests on `vkcube_replay` fixture
- Mock additions: `GetTargetShaderEncodings`, `BuildTargetShader`, `ReplaceResource`,
  `RemoveReplacement`, `FreeTargetResource` on `MockReplayController`

### Out of scope
- Phase 4C overlay/mesh commands
- VFS debug paths for shader source
- Shader cleanup on daemon shutdown
- D3D11/D3D12 encoding support
- SPIRV-asm encoding (segfaults on ReplaceResource — verified in API probe)
- Performance benchmarking of build/replace cycle

## Test Matrix

| Layer | Scope | File |
|-------|-------|------|
| Unit | `shader_encodings` handler (2 cases) | `tests/unit/test_shader_edit_handlers.py` |
| Unit | `shader_build` handler (4 cases) | `tests/unit/test_shader_edit_handlers.py` |
| Unit | `shader_replace` handler (5 cases) | `tests/unit/test_shader_edit_handlers.py` |
| Unit | `shader_restore` handler (3 cases) | `tests/unit/test_shader_edit_handlers.py` |
| Unit | `shader_restore_all` handler (4 cases) | `tests/unit/test_shader_edit_handlers.py` |
| Unit | `shader-encodings` CLI (3 cases) | `tests/unit/test_shader_edit_commands.py` |
| Unit | `shader-build` CLI (5 cases) | `tests/unit/test_shader_edit_commands.py` |
| Unit | `shader-replace` CLI (2 cases) | `tests/unit/test_shader_edit_commands.py` |
| Unit | `shader-restore` CLI (2 cases) | `tests/unit/test_shader_edit_commands.py` |
| Unit | `shader-restore-all` CLI (2 cases) | `tests/unit/test_shader_edit_commands.py` |
| Unit | Help text (4 cases) | `tests/unit/test_shader_edit_commands.py` |
| GPU | `TestShaderEditReal` (4 cases) | `tests/integration/test_daemon_handlers_real.py` |

## Cases

### `shader_encodings` handler

All tests use `_handle_request` with `DaemonState` + mock adapter pattern from
`test_debug_handlers.py`. A `_make_state()` helper configures `MockReplayController` and
wires it into `DaemonState`.

1. **Happy path — returns encoding list**: `MockReplayController.GetTargetShaderEncodings()`
   returns `[3, 2]` (SPIRV, GLSL integer values); response `result` has key `"encodings"` as a
   list; each entry has `"name"` (string) and `"value"` (int); list length is 2; GLSL entry has
   `value == 2`, SPIRV entry has `value == 3`.
2. **No adapter — error -32002**: `state.adapter` is `None`; response `error.code == -32002`;
   message contains `"no replay"`.

### `shader_build` handler

3. **Happy path — GLSL pixel shader**: configure `MockReplayController.BuildTargetShader` to
   return `(ResourceId(42), "")` (non-null id, empty warnings); call with params
   `{eid, stage: "ps", source: "void main(){}", encoding: "glsl", entry: "main"}`;
   response `result["shader_id"] == 42` and `result["warnings"] == ""`.
4. **Compilation failure — null ResourceId**: `BuildTargetShader` returns
   `(ResourceId(0), "undefined: foo")` (int(rid)==0 signals failure); response
   `error.code == -32001`; `error.data["warnings"]` contains `"undefined: foo"`.
5. **Invalid stage string — error -32602**: params include `stage: "xs"` (unknown stage name);
   response `error.code == -32602`; message contains `"invalid stage"`.
6. **No adapter — error -32002**: `state.adapter` is `None`; response `error.code == -32002`.

### `shader_replace` handler

7. **Happy path — replaces shader, returns original_id**: configure `state.built_shaders` with
   entry `{42: <ResourceId(42)>}`; configure `MockPipeState.GetShader(ShaderStage.Pixel)` to
   return `ResourceId(7)` (existing bound shader); call with params
   `{eid: 100, stage: "ps", shader_id: 42}`; verify `MockReplayController.ReplaceResource`
   called with `(ResourceId(7), ResourceId(42))`; response `result["original_id"] == 7`;
   verify `state.shader_replacements` maps stage `"ps"` to `ResourceId(7)`.
8. **Cache invalidation after replace**: same setup as case 7; set `state._eid_cache = 100`
   before the call; after response, assert `state._eid_cache == -1`.
9. **Built shader not found — error -32001**: `state.built_shaders` is empty (or does not
   contain `shader_id`); call with `shader_id: 999`; response `error.code == -32001`;
   message contains `"shader not found"`.
10. **No shader bound at stage — error -32001**: `state.built_shaders` has `{42: ResourceId(42)}`;
    `MockPipeState.GetShader(ShaderStage.Pixel)` returns `ResourceId(0)` (null id,
    `int(rid) == 0`); response `error.code == -32001`; message contains `"no shader bound"`.
11. **No adapter — error -32002**: `state.adapter` is `None`; response `error.code == -32002`.

### `shader_restore` handler

12. **Happy path — removes replacement**: configure `state.shader_replacements` with
    `{"ps": ResourceId(7)}`; call with params `{eid: 100, stage: "ps"}`; verify
    `MockReplayController.RemoveReplacement` called with `ResourceId(7)`;
    response `result["stage"] == "ps"` and `result["restored"] == True`; verify
    `state.shader_replacements` no longer contains `"ps"`.
13. **No replacement active — error -32001**: `state.shader_replacements` is empty; call with
    `{eid: 100, stage: "ps"}`; response `error.code == -32001`; message contains
    `"no replacement"`.
14. **No adapter — error -32002**: `state.adapter` is `None`; response `error.code == -32002`.

### `shader_restore_all` handler

15. **Happy path — clears all replacements and frees all built shaders**: configure
    `state.shader_replacements = {"ps": ResourceId(7), "vs": ResourceId(3)}`; configure
    `state.built_shaders = {42: ResourceId(42), 99: ResourceId(99)}`; call with params `{}`;
    verify `MockReplayController.RemoveReplacement` called twice (once per replacement);
    verify `MockReplayController.FreeTargetResource` called twice (once per built shader);
    response `result["count"] == 2` (replacement count); verify `state.shader_replacements`
    is empty and `state.built_shaders` is empty.
16. **No active replacements — count=0**: `state.shader_replacements` is empty,
    `state.built_shaders` is empty; response `result["count"] == 0`; no `RemoveReplacement`
    or `FreeTargetResource` calls made.
17. **FreeTargetResource called for each built shader**: same as case 15; track call arguments
    in a list via monkeypatch; assert `ResourceId(42)` and `ResourceId(99)` both appear in
    the tracked args (order independent).
18. **Mixed state — replacements without matching built shaders**: configure
    `state.shader_replacements = {"ps": ResourceId(7)}`; configure `state.built_shaders = {}`;
    call; verify `RemoveReplacement` called once; verify `FreeTargetResource` not called;
    response `result["count"] == 1`.

### `shader-encodings` CLI

All CLI tests monkeypatch `_daemon_call` in the `shader_edit` module and use `CliRunner`.
Pattern mirrors `test_debug_commands.py`: define a `_patch(monkeypatch, response)` helper that
captures params and injects a fake `_daemon_call`.

19. **Default output — one encoding per line**: mock response
    `{"encodings": [{"name": "GLSL", "value": 2}, {"name": "SPIRV", "value": 3}]}`;
    `CliRunner().invoke(main, ["shader-encodings"])`; exit code 0; output contains `"GLSL"` and
    `"2"` on one line, `"SPIRV"` and `"3"` on another line (format: `NAME VALUE`).
20. **`--json` output**: same mock; `--json` flag; exit code 0; `json.loads(output)` succeeds;
    parsed dict has key `"encodings"` with a list of 2 entries; first entry has `"name"` and
    `"value"` keys.
21. **Help text**: `CliRunner().invoke(main, ["shader-encodings", "--help"])`; exit code 0;
    output contains `"--json"`.

### `shader-build` CLI

22. **Happy path — outputs shader_id**: mock response `{"shader_id": 42, "warnings": ""}`;
    create a temp file `shader.frag` with content `"void main(){}"`;
    `CliRunner().invoke(main, ["shader-build", str(shader_path), "--stage", "ps"])`; exit code 0;
    output contains `"42"`.
23. **`--quiet` flag — only ID on stdout**: same mock and temp file; add `--quiet`; output is
    exactly `"42\n"` (no labels or extra text).
24. **`--json` flag — full result**: same mock and temp file; add `--json`; exit code 0;
    `json.loads(output)` succeeds; parsed dict contains `"shader_id": 42` and `"warnings": ""`.
25. **File not found — Click error**: invoke without creating a temp file, passing a nonexistent
    path; exit code 2; output contains error about the path or file.
26. **Help text**: `CliRunner().invoke(main, ["shader-build", "--help"])`; exit code 0;
    output contains `"FILE"`, `"--stage"`, `"--entry"`, `"--encoding"`.

### `shader-replace` CLI

27. **Happy path — confirmation output**: mock response `{"original_id": 7, "stage": "ps"}`;
    `CliRunner().invoke(main, ["shader-replace", "100", "ps", "--with", "42"])`; exit code 0;
    output contains `"ps"` and `"42"` (or `"7"` original).
28. **Help text**: `CliRunner().invoke(main, ["shader-replace", "--help"])`; exit code 0;
    output contains `"EID"`, `"STAGE"`, `"--with"`.

### `shader-restore` CLI

29. **Happy path — confirmation output**: mock response `{"stage": "ps", "restored": True}`;
    `CliRunner().invoke(main, ["shader-restore", "100", "ps"])`; exit code 0;
    output contains `"ps"`.
30. **Help text**: `CliRunner().invoke(main, ["shader-restore", "--help"])`; exit code 0;
    output contains `"EID"` and `"STAGE"`.

### `shader-restore-all` CLI

31. **Happy path — count in output**: mock response `{"count": 2}`;
    `CliRunner().invoke(main, ["shader-restore-all"])`; exit code 0; output contains `"2"`.
32. **Help text**: `CliRunner().invoke(main, ["shader-restore-all", "--help"])`; exit code 0;
    exit code 0.

## GPU Integration Tests

Append a new `TestShaderEditReal` class to
`tests/integration/test_daemon_handlers_real.py`. Use the same `vkcube_replay` fixture and
`_call()` helper as `TestShaderDebugReal`.

```python
@pytest.mark.gpu
class TestShaderEditReal:
    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay, rd_module):
        self.state = _make_state(vkcube_replay, rd_module)
```

| # | Test name | Setup | Assertion |
|---|-----------|-------|-----------|
| G1 | `test_shader_encodings` | Call `shader_encodings` with first draw eid | `result["encodings"]` is a non-empty list; at least one entry has `"name"` in `{"GLSL", "SPIRV"}`; every entry has integer `"value"` |
| G2 | `test_shader_build_glsl` | Get first draw eid; call `shader_build` with a minimal GLSL PS shader source (`"#version 450\nlayout(location=0) out vec4 o; void main(){o=vec4(1);}"`), `stage="ps"`, `encoding="glsl"`; GLSL must be in supported encodings (skip if not) | `result["shader_id"] > 0`; no error |
| G3 | `test_shader_replace_cycle` | Get first draw eid; build GLSL PS shader (skip if GLSL not supported or build fails); call `shader_replace` with the built shader_id and `stage="ps"`; verify response has `"original_id"`; call `shader_restore` with same eid/stage | Replace: `"original_id"` is an int > 0; Restore: `"restored" == True`; no errors |
| G4 | `test_shader_restore_all` | Get first draw eid; build GLSL PS shader twice (skip if not supported); replace PS with first built shader; call `shader_restore_all` | `result["count"] >= 1`; subsequent `shader_restore` on the same stage returns error -32001 (no replacement active) |

### GPU test notes
- Skip tests requiring GLSL if `shader_encodings` does not include GLSL value (2) via
  `pytest.skip`.
- If `shader_build` returns error -32001 (compilation failure), skip the dependent test rather
  than fail, because GPU capability varies.
- `test_shader_replace_cycle` must call `shader_restore` in a `finally` block to avoid leaving
  replacements active in state for subsequent tests.
- `test_shader_restore_all` should not depend on `test_shader_replace_cycle` running first
  (independent setup).

## Assertions

### Handler contracts
- `shader_encodings` returns `{encodings: [{name: str, value: int}]}`
- `shader_build` returns `{shader_id: int, warnings: str}` on success
- `shader_replace` returns `{original_id: int, stage: str}` on success
- `shader_restore` returns `{stage: str, restored: bool}` on success
- `shader_restore_all` returns `{count: int}` on success
- Error -32001: resource/operation failure (build error, shader not found, no replacement)
- Error -32002: no replay loaded (adapter is None)
- Error -32602: invalid parameter (bad stage name)
- `shader_replace` always invalidates `_eid_cache` (sets to -1) on success

### Mock requirements
`MockReplayController` needs these additions (not yet present):

| Method | Signature | Default behaviour |
|--------|-----------|-------------------|
| `GetTargetShaderEncodings()` | `() -> list[int]` | Returns `[3, 2]` (SPIRV, GLSL) |
| `BuildTargetShader(entry, encoding, source, flags, stage)` | `-> tuple[ResourceId, str]` | Configurable via `_build_result: tuple[ResourceId, str]`; defaults to `(ResourceId(1), "")` |
| `ReplaceResource(original, replacement)` | `-> None` | Records call in `_replace_calls: list[tuple]` |
| `RemoveReplacement(rid)` | `-> None` | Records call in `_remove_calls: list[ResourceId]` |
| `FreeTargetResource(rid)` | `-> None` | Records call in `_free_calls: list[ResourceId]` |

`MockPipeState` already has `GetShader(stage) -> ResourceId`; configure via
`pipe._shaders[ShaderStage.Pixel] = ResourceId(7)` in per-test setup.

### CLI contracts
- Default `shader-encodings`: one `NAME VALUE` pair per line, no header
- `shader-encodings --json`: full `encodings` list as JSON object
- `shader-build FILE --stage STAGE`: outputs `shader_id: <N>` (or similar) by default
- `shader-build --quiet`: outputs only the integer shader_id
- `shader-build --json`: full `{shader_id, warnings}` JSON object
- `shader-replace EID STAGE --with ID`: outputs confirmation line
- `shader-restore EID STAGE`: outputs confirmation line
- `shader-restore-all`: outputs restored count

### Error output contract (same as all other commands)
- All error messages to stderr via `click.echo(..., err=True)`
- JSON output always to stdout
- Exit code 0: success; 1: logical failure; 2: error (no session, bad args, daemon error)

## Risks & Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| `BuildTargetShader` only accepts bytes, not str | Handler crashes on string source | Handler must encode source to bytes before call; unit test passes bytes via mock |
| SPIRV-asm encoding segfaults on `ReplaceResource` | Daemon crash | Only GLSL encoding permitted in `shader_build`; validated by stage guard |
| `int(ResourceId(0)) == 0` check for null id | Wrong success detection | All tests explicitly set non-zero id for success case; zero for failure |
| `_eid_cache` not invalidated → stale pipeline state after replace | Subsequent handler queries return stale data | Case 8 explicitly asserts `_eid_cache == -1` post-replace |
| GPU test leaves replacement active on failure | Corrupts state for subsequent tests | `test_shader_replace_cycle` uses `finally: shader_restore`; `test_shader_restore_all` is self-contained |
| `FreeTargetResource` called on already-freed shader | Potential crash on real GPU | `shader_restore_all` clears `built_shaders` before returning; no double-free possible |
| Rollback | Remove `shader_edit.py` handler + command, revert `DaemonState` field additions, remove 5 registration lines | No other handlers affected |
