# Tasks: phase4b-shader-edit-replay

## Parallelization

Two agents work in parallel worktrees:

- **Agent 1** (Opus): Tasks 1–4 + 8 — mocks, DaemonState, handlers, handler unit tests, GPU integration tests
- **Agent 2** (Opus): Tasks 5–7 — CLI commands, CLI registration, CLI unit tests

Task 9 (verification) runs after both agents merge.

---

## Agent 1: Handlers + Tests

### Task 1 — Mock updates (`tests/mocks/mock_renderdoc.py`)

- [ ] Add `_target_encodings: list[int]`, `_built_counter: int`, `_replacements: dict[int, Any]`, `_freed: set[int]` tracking fields to `MockReplayController.__init__`
- [ ] Add `GetTargetShaderEncodings() -> list[int]` → returns `[3, 2]` (SPIRV, GLSL)
- [ ] Add `BuildTargetShader(entry, encoding, source, flags, stage) -> tuple[ResourceId, str]` → increments `_built_counter`, returns `(ResourceId(_built_counter), "")`
- [ ] Add `ReplaceResource(original, replacement) -> None` → stores `_replacements[int(original)] = replacement`
- [ ] Add `RemoveReplacement(original) -> None` → removes `int(original)` from `_replacements`
- [ ] Add `FreeTargetResource(rid) -> None` → adds `int(rid)` to `_freed`

### Task 2 — DaemonState + handler registration (`src/rdc/daemon_server.py`)

- [ ] Add `built_shaders: dict[int, Any] = field(default_factory=dict)` to `DaemonState`
- [ ] Add `shader_replacements: dict[int, int] = field(default_factory=dict)` to `DaemonState`
- [ ] Add `from rdc.handlers.shader_edit import HANDLERS as _SHADER_EDIT_HANDLERS` import
- [ ] Merge `**_SHADER_EDIT_HANDLERS` into `_DISPATCH`

### Task 3 — Handler module (`src/rdc/handlers/shader_edit.py`)

- [ ] Create `src/rdc/handlers/shader_edit.py` with `from __future__ import annotations` and required imports
- [ ] Define `_ENCODING_NAMES: dict[int, str]` mapping int → name (3→"SPIRV", 2→"GLSL", 1→"DXBC", 5→"HLSL", 6→"DXIL")
- [ ] Implement `_handle_shader_encodings(request_id, params, state)`:
  - Validate `state.adapter is not None` → error `-32002`
  - Call `state.adapter.controller.GetTargetShaderEncodings()`
  - Return `{"encodings": [{"id": int(e), "name": _ENCODING_NAMES.get(int(e), str(int(e)))} for e in encs]}`
- [ ] Implement `_handle_shader_build(request_id, params, state)`:
  - Validate `state.adapter is not None` → error `-32002`
  - Extract `source` (str), `stage` (str), `entry` (str, default `"main"`), `encoding` (int, default 2)
  - Validate `stage` is a recognized stage name → error `-32002` on invalid
  - Encode source as UTF-8 bytes
  - Build `ShaderCompileFlags()` (empty flags)
  - Call `controller.BuildTargetShader(entry, encoding, source_bytes, flags, stage_enum)` → `(rid, errors)`
  - If `errors` is non-empty → error `-32002` with the error string
  - Store `int(rid)` → `{"source": source, "stage": stage, "entry": entry, "encoding": encoding}` in `state.built_shaders`
  - Return `{"id": int(rid), "stage": stage, "entry": entry, "encoding": encoding}`
- [ ] Implement `_handle_shader_replace(request_id, params, state)`:
  - Validate `state.adapter is not None` → error `-32002`
  - Extract `eid` (int), `stage` (str), `built_id` (int, from params key `"with"`)
  - Validate `built_id` in `state.built_shaders` → error `-32002` with `"unknown built shader id"`
  - Call `_set_frame_event(state, eid)` to navigate to the draw
  - Look up live shader ResourceId for the given stage via pipeline state → error `-32002` if not found
  - Call `controller.ReplaceResource(original_rid, replacement_rid)`
  - Store `int(original_rid)` → `built_id` in `state.shader_replacements`
  - Invalidate `state._eid_cache = -1`
  - Return `{"eid": eid, "stage": stage, "original": int(original_rid), "replacement": built_id}`
- [ ] Implement `_handle_shader_restore(request_id, params, state)`:
  - Validate `state.adapter is not None` → error `-32002`
  - Extract `eid` (int), `stage` (str)
  - Call `_set_frame_event(state, eid)` to navigate to the draw
  - Look up live shader ResourceId for the given stage → error `-32002` if not found
  - Look up `int(original_rid)` in `state.shader_replacements` → error `-32002` with `"no replacement active for stage"` if missing
  - Call `controller.RemoveReplacement(original_rid)`
  - Remove from `state.shader_replacements`
  - Invalidate `state._eid_cache = -1`
  - Return `{"eid": eid, "stage": stage, "restored": int(original_rid)}`
- [ ] Implement `_handle_shader_restore_all(request_id, params, state)`:
  - Validate `state.adapter is not None` → error `-32002`
  - For each `original_rid` in `state.shader_replacements`: call `controller.RemoveReplacement(ResourceId(original_rid))`
  - For each `built_id` in `state.built_shaders`: call `controller.FreeTargetResource(ResourceId(built_id))`
  - Clear `state.shader_replacements` and `state.built_shaders`
  - Invalidate `state._eid_cache = -1`
  - Return `{"restored": restored_count, "freed": freed_count}`
- [ ] Define and export `HANDLERS: dict[str, Any] = {"shader_encodings": _handle_shader_encodings, "shader_build": _handle_shader_build, "shader_replace": _handle_shader_replace, "shader_restore": _handle_shader_restore, "shader_restore_all": _handle_shader_restore_all}`

### Task 4 — Handler unit tests (`tests/unit/test_shader_edit_handlers.py`)

- [ ] Create `tests/unit/test_shader_edit_handlers.py`
- [ ] Create `_make_state()` helper: `DaemonState` with mock adapter whose controller has `GetTargetShaderEncodings`, `BuildTargetShader`, `ReplaceResource`, `RemoveReplacement`, `FreeTargetResource`, `SetFrameEvent` on a `SimpleNamespace`

#### `shader_encodings` handler tests
- [ ] Add `test_encodings_happy_path`: mock returns `[3, 2]` → response has `encodings` list with `{"id": 3, "name": "SPIRV"}` and `{"id": 2, "name": "GLSL"}`
- [ ] Add `test_encodings_no_adapter`: `state.adapter = None` → error `-32002`
- [ ] Add `test_encodings_unknown_id`: mock returns `[99]` → `name` is `"99"` (fallback)

#### `shader_build` handler tests
- [ ] Add `test_build_happy_path`: source `"void main() {}"`, stage `"ps"`, encoding 2 → response has `id` (int), `stage`, `entry`, `encoding`; `built_id` stored in `state.built_shaders`
- [ ] Add `test_build_compile_error`: `BuildTargetShader` returns `(rid, "error: undefined symbol")` → error `-32002` with message containing the error string; `built_shaders` not updated
- [ ] Add `test_build_no_adapter`: `state.adapter = None` → error `-32002`
- [ ] Add `test_build_invalid_stage`: stage `"bogus"` → error `-32002` with `"invalid stage"`
- [ ] Add `test_build_default_entry`: no `entry` param → `BuildTargetShader` called with `"main"`

#### `shader_replace` handler tests
- [ ] Add `test_replace_happy_path`: pre-populate `state.built_shaders[42] = {...}`; call replace with `built_id=42`; assert `ReplaceResource` called; `state.shader_replacements` updated; `state._eid_cache == -1`
- [ ] Add `test_replace_unknown_built_id`: `built_id=999` not in `built_shaders` → error `-32002` with `"unknown built shader id"`
- [ ] Add `test_replace_no_adapter`: → error `-32002`
- [ ] Add `test_replace_cache_invalidated`: after replace, `state._eid_cache` is `-1` even if it was non-negative before

#### `shader_restore` handler tests
- [ ] Add `test_restore_happy_path`: pre-populate `state.shader_replacements`; call restore; assert `RemoveReplacement` called; entry removed from `state.shader_replacements`; `state._eid_cache == -1`
- [ ] Add `test_restore_no_active_replacement`: stage not in replacements → error `-32002` with `"no replacement active for stage"`
- [ ] Add `test_restore_no_adapter`: → error `-32002`

#### `shader_restore_all` handler tests
- [ ] Add `test_restore_all_happy_path`: 2 replacements + 2 built shaders; call restore_all; assert `RemoveReplacement` called twice, `FreeTargetResource` called twice; both dicts cleared; response has `restored=2, freed=2`
- [ ] Add `test_restore_all_empty`: no replacements, no built shaders → returns `restored=0, freed=0`; no API calls
- [ ] Add `test_restore_all_no_adapter`: → error `-32002`

- [ ] Run `pixi run test -k test_shader_edit_handlers` — all tests green

### Task 8 — GPU integration tests (`tests/integration/test_daemon_handlers_real.py`)

- [ ] Add `class TestShaderEditReal` to `tests/integration/test_daemon_handlers_real.py`
- [ ] Add `test_get_encodings_real`: call `_handle_shader_encodings` directly; assert response has `encodings` list, each entry has `id` (int) and `name` (str); GLSL (2) or SPIRV (3) present
- [ ] Add `test_build_glsl_real`: compile a minimal passthrough GLSL fragment shader using encoding 2; assert response has `id` (positive int); `state.built_shaders` is non-empty; no error
- [ ] Add `test_replace_and_restore_real`: build a passthrough GLSL PS; replace at a known draw EID; assert `state.shader_replacements` non-empty; then call restore; assert `shader_replacements` empty; `state._eid_cache == -1` after each operation
- [ ] Add `test_restore_all_real`: build 2 shaders (or 1), replace, call restore_all; assert both dicts cleared; no exceptions
- [ ] Run `RENDERDOC_PYTHON_PATH=/home/jim_z/Dev/renderdoc-src/build-py314/lib pixi run test-gpu -k TestShaderEditReal`

---

## Agent 2: CLI + Registration

### Task 5 — CLI commands (`src/rdc/commands/shader_edit.py`)

- [ ] Create `src/rdc/commands/shader_edit.py` with `from __future__ import annotations` and required imports
- [ ] Implement `shader_encodings_cmd` (`rdc shader-encodings`):
  - Option `--json / --no-json` (default off)
  - Call `_daemon_call("shader_encodings", {})` (import `_daemon_call` from `rdc.commands.info`)
  - Default: one line per encoding `"<id>  <name>"`, sorted by id
  - `--json`: emit full JSON response
- [ ] Implement `shader_build_cmd` (`rdc shader-build <file>`):
  - Argument `file` (`click.Path(exists=True, dir_okay=False, path_type=Path)`)
  - Option `--stage` (required, `Choice(["vs","hs","ds","gs","ps","cs","ms","ts"])`)
  - Option `--entry` (str, default `"main"`)
  - Option `--encoding` (int, default 2, help `"shader encoding id (2=GLSL, 3=SPIRV)"`)
  - Option `--json / --no-json`
  - Option `-q / --quiet` (suppress success message)
  - Read file as UTF-8 text; send `_daemon_call("shader_build", {"source": text, "stage": stage, "entry": entry, "encoding": encoding})`
  - Default: `click.echo(f"built shader id={result['id']} stage={result['stage']}")` unless `-q`
  - `--json`: emit full JSON response
- [ ] Implement `shader_replace_cmd` (`rdc shader-replace <eid> <stage>`):
  - Arguments `eid` (int), `stage` (str)
  - Option `--with` (`"built_id"`, required, int, help `"built shader id from shader-build"`)
  - Send `_daemon_call("shader_replace", {"eid": eid, "stage": stage, "with": built_id})`
  - Echo `"replaced stage={stage} at eid={eid}"` on success
- [ ] Implement `shader_restore_cmd` (`rdc shader-restore <eid> <stage>`):
  - Arguments `eid` (int), `stage` (str)
  - Send `_daemon_call("shader_restore", {"eid": eid, "stage": stage})`
  - Echo `"restored stage={stage} at eid={eid}"` on success
- [ ] Implement `shader_restore_all_cmd` (`rdc shader-restore-all`):
  - No arguments or options
  - Send `_daemon_call("shader_restore_all", {})`
  - Echo `"restored {result['restored']} replacement(s), freed {result['freed']} shader(s)"` on success

### Task 6 — CLI registration (`src/rdc/cli.py`)

- [ ] Add import block to `src/rdc/cli.py`:
  ```python
  from rdc.commands.shader_edit import (
      shader_build_cmd,
      shader_encodings_cmd,
      shader_replace_cmd,
      shader_restore_all_cmd,
      shader_restore_cmd,
  )
  ```
- [ ] Add 5 registration lines after existing Phase 4A debug registration:
  ```python
  main.add_command(shader_encodings_cmd, name="shader-encodings")
  main.add_command(shader_build_cmd, name="shader-build")
  main.add_command(shader_replace_cmd, name="shader-replace")
  main.add_command(shader_restore_cmd, name="shader-restore")
  main.add_command(shader_restore_all_cmd, name="shader-restore-all")
  ```

### Task 7 — CLI unit tests (`tests/unit/test_shader_edit_commands.py`)

- [ ] Create `tests/unit/test_shader_edit_commands.py`
- [ ] Create `_patch(monkeypatch, response)` helper monkeypatching `_daemon_call` in `rdc.commands.shader_edit`

#### `shader-encodings` CLI tests
- [ ] Add `test_encodings_default_output`: mock returns `{"encodings": [{"id": 3, "name": "SPIRV"}, {"id": 2, "name": "GLSL"}]}`; assert stdout contains `"SPIRV"` and `"GLSL"`; exit 0
- [ ] Add `test_encodings_json`: `--json`; assert stdout is valid JSON with `"encodings"` key; exit 0
- [ ] Add `test_encodings_help`: `rdc shader-encodings --help` exits 0

#### `shader-build` CLI tests
- [ ] Add `test_build_happy_path`: write temp GLSL file; mock returns `{"id": 7, "stage": "ps", "entry": "main", "encoding": 2}`; invoke `shader-build <file> --stage ps`; assert stdout contains `"id=7"`; exit 0
- [ ] Add `test_build_quiet`: `--quiet` flag → no stdout output; exit 0
- [ ] Add `test_build_json`: `--json` → stdout is valid JSON with `"id"` key; exit 0
- [ ] Add `test_build_missing_stage`: omit `--stage` → exit 2 (Click missing required option)
- [ ] Add `test_build_nonexistent_file`: pass non-existent path → exit 2 (Click path validation)
- [ ] Add `test_build_daemon_error`: mock raises `SystemExit(1)` → exit 1
- [ ] Add `test_build_help`: `rdc shader-build --help` exits 0

#### `shader-replace` CLI tests
- [ ] Add `test_replace_happy_path`: mock returns `{"eid": 10, "stage": "ps", "original": 5, "replacement": 7}`; invoke with `--with 7`; assert stdout contains `"replaced"`; exit 0
- [ ] Add `test_replace_missing_with`: omit `--with` → exit 2
- [ ] Add `test_replace_help`: exits 0

#### `shader-restore` CLI tests
- [ ] Add `test_restore_happy_path`: mock returns `{"eid": 10, "stage": "ps", "restored": 5}`; assert stdout contains `"restored"`; exit 0
- [ ] Add `test_restore_help`: exits 0

#### `shader-restore-all` CLI tests
- [ ] Add `test_restore_all_happy_path`: mock returns `{"restored": 2, "freed": 2}`; assert stdout contains `"2 replacement(s)"` and `"2 shader(s)"`; exit 0
- [ ] Add `test_restore_all_help`: exits 0

#### Registration smoke test
- [ ] Add `test_all_commands_in_main_help`: `CliRunner().invoke(main, ["--help"])` output contains `shader-encodings`, `shader-build`, `shader-replace`, `shader-restore`, `shader-restore-all`

- [ ] Run `pixi run test -k test_shader_edit_commands` — all tests green

---

## Task 9 — Final verification (after merge)

- [ ] `pixi run lint` — zero ruff errors, zero mypy strict errors
- [ ] `pixi run test` — all unit tests green, coverage >= 80%
- [ ] Run GPU tests: `RENDERDOC_PYTHON_PATH=/home/jim_z/Dev/renderdoc-src/build-py314/lib pixi run test-gpu -k TestShaderEditReal`
- [ ] Multi-agent code review (Opus / Codex / Gemini) — zero P0/P1 blockers
- [ ] Archive: move `openspec/changes/2026-02-22-phase4b-shader-edit-replay/` → `openspec/changes/archive/`
- [ ] Update `进度跟踪.md` in Obsidian vault
- [ ] Commit, push branch, open PR
