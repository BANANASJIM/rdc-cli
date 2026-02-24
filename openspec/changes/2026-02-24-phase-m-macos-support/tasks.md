# Phase M: macOS Support — Tasks

## Execution Plan (dependency graph)

```
M1 ──┐
M5 ──┤── [sequential, share _platform.py] ──┐
M2 ──┘ (doctor.py, parallel to M1+M5)       ├── lint + test ── M4
M3 ──────────────────────────────────────────┘
```

M1 and M5 must be sequential (both modify `_platform.py`).
M2 and M3 are independent and can run in parallel with M1/M5.
M4 runs last.

## Task List

### M1: Homebrew search paths (~0.5 day)
Files: `src/rdc/_platform.py`, `tests/unit/test_platform.py`

- [ ] Add `sys.platform == "darwin"` branch to `renderdoc_search_paths()` with Homebrew ARM (`/opt/homebrew/opt/renderdoc/lib`), Intel (`/usr/local/opt/renderdoc/lib`), and user build (`~/.local/renderdoc`)
- [ ] Add `sys.platform == "darwin"` branch to `renderdoccmd_search_paths()` with Homebrew bin paths
- [ ] Add unit tests monkeypatching `sys.platform` to `"darwin"` for both functions

### M2: Doctor macOS checks (~0.5 day)
Files: `src/rdc/commands/doctor.py`, `tests/unit/test_doctor.py`

- [ ] Add `_check_mac_xcode_cli()` — verify `xcode-select -p` exits 0
- [ ] Add `_check_mac_homebrew()` — verify `brew` is on PATH
- [ ] Add `_check_mac_renderdoc_dylib()` — check for `librenderdoc.dylib` in Homebrew and build paths
- [ ] Add macOS branch to `_make_build_hint()` returning Homebrew install instructions
- [ ] Wire all three checks into `run_doctor()` under `sys.platform == "darwin"`
- [ ] Add unit tests for each check (mock subprocess/shutil.which, monkeypatch platform)

### M3: CI macOS matrix (~0.5 day)
Files: `.github/workflows/ci.yml`

- [ ] Add `macos-latest` to the OS dimension of the test matrix
- [ ] Gate macOS jobs on `workflow_dispatch` and tag pushes only (not every PR push)
- [ ] Pin a single Python version (3.12) for macOS to control cost
- [ ] Verify branch-protection required checks still match (ubuntu/windows jobs unaffected)

### M4: README macOS section (~0.5 day)
Files: `README.md`

- [ ] Add macOS install section: `pip install rdc-cli`, remote workflow note, optional local build pointer
- [ ] Keep section short (≤10 lines); no duplication of Linux content

### M5: `is_pid_alive()` darwin optimization (~0.5 day)
Files: `src/rdc/_platform.py`, `tests/unit/test_platform.py`

- [ ] Replace `/proc/<pid>/cmdline` read with `ps -p <pid> -o command=` via `subprocess` on darwin
- [ ] Ensure fallback to `os.kill(pid, 0)` on darwin if `ps` call itself fails
- [ ] Add unit tests monkeypatching `sys.platform` to `"darwin"` and mocking `subprocess.run`

## File Conflict Analysis

| File | Tasks | Strategy |
|------|-------|----------|
| `src/rdc/_platform.py` | M1, M5 | Sequential (M1 → M5) or single worktree |
| `tests/unit/test_platform.py` | M1, M5 | Sequential with _platform.py |
| `src/rdc/commands/doctor.py` | M2 | Independent worktree |
| `tests/unit/test_doctor.py` | M2 | Independent worktree |
| `.github/workflows/ci.yml` | M3 | Independent worktree |
| `README.md` | M4 | Independent, do last |

## Definition of Done

- `pixi run lint && pixi run test` passes with zero failures
- No new mypy errors (strict mode)
- macOS paths covered by unit tests (no GPU hardware required)
- CI matrix updated and branch-protection rules verified
- README macOS section merged
- Manual test: `rdc doctor` on macOS (or note macOS hardware requirement for validation)
