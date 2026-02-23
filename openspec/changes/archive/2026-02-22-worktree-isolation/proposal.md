# Proposal: Worktree Python Import Isolation Fix

**Date:** 2026-02-22
**Scope:** `pixi.toml` (one-line config change)
**Phase:** Infrastructure / Engineering

---

## Problem

Parallel agent development uses `git worktree` to isolate branches. However, tests run inside a worktree import `rdc` from the **main repo's** `src/`, not the worktree's `src/`. This means code changes in the worktree are silently ignored by the test suite.

## Root Cause

`uv sync` (run once in the main repo) installs an editable package entry:

```
~/.local/lib/python3.14/site-packages/__editable__.rdc_cli-0.2.0.pth
```

This `.pth` file contains an absolute path:

```
/home/jim_z/Dev/rdc-cli/src
```

Python processes `.pth` files at interpreter startup. Regardless of which worktree invokes `pixi run test`, the `.pth` silently redirects all `import rdc` calls to the main repo. `sys.path` entries from `.pth` files take **lower priority** than `PYTHONPATH`, but since `PYTHONPATH` is currently unset, the `.pth` wins.

## Solution

### Code change (one line)

Add `PYTHONPATH = "src"` to `[activation.env]` in `pixi.toml`:

```toml
[activation.env]
RENDERDOC_PYTHON_PATH = ".local/renderdoc"
PYTHONPATH = "src"
```

Pixi resolves relative paths in `[activation.env]` from the **pixi project root**, which for a worktree is the worktree's own root directory — not the main repo. `PYTHONPATH` entries are prepended to `sys.path` before `.pth` files are processed, so each worktree's `src/` takes precedence.

### One-time manual step (not a code change)

Remove the stale user-level editable install:

```sh
pip uninstall rdc-cli   # or: rm ~/.local/lib/python3.14/site-packages/__editable__.rdc_cli*.pth
```

This prevents the `.pth` from polluting `sys.path` for developers who do not have `PYTHONPATH` set outside of pixi (e.g., IDE terminals, bare `python` invocations).

## Non-Goals

- Not changing how `uv sync` or package installation works.
- Not modifying test configuration or `conftest.py`.
- No changes to worktree setup scripts (the fix is self-contained in `pixi.toml`).

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `PYTHONPATH` interferes with other packages | Low | `src/` only contains the `rdc` namespace; no stdlib or third-party shadowing |
| pixi relative path resolution differs across OS | Low | Verified behavior; pixi docs confirm project-root-relative expansion |
| Developers without pixi still affected by `.pth` | Low | Documented in worktree setup as a one-time step |

## Acceptance Criteria

1. `pixi run test` inside a worktree imports from the worktree's `src/`, confirmed by checking `rdc.__file__`.
2. `pixi run lint && pixi run test` passes in both the main repo and any worktree simultaneously.
3. No new test failures introduced.
