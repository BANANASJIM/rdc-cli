# Tasks: discover-test-isolation

## Phase A: fix the failing test

- [ ] In `tests/unit/test_discover.py`,
  `TestFindRenderdocFallback.test_import_failed_without_module_leaves_no_diagnostic` (line 274):
  add `monkeypatch.delenv("RENDERDOC_PYTHON_PATH", raising=False)` alongside the other
  `monkeypatch.setattr` calls.

## Phase B: harden sibling tests

- [ ] `test_skips_crash_prone_candidate` (line 167): add `monkeypatch.delenv("RENDERDOC_PYTHON_PATH", raising=False)`.
- [ ] `test_diagnostic_set_after_crash_prone` (line 207): same.
- [ ] `test_diagnostic_set_after_import_failed` (line 237): same.

## Phase C: add regression guard (TC-2)

- [ ] Add `test_import_failed_with_env_module_sets_diagnostic` to
  `TestFindRenderdocFallback`, implementing test-plan TC-2 exactly (tmp-dir
  `mkdir()` + `renderdoc.so` stub file, `setenv`, mocks, assert no module +
  diagnostic `IMPORT_FAILED` with `candidate_path == str(real_dir)`).

## Phase D: verification

- [ ] Run `pixi run uv run pytest tests/unit/test_discover.py -v` — all 17+ tests pass.
- [ ] Run `pixi run test` — full unit suite passes, coverage ≥ 80%.
- [ ] Confirm TC-1 passes with `RENDERDOC_PYTHON_PATH` set in the outer env (i.e. within `pixi run`).
