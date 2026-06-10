# Tasks: discover-test-isolation

## Phase A: fix the failing test

- [x] In `tests/unit/test_discover.py`,
  `TestFindRenderdocFallback.test_import_failed_without_module_leaves_no_diagnostic` (line 274):
  add `monkeypatch.delenv("RENDERDOC_PYTHON_PATH", raising=False)` alongside the other
  `monkeypatch.setattr` calls.

## Phase B: harden sibling tests

- [x] `test_skips_crash_prone_candidate` (line 167): add `monkeypatch.delenv("RENDERDOC_PYTHON_PATH", raising=False)`.
- [x] `test_diagnostic_set_after_crash_prone` (line 207): same.
- [x] `test_diagnostic_set_after_import_failed` (line 237): same.

## Phase C: add regression guard (TC-2)

- [x] Add `test_import_failed_with_env_module_sets_diagnostic` to
  `TestFindRenderdocFallback`, implementing test-plan TC-2 exactly (tmp-dir
  `mkdir()` + `renderdoc.so` stub file, `setenv`, mocks, assert no module +
  diagnostic `IMPORT_FAILED` with `candidate_path == str(real_dir)`).

## Phase D: verification

- [x] Run `pixi run uv run pytest tests/unit/test_discover.py -v` — all 17+ tests pass.
- [x] Run `pixi run test` — full unit suite passes, coverage ≥ 80%.
- [x] Confirm TC-1 passes with `RENDERDOC_PYTHON_PATH` set in the outer env (i.e. within `pixi run`).
