# Tasks: Phase 1.5 — VFS Path Addressing

## Dependencies

Tasks are ordered by dependency. Tests are written before or alongside implementation (No Test Design, No Implementation).

---

## Phase A: VFS Core (pure functions, no daemon changes)

### A1. Path router
- Create `src/rdc/vfs/__init__.py` (empty)
- Create `src/rdc/vfs/router.py` with `ROUTE_TABLE`, `PathMatch` dataclass, `resolve_path()`
- Route table covers all paths from proposal (root leaves, events, draws, draws/eid/pipeline, draws/eid/shader/stage/*, passes, resources, shaders, current)
- Write `tests/unit/test_vfs_router.py` — all happy path + error cases from test plan
- Verify: `pixi run test -k test_vfs_router`

### A2. Tree cache
- Create `src/rdc/vfs/tree_cache.py` with `VfsNode`, `VfsTree`, `build_vfs_skeleton()`, `populate_draw_subtree()`
- Static skeleton: walks action tree + resource list, populates root + per-draw + per-event + per-pass + per-resource nodes
- Dynamic subtree: `populate_draw_subtree(tree, eid, pipe_state)` inspects active shader stages, fills children
- LRU: `VfsTree.set_draw_subtree()` with configurable capacity (default 64)
- Write `tests/unit/test_vfs_tree_cache.py` — skeleton, dynamic populate, LRU eviction
- Verify: `pixi run test -k test_vfs_tree_cache`

### A3. VFS formatter
- Create `src/rdc/vfs/formatter.py` with `render_ls()`, `render_tree_root()` (ASCII tree rendering)
- `render_ls(children, classify=False)` — one name per line, optional `-F` suffix
- `render_tree_root(path, tree_json, max_depth)` — ASCII `├──`/`└──` rendering
- Tests for formatter are covered by CLI tests in Phase C

---

## Phase B: Daemon Integration

### B1. DaemonState + skeleton build
- Add `vfs_tree: Any = field(default=None, repr=False)` to `DaemonState`
- At end of `_load_replay()`, after `state.max_eid = _max_eid(root_actions)`:
  - `from rdc.vfs.tree_cache import build_vfs_skeleton`
  - `state.vfs_tree = build_vfs_skeleton(root_actions, resources, state.structured_file)`
- Where `resources = state.adapter.get_resources()`

### B2. `vfs_ls` daemon handler
- Add `_handle_vfs_ls(request_id, path, state)` to `daemon_server.py`
- Handle `/current` alias: if path starts with `/current`, replace with `/draws/<current_eid>`. Error if current_eid == 0.
- Look up path in `state.vfs_tree.static`. If not found, return -32001.
- For `/draws/<eid>/shader`: detect cache miss, trigger `SetFrameEvent` + `GetPipelineState` + `populate_draw_subtree()`
- Return `{path, kind, children: [{name, kind}]}`
- Register `vfs_ls` in `_handle_request()` dispatch chain

### B3. `vfs_tree` daemon handler
- Add `_handle_vfs_tree(request_id, path, depth, state)` to `daemon_server.py`
- Handle `/current` alias same as vfs_ls
- Recursive `_subtree(path, depth)` walks `state.vfs_tree.static`
- Depth validation: 1-8, return -32602 if out of range
- Return `{path, tree: {name, kind, children: [...]}}`
- Register `vfs_tree` in `_handle_request()` dispatch chain

### B4. Daemon VFS tests
- Write `tests/unit/test_vfs_daemon.py` — all cases from test plan
- Use `_handle_request()` pattern with `DaemonState` + mock adapter
- Build state with `vfs_tree` pre-populated via `build_vfs_skeleton()`
- Verify: `pixi run test -k test_vfs_daemon`

---

## Phase C: CLI Commands

### C1. VFS CLI commands
- Create `src/rdc/commands/vfs.py` with `ls_cmd`, `cat_cmd`, `tree_cmd`, `complete_cmd`
- Use `_call` pattern (Variant B: `_require_session` + `send_request`)
- `ls`: calls `vfs_ls`, renders with `render_ls()`. Supports `-F`, `--json`.
- `cat`: calls `vfs_ls` to check kind (dir → error, binary on TTY → error), then `resolve_path()` to get handler, then calls handler RPC, formats with extractors.
- `tree`: calls `vfs_tree`, renders with `render_tree_root()`. Supports `--depth`, `--json`.
- `_complete`: hidden command, calls `vfs_ls` on parent dir, filters and outputs matching paths.

### C2. Register in cli.py
- Import `ls_cmd`, `cat_cmd`, `tree_cmd`, `complete_cmd` from `rdc.commands.vfs`
- `main.add_command(ls_cmd, name="ls")` etc.

### C3. CLI tests
- Write `tests/unit/test_vfs_commands.py` — all cases from test plan
- Monkeypatch `_call` in vfs module (or `load_session` + `send_request`)
- Also monkeypatch `resolve_path` for `cat` tests
- Verify: `pixi run test -k test_vfs_commands`

---

## Phase D: Integration + Polish

### D1. GPU integration test
- Add VFS tests to `tests/integration/test_daemon_handlers_real.py`:
  - `test_vfs_ls_root` — `vfs_ls` path="/" returns root children
  - `test_vfs_ls_draws` — `vfs_ls` path="/draws" returns draw eids
  - `test_vfs_ls_draw_shader` — `vfs_ls` on `/draws/<eid>/shader` returns stages
  - `test_vfs_tree_root` — `vfs_tree` depth=1 returns valid tree

### D2. Final verification
- `pixi run lint && pixi run test` — all pass
- `pixi run test-gpu` — integration pass
- Manual smoke test: `rdc open tests/fixtures/hello_triangle.rdc && rdc ls / && rdc cat /info && rdc tree / --depth 2`

---

## Estimated test count

| Test file | Estimated cases |
|-----------|----------------|
| test_vfs_router.py | ~30 (all path patterns + edge cases) |
| test_vfs_tree_cache.py | ~12 (skeleton + dynamic + LRU) |
| test_vfs_daemon.py | ~10 (ls + tree happy/error) |
| test_vfs_commands.py | ~18 (ls/cat/tree/_complete happy/error) |
| integration | ~4 |
| **Total** | **~74** |
