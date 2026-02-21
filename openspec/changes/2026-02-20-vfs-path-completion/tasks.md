# Tasks: VFS Path Shell Completion

## Phase A: Tests

- [ ] Create `tests/unit/test_vfs_completion.py`
- [ ] Test `_complete_vfs_path` with mocked `_daemon_call` — 8 cases
- [ ] Test argument wiring on `ls_cmd`, `cat_cmd`, `tree_cmd` — 3 cases

## Phase B: Implementation

- [ ] Add `_complete_vfs_path(ctx, param, incomplete)` to `src/rdc/commands/vfs.py`
- [ ] Add `shell_complete=_complete_vfs_path` to `ls_cmd` path argument
- [ ] Add `shell_complete=_complete_vfs_path` to `cat_cmd` path argument
- [ ] Add `shell_complete=_complete_vfs_path` to `tree_cmd` path argument

## Phase C: Verify

- [ ] `pixi run check` passes (lint + typecheck + test)
- [ ] Manual smoke test: `rdc completion zsh | source /dev/stdin && rdc ls /d<TAB>`
