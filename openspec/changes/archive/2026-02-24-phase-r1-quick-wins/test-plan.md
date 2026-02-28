# Phase R1: Test Plan

## Validation Strategy

Pure refactoring — no new tests needed. All 2135 existing tests must pass unchanged.

## Acceptance Criteria

1. `pixi run lint` passes (ruff + mypy)
2. `pixi run test` passes — all 2135 tests green
3. Coverage does not decrease from 94.92%
4. No `sys.path.insert` remains in any test file
5. No local `_req()` definition remains in daemon test files
6. No duplicate `_require_renderdoc()` outside `_helpers.py`

## Regression Checks

- `grep -r "sys.path.insert" tests/` returns 0 matches
- `grep -rn "def _req(" tests/unit/` returns 0 matches (only conftest.py has `rpc_request`)
- `grep -rn "_require_renderdoc" src/rdc/commands/` shows only `_helpers.py` definition + imports
