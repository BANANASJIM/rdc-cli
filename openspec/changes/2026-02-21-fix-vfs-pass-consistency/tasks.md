# Tasks: fix/vfs-pass-consistency

- [x] Create OpenSpec (proposal, test-plan, tasks)
- [ ] Create branch `fix/vfs-pass-consistency`
- [ ] Write failing unit tests (`tests/unit/test_pass_vfs_fixes.py`)
- [ ] Write failing GPU tests (append to `test_daemon_handlers_real.py`)
- [ ] Fix 3: `_friendly_pass_name` — add fallback for `(Clear)` format
- [ ] Fix 1: `_handle_draws` — use `pass_name_for_eid` helper
- [ ] Fix 2a: `router.py` — add intermediate dir routes for cbuffer/bindings set
- [ ] Fix 2b: `tree_cache.py` — populate bindings/cbuffer children in `populate_draw_subtree`
- [ ] `pixi run check` passes
- [ ] GPU tests pass
- [ ] PR + code review
