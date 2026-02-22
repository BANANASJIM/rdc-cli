# Tasks: Code Structure Refactor

All three Phase 2.7 feature branches are merged to master.
This refactor works on the post-merge codebase (838 tests).

---

## Phase A: Extract shared command helpers

- [ ] A1. Create `src/rdc/commands/_helpers.py`
  - Define `require_session() -> tuple[str, int, str]` (exact body from `resources.py`)
  - Define `call(method: str, params: dict[str, Any]) -> dict[str, Any]` (exact body from `resources.py`)
  - Add `__all__ = ["require_session", "call"]`
  - Full type hints; Google-style docstrings

- [ ] A2. Update `src/rdc/commands/resources.py`
  - Remove local `_require_session` and `_call` definitions
  - Add `from rdc.commands._helpers import call as _call, require_session as _require_session`

- [ ] A3. Update `src/rdc/commands/pipeline.py`
  - Remove local `_require_session` and `_call` definitions
  - Add `from rdc.commands._helpers import call as _call, require_session as _require_session`

- [ ] A4. Update `src/rdc/commands/unix_helpers.py`
  - Remove local `_require_session` definition
  - Add `from rdc.commands._helpers import require_session as _require_session`

- [ ] A5. Run `pixi run check` — must pass before proceeding

---

## Phase B: Deduplicate constants, small helpers, dead code

- [ ] B1. STAGE_MAP dedup
  - In `src/rdc/services/query_service.py`, rename `_STAGE_MAP` to `STAGE_MAP`
  - Update all internal references in `query_service.py`
  - In `daemon_server.py`: import `STAGE_MAP`, replace all 8 inline dict literals
  - Replace `_SHADER_STAGES` frozenset definitions in `daemon_server.py` and `commands/pipeline.py`
    with `frozenset(STAGE_MAP)` or `set(STAGE_MAP)` as appropriate

- [ ] B2. Fix `_enum_name` to always return str
  - In `daemon_server.py`: change `_enum_name` body to `return v.name if hasattr(v, "name") else str(v)`
  - Grep for all 3 inline patterns (`v.name if hasattr(v, "name") else str(v)`,
    `getattr(v, "name", str(v))`, `v.name if hasattr(v, "name") else v`)
  - Replace each with `_enum_name(v)` call (import from daemon_server or handlers._helpers)

- [ ] B3. Consolidate `_recv_line` into `src/rdc/_transport.py`
  - Move `_recv_line` from `daemon_server.py` to `_transport.py`
  - Import in both `daemon_server.py` and `daemon_client.py`
  - Add empty-response guard in `daemon_client.send_request`

- [ ] B4. Delete dead `_count_events` from `daemon_server.py` (unused, live version in query_service)

- [ ] B5. Replace magic numbers `0x0002` / `0x0004` in `_collect_pipe_states_recursive`
  - Import `_DRAWCALL`, `_DISPATCH` from `query_service` (or from handlers._helpers)

- [ ] B6. Run `pixi run check` — must pass before proceeding

---

## Phase C: Split `_handle_request` into handler modules

- [ ] C1. Create `src/rdc/handlers/__init__.py`
  - Define `HandlerFunc = Callable[[int, dict[str, Any], DaemonState], tuple[dict[str, Any], bool]]`
  - Export `HandlerFunc`

- [ ] C2. Create `src/rdc/handlers/_helpers.py`
  - Move from `daemon_server.py`:
    - `_set_frame_event`, `_enum_name`, `_sanitize_size`, `_max_eid`
    - `_get_flat_actions`, `_action_type_str`, `_build_shader_cache`, `_collect_pipe_states`
    - `_result_response`, `_error_response`
  - Add new shared helpers:
    - `require_pipe(params, state, request_id)` — replaces 25x boilerplate
    - `get_pipeline_for_stage(pipe_state, stage_val)` — replaces 4x ternary
    - `get_default_disasm_target(controller)` — replaces 4x fallback pattern
  - `daemon_server.py` re-exports all for backward compatibility

- [ ] C3. Create `src/rdc/handlers/core.py`
  - Methods: `ping`, `status`, `goto`, `count`, `shutdown`
  - Export `HANDLERS: dict[str, HandlerFunc]`

- [ ] C4. Create `src/rdc/handlers/query.py`
  - Methods: `shader_map`, `pipeline`, `bindings`, `shader`, `shaders`, `resources`, `resource`,
    `passes`, `pass`, `events`, `draws`, `event`, `draw`, `search`
  - Export `HANDLERS: dict[str, HandlerFunc]`

- [ ] C5. Create `src/rdc/handlers/shader.py`
  - Methods: `shader_targets`, `shader_reflect`, `shader_constants`, `shader_source`,
    `shader_disasm`, `shader_all`, `shader_list_info`, `shader_list_disasm`
  - Use `get_pipeline_for_stage`, `get_default_disasm_target` from `_helpers`
  - Export `HANDLERS: dict[str, HandlerFunc]`

- [ ] C6. Create `src/rdc/handlers/texture.py`
  - Methods: `tex_info`, `tex_export`, `tex_raw`, `rt_export`, `rt_depth`
  - Export `HANDLERS: dict[str, HandlerFunc]`

- [ ] C7. Create `src/rdc/handlers/buffer.py`
  - Methods: `buf_info`, `buf_raw`, `postvs`, `cbuffer_decode`, `vbuffer_decode`, `ibuffer_decode`
  - Export `HANDLERS: dict[str, HandlerFunc]`

- [ ] C8. Create `src/rdc/handlers/pipe_state.py`
  - All 13 `pipe_*` handlers
  - Use `require_pipe` from `_helpers` to eliminate boilerplate
  - Export `HANDLERS: dict[str, HandlerFunc]`

- [ ] C9. Create `src/rdc/handlers/descriptor.py`
  - Methods: `descriptors`, `usage`, `usage_all`, `counter_list`, `counter_fetch`
  - Export `HANDLERS: dict[str, HandlerFunc]`

- [ ] C10. Create `src/rdc/handlers/vfs.py`
  - Methods: `vfs_ls`, `vfs_tree`
  - Export `HANDLERS: dict[str, HandlerFunc]`

- [ ] C11. Refactor `_handle_request` in `daemon_server.py`
  - Import all 8 `HANDLERS` dicts from `rdc.handlers.*`
  - Build `_DISPATCH: dict[str, HandlerFunc]` by merging at module level
  - Replace `if/elif` body with dict lookup + call
  - Keep `_handle_request` signature unchanged
  - Re-export all helpers from `rdc.handlers._helpers` for backward compat
  - Ensure `DaemonState`, `_load_replay` remain in `daemon_server.py`

- [ ] C12. Run `pixi run check` — must pass before proceeding

---

## Phase D: Verify and close

- [ ] D1. Run full check: `pixi run check`
  - ruff check: zero errors
  - ruff format: no drift
  - mypy strict: zero errors
  - pytest: all 838 tests pass, coverage >= 80%

- [ ] D2. Manual import smoke test:
  ```bash
  python -c "from rdc.daemon_server import DaemonState, _handle_request, _build_shader_cache, _enum_name, _sanitize_size, _max_eid"
  python -c "from rdc.commands._helpers import require_session, call"
  python -c "from rdc._transport import recv_line"
  python -c "import rdc.handlers.core, rdc.handlers.query, rdc.handlers.shader, rdc.handlers.texture, rdc.handlers.buffer, rdc.handlers.pipe_state, rdc.handlers.descriptor, rdc.handlers.vfs"
  ```
  All must exit 0.

- [ ] D3. Verify no circular imports:
  ```bash
  python -c "import rdc.daemon_server; import rdc.handlers; from rdc.commands import _helpers; from rdc import _transport"
  ```

- [ ] D4. Commit with message: `refactor(structure): split handler modules, deduplicate helpers and stage map`

- [ ] D5. Open PR targeting master

- [ ] D6. Archive this OpenSpec: move directory to `openspec/changes/archive/`

- [ ] D7. Update Obsidian `进度跟踪.md` — mark phase2.7-refactor-structure complete
