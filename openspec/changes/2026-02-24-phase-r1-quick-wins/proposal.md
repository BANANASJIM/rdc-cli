# Phase R1: Quick Wins — Deduplicate Source & Test Helpers

## Motivation

The codebase has accumulated mechanical duplication across 43+ test files and 2 source files.
This PR eliminates the most widespread copy-paste patterns with zero behavioral change.

## Changes

### R1.1 Deduplicate `_require_renderdoc()`
- Move identical function from `commands/remote.py` and `commands/capture_control.py` to `commands/_helpers.py`
- Replace both call-sites with import

### R1.2 Remove `sys.path.insert` from tests
- Add `pythonpath = ["src"]` to `[tool.pytest.ini_options]` in `pyproject.toml`
- Delete all `sys.path.insert(0, ...)` lines from 43+ test files
- Remove now-unused `import sys` / `from pathlib import Path` where they become orphaned

### R1.3 Unify `_req()` test helper
- Create `tests/unit/conftest.py` with shared `rpc_request()` function
- Replace 25+ local `_req()` definitions across daemon test files
- Adapt call-sites: `_req(m, **kw)` → `rpc_request(m, kw)` (kwargs→dict)

## Risks

- **R1.2**: If any test relied on `sys.path` ordering, it would break. Mitigated: `pythonpath` does the same thing.
- **R1.3**: Two `_req()` signatures exist (`**params` vs `params: dict`). Must handle both during migration.

## Out of Scope

- `_make_state()` consolidation (R2)
- CLI monkeypatch helpers (R2)
- Command layer unification (R3)
- Handler consolidation (R4)
