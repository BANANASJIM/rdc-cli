# Test Plan: Worktree Environment Isolation Fix

This is a one-line config change (`PYTHONPATH = "src"` in `pixi.toml`).
No new Python code is written; the test plan is verification-only.

## Regression

All existing tests must continue to pass with no changes:

```bash
pixi run lint && pixi run test
# Expected: all tests pass, 0 failures
```

## Manual Verification

### 1. PYTHONPATH is exported in pixi environment

```bash
pixi run python -c "import os; print(os.environ.get('PYTHONPATH', '<not set>'))"
# Expected: src
```

### 2. Import resolves to local src/

```bash
pixi run python -c "import rdc; print(rdc.__file__)"
# Expected path contains: src/rdc/__init__.py (relative to project root)
```

### 3. Worktree resolves imports to its own src/

In any git worktree of this repo:

```bash
pixi run python -c "import rdc; print(rdc.__file__)"
# Expected: path contains the WORKTREE's src/rdc/__init__.py, NOT the main repo's
```
