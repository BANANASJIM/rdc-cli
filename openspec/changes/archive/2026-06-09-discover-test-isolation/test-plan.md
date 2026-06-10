# Test plan: discover test isolation

## Regression guard (primary)

The corrected test must pass in BOTH environments:

| Environment | Expected result |
|-------------|----------------|
| `pixi run test` with `pixi run sync` done (`.local/renderdoc` populated, `RENDERDOC_PYTHON_PATH=.local/renderdoc`) | PASS |
| Clean env, `RENDERDOC_PYTHON_PATH` unset | PASS |
| `RENDERDOC_PYTHON_PATH` set to a directory that contains `renderdoc.so` | PASS |

To verify the "real renderdoc present" case explicitly, run:

```
pixi run uv run pytest tests/unit/test_discover.py::TestFindRenderdocFallback::test_import_failed_without_module_leaves_no_diagnostic -v
```

This already exercises the failure condition (pixi activation sets `RENDERDOC_PYTHON_PATH`).
After the fix is applied this must exit 0 in this worktree.

## Test cases

### TC-1 — originally failing: no-module dir, env var populated

- Setup: `monkeypatch.delenv("RENDERDOC_PYTHON_PATH", raising=False)` added.
- Input: `empty_dir` (no `.so` / `.py` / `.pyd`), `_probe_candidate` returns
  `IMPORT_FAILED`, `renderdoc_search_paths` returns `[str(empty_dir)]`,
  `shutil.which` returns `None`.
- Expected: `find_renderdoc()` returns `None`; `_get_diagnostic()` returns `None`.
- Must pass with `RENDERDOC_PYTHON_PATH=.local/renderdoc` in the outer env.

### TC-2 — regression guard: env-path candidate with real module produces diagnostic

- New test (or inline parametrize).
- Setup: `real_dir = tmp_path / "real-rdoc"; real_dir.mkdir()`; write a stub
  `(real_dir / "renderdoc.so").write_bytes(b"fake")`. A plain file named
  `renderdoc.so` is sufficient: `_has_renderdoc_module` (discover.py:59-66)
  only checks `renderdoc.py` is_file / glob `renderdoc*.so` / glob
  `renderdoc*.pyd`; it never loads the file. `monkeypatch.setenv("RENDERDOC_PYTHON_PATH", str(real_dir))`.
  Mock `_try_import -> None`,
  `_probe_candidate -> ProbeOutcome(IMPORT_FAILED, str(real_dir))`,
  `_try_import_from -> None`, `renderdoc_search_paths -> []`, `shutil.which -> None`.
- Expected: `find_renderdoc()` returns `None`; `_get_diagnostic()` is **not** `None`,
  has `result == IMPORT_FAILED` and `candidate_path == str(real_dir)`.
- Deterministic in both ambient env states (the test sets the variable itself),
  so it runs green inside and outside `pixi run`.
- This documents and protects the product behaviour (env-path module present → diagnostic set).

### TC-3 through TC-5 — latent env leak in sibling tests

Each of `test_skips_crash_prone_candidate`, `test_diagnostic_set_after_crash_prone`,
and `test_diagnostic_set_after_import_failed` must include:

```python
monkeypatch.delenv("RENDERDOC_PYTHON_PATH", raising=False)
```

These tests already pass but carry a hidden dependency.  Adding the `delenv` call
makes them unconditionally safe.  Confirm they still pass after the addition.

## Full suite check

Run `pixi run test` (all unit tests, coverage ≥ 80%); all must pass.
