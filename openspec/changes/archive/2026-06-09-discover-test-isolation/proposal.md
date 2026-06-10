# Proposal: discover test isolation — RENDERDOC_PYTHON_PATH env leak

## Root cause

`test_import_failed_without_module_leaves_no_diagnostic`
(`tests/unit/test_discover.py:274`) fails when run under `pixi run` because
`pixi.toml` sets `RENDERDOC_PYTHON_PATH = ".local/renderdoc"` in the activation
environment, and the test does not neutralise that variable.

### Exact mechanism (file:line)

`find_renderdoc()` in `src/rdc/discover.py:150` reads `os.environ.get("RENDERDOC_PYTHON_PATH")`.
When the variable is set to `.local/renderdoc` (a symlink that resolves to
`.local/renderdoc` in the main worktree, which contains `renderdoc.so`),
`os.path.abspath(env_path)` produces a valid directory that is prepended to the
`candidates` list.

The test mocks `_probe_candidate` with a lambda that ignores its `path` argument
and unconditionally returns `ProbeOutcome(IMPORT_FAILED, str(empty_dir))`.  When
`find_renderdoc()` iterates over `candidates` it calls this mock with the real
`.local/renderdoc` path, receives `IMPORT_FAILED` back, then evaluates:

```python
# discover.py:187
elif outcome.result == ProbeResult.IMPORT_FAILED and _has_renderdoc_module(path):
    _diagnostic = outcome
```

`_has_renderdoc_module(path)` is called with the **real** `.local/renderdoc` path
(not `empty_dir`).  That directory contains `renderdoc.so`, so the function
returns `True`, and `_diagnostic` is set — making the test's final assertion
`assert _get_diagnostic() is None` fail.

The `empty_dir` fixture has no `.so` / `.py` / `.pyd` files, so the guard at line
187 was intended to be False.  The mismatch arises because the mock returns an
outcome whose `candidate_path` points to `empty_dir`, while `_has_renderdoc_module`
is evaluated against the loop variable `path`, which is the env-path candidate.

### Why it is env-dependent

| Condition | `RENDERDOC_PYTHON_PATH` in env | `.local/renderdoc` exists | Result |
|-----------|-------------------------------|--------------------------|--------|
| Clean checkout, no `pixi run sync` | not set or empty | no | PASS |
| `pixi run` (activation sets var) | `.local/renderdoc` | no | PASS (dir missing, not added) |
| `pixi run` after `pixi run sync` | `.local/renderdoc` | yes, has `renderdoc.so` | **FAIL** |
| `pixi run` after `pixi run sync`, even in isolation | `.local/renderdoc` | yes | **FAIL** |

Agent 1 ran after `pixi run sync` (real renderdoc built) — fails.  Agent 2 ran
without `pixi run sync` (`.local/renderdoc` absent or not yet populated) — passes.

## Fix design

The test's declared precondition is "import failed without a module present".  It
must hold regardless of the ambient `RENDERDOC_PYTHON_PATH`.  The correct fix is
to isolate the environment inside the test: use
`monkeypatch.delenv("RENDERDOC_PYTHON_PATH", raising=False)` so that no env
candidate is injected into `candidates`.

This is a **test fix, not a product bug**.  `discover.py` correctly reads the env
variable and correctly applies `_has_renderdoc_module`; the real `.local/renderdoc`
directory does contain a module file, so setting `_diagnostic` there is the right
behaviour.  The test simply failed to declare an assumption about the environment.

The same isolation pattern should also be applied to the three sibling tests in
`TestFindRenderdocFallback` that mock `renderdoc_search_paths` and `shutil.which`
but also leave `RENDERDOC_PYTHON_PATH` unmocked.  They currently pass only by
accident, each for a different reason:

- `test_skips_crash_prone_candidate` (line 167) uses a two-outcome iterator;
  with the env candidate present, the `CRASH_PRONE` outcome lands on the env
  path and `SUCCESS` lands on `crash_dir` — the assertion still holds because
  `_try_import_from` is mocked to return the module for any directory, but the
  test no longer exercises the scenario it claims, and a third candidate would
  raise `StopIteration`.
- `test_diagnostic_set_after_crash_prone` (line 207): the env candidate just
  adds one more `CRASH_PRONE` probe whose outcome carries `crash_dir`, so the
  assertions hold.
- `test_diagnostic_set_after_import_failed` (line 237): the env candidate
  probes `IMPORT_FAILED` and `_has_renderdoc_module(env path)` is `True`, so
  `_diagnostic` is set from the env candidate too — the assertions hold only
  because the mocked outcome's fields point at `bad_dir` regardless.

All three carry a latent dependency on the ambient env.  Clearing the variable
in all four tests makes the suite robust.

### Minimal change

In `tests/unit/test_discover.py`, add one line to each of the four tests in
`TestFindRenderdocFallback`:

```python
monkeypatch.delenv("RENDERDOC_PYTHON_PATH", raising=False)
```

Place it alongside the other `monkeypatch.setattr` calls at the top of each test
body.

No changes to `src/rdc/discover.py`.

## Risks

| Risk | Mitigation |
|------|------------|
| Other env vars also leak into `find_renderdoc()` | `RENDERDOC_PYTHON_PATH` is the only env var read directly (discover.py:150). `PATH` reaches the candidate list indirectly via `shutil.which("renderdoccmd")` (discover.py:159-161) and `PYTHONPATH`/`sys.path` reach `_try_import` — both are already mocked in all four tests, so `delenv` plus the existing mocks give full isolation. |
| Removing env var hides a real test scenario | The env-path scenario is covered by `test_diagnostic_set_after_crash_prone` and `test_diagnostic_set_after_import_failed`; those tests can explicitly set `RENDERDOC_PYTHON_PATH` to a tmp dir if desired. |
| Sibling tests in `TestTryImportFrom` / `TestProbeCandidate` | Those tests do not call `find_renderdoc()` and are unaffected. |
