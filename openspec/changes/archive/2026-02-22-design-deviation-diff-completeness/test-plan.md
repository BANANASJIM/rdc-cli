# Test Plan: diff-completeness — --draws, --passes, and summary mode

## Unit Tests

### `tests/unit/test_diff_summary.py` (new file)

Tests for the new `src/rdc/diff/summary.py` module.

**`TestDiffSummary`**

| ID | Test | Assertion |
|----|------|-----------|
| S-01 | `diff_summary` — identical stats | all deltas zero, returns `{"draws": (n,n,0), ...}` |
| S-02 | `diff_summary` — draw count increased | `draws` delta positive |
| S-03 | `diff_summary` — pass removed | `passes` delta negative |
| S-04 | `diff_summary` — resource count changed | `resources` delta non-zero |
| S-05 | `diff_summary` — all categories changed simultaneously | all four deltas present |
| S-06 | `diff_summary` — empty both sides | all zeros |

**`TestRenderText`**

| ID | Test | Assertion |
|----|------|-----------|
| S-07 | all-zero deltas → `"identical"` output | output is exactly `"identical"` |
| S-08 | positive draw delta → `"+N"` formatted | `"draws"` line contains `(+N)` |
| S-09 | negative pass delta → `"-N"` formatted | `"passes"` line contains `(-N)` |
| S-10 | equal category shows `(=)` | lines with zero delta show `(=)` |
| S-11 | four categories always emitted | output has exactly 4 non-empty lines when non-identical |

**`TestRenderJsonSummary`**

| ID | Test | Assertion |
|----|------|-----------|
| S-12 | JSON schema has `draws`, `passes`, `resources`, `events` keys | all four present |
| S-13 | each key has `a`, `b`, `delta` sub-fields | sub-fields exist and are ints |
| S-14 | empty input → valid JSON with all-zero values | parses without error |

### `tests/unit/test_diff_command.py` (extend existing)

**Update existing stubs to real behavior:**

| ID | Test | Change |
|----|------|--------|
| C-01 | `test_diff_draws_mode` (was #31) | mock `query_both` to return draw lists; assert exit 0 or 1, not 2; assert output contains TSV header |
| C-02 | `test_diff_default_summary` (was #33) | mock `query_both` to return stats; assert output non-empty and exit 0 or 1 |

**New `--draws` mode tests:**

| ID | Test | Assertion |
|----|------|-----------|
| C-03 | `--draws` with identical draws | exit 0, output contains `=` rows |
| C-04 | `--draws` with differences | exit 1, output contains `~` or `+`/`-` rows |
| C-05 | `--draws --shortstat` | exit 0/1, output matches `"N added, N deleted, N modified, N unchanged"` pattern |
| C-06 | `--draws --format json` | exit 0/1, output is valid JSON array |
| C-07 | `--draws --format unified` | exit 0/1, output starts with `--- a/` header |
| C-08 | `--draws` when `query_both` returns None | exit 2, error message on stderr |
| C-09 | `--draws --no-header` with TSV | output has no header line |

**New `--passes` mode tests:**

| ID | Test | Assertion |
|----|------|-----------|
| C-10 | `--passes` with identical passes | exit 0, TSV output with `=` status rows |
| C-11 | `--passes` with pass added | exit 1, output contains `+` row |
| C-12 | `--passes` with pass removed | exit 1, output contains `-` row |
| C-13 | `--passes --shortstat` | exit 0/1, output matches shortstat pattern |
| C-14 | `--passes --format json` | exit 0/1, valid JSON array |
| C-15 | `--passes --format unified` | exit 0/1, starts with `--- a/` header |
| C-16 | `--passes` when `query_both` returns None | exit 2, error on stderr |

**New `summary` mode tests:**

| ID | Test | Assertion |
|----|------|-----------|
| C-17 | no flag, all identical | exit 0, output is `"identical"` |
| C-18 | no flag, draws differ | exit 1, output contains `draws:` line with delta |
| C-19 | no flag `--json` | exit 0/1, valid JSON with four top-level keys |
| C-20 | no flag, `query_both` fails | exit 2, error message |

### `tests/unit/test_diff_draws.py` (no change needed)

Existing tests cover `diff_draws()`, `compare_draw_pair()`, and all renderers. No additions required.

### `tests/unit/test_diff_stats.py` (no change needed)

Existing tests cover `diff_stats()` and all renderers — these are reused for `--passes`.

## CLI Tests

All CLI tests use `CliRunner` with monkeypatched `start_diff_session`, `stop_diff_session`, and `query_both` on `rdc.commands.diff`. This follows the existing pattern in `test_diff_command.py`.

**Mock shape for `query_both` returning draws:**
```python
def mock_query_both(ctx, method, params, **kw):
    if method == "draws":
        draws = [{"eid": 10, "type": "DrawIndexed", "triangles": 100, "instances": 1,
                  "pass": "GBuffer", "marker": "Floor"}]
        resp = {"result": {"draws": draws, "summary": "1 draw calls"}}
        return resp, resp, ""
    return None, None, "unexpected method"
```

**Mock shape for `query_both` returning stats (for `--passes` and `summary`):**
```python
def mock_query_both(ctx, method, params, **kw):
    if method == "stats":
        per_pass = [{"name": "GBuffer", "draws": 10, "triangles": 5000, "dispatches": 0}]
        resp = {"result": {"per_pass": per_pass, "top_draws": []}}
        return resp, resp, ""
    return None, None, "unexpected method"
```

## GPU Integration Tests

Location: `tests/integration/test_daemon_handlers_real.py`, new class `TestDiffCompletenessReal`.

These tests use two copies of the same `.rdc` file (self-diff), so all results should show no differences.

**Setup pattern (same capture diffed against itself):**

```python
@pytest.fixture(scope="class")
def self_diff_ctx(real_capture):
    ctx, err = start_diff_session(str(real_capture), str(real_capture))
    assert ctx is not None, err
    yield ctx
    stop_diff_session(ctx)
```

| ID | Test | Assertion |
|----|------|-----------|
| G-01 | `--draws` self-diff | all rows have status `=`; exit 0 |
| G-02 | `--passes` self-diff | all rows have status `=`; exit 0 |
| G-03 | `summary` self-diff | output is `"identical"`; exit 0 |
| G-04 | `--draws` `--format json` self-diff | valid JSON; all `"status"` fields are `"="` |
| G-05 | `--passes` `--shortstat` self-diff | shortstat shows all-zero deltas |
| G-06 | `--draws` raw `draws` RPC → `build_draw_records` produces non-empty list | `DrawRecord` list has at least one entry |
| G-07 | `--passes` raw `stats` RPC → `per_pass` list non-empty | at least one pass present |

These tests are marked `@pytest.mark.gpu` and only run when `RENDERDOC_PYTHON_PATH` is set.
