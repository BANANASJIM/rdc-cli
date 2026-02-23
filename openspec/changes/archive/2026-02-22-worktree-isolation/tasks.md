# Tasks: Worktree Environment Isolation Fix

## Branch
`fix/worktree-isolation`

## Tasks

- [ ] **T1** Create branch `fix/worktree-isolation` from `master`
- [ ] **T2** Edit `pixi.toml`: add `PYTHONPATH = "src"` under `[activation.env]`
- [ ] **T3** Run `pixi run check` — lint + typecheck + test must all pass
- [ ] **T4** Commit: `fix(build): add PYTHONPATH to pixi activation for worktree isolation`
- [ ] **T5** Push + create PR via `gh pr create`
- [ ] **T6** Post-merge: run `pip uninstall rdc-cli` to remove stale user-level `.pth`; close bug in `待解决.md`

## Notes

- Single-line config change — no new files, no test changes expected
- T6 must be done manually in each developer environment
