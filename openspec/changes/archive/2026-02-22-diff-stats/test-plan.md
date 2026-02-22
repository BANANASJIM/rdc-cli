# Test Plan: diff-stats

## Unit Tests: logic (`test_diff_stats.py`)

### P0 — Core diff logic

| # | Test | Validates |
|---|------|-----------|
| 1 | Both sides identical passes → all EQUAL | Happy path |
| 2 | One pass draws differ → MODIFIED | Field delta |
| 3 | One pass dispatches differ → MODIFIED | Field delta |
| 4 | One pass triangles differ → MODIFIED | Field delta |
| 5 | Pass only in A → DELETED | Deletion |
| 6 | Pass only in B → ADDED | Addition |
| 7 | Empty A, non-empty B → all ADDED | Edge |
| 8 | Non-empty A, empty B → all DELETED | Edge |
| 9 | Both empty → empty result | Edge |
| 10 | Name match is case-insensitive | Matching |
| 11 | Name match strips leading/trailing whitespace | Matching |
| 12 | Multiple passes: mixed EQUAL/MODIFIED/ADDED/DELETED | Integration |

### P0 — Delta computation

| # | Test | Validates |
|---|------|-----------|
| 13 | Positive delta → `+N` string | Formatting |
| 14 | Negative delta → `-N` string | Formatting |
| 15 | Zero delta → `0` string | Formatting |
| 16 | ADDED row: draws_a/tri_a/disp_a are None | Null fields |
| 17 | DELETED row: draws_b/tri_b/disp_b are None | Null fields |

### P1 — Renderers

| # | Test | Validates |
|---|------|-----------|
| 18 | TSV header present by default | Header |
| 19 | TSV no header with `no_header=True` | Option |
| 20 | TSV EQUAL row format | Row format |
| 21 | TSV MODIFIED row shows signed delta | Delta format |
| 22 | TSV ADDED row uses `-` for A fields | Missing side |
| 23 | TSV DELETED row uses `-` for B fields | Missing side |
| 24 | `--shortstat`: all equal → "0 passes changed" | Summary |
| 25 | `--shortstat`: mixed → correct counts and totals | Summary |
| 26 | `--shortstat`: only additions → correct phrasing | Summary |
| 27 | JSON output is valid JSON | JSON validity |
| 28 | JSON schema: all PassDiffRow fields present | JSON schema |
| 29 | JSON: ADDED row has null A fields | JSON nulls |
| 30 | Unified diff: header lines `--- a/` `+++ b/` | Unified header |
| 31 | Unified diff: EQUAL → ` name draws=N` | Equal line |
| 32 | Unified diff: DELETED → `-name ...` | Deleted line |
| 33 | Unified diff: ADDED → `+name ...` | Added line |
| 34 | Unified diff: MODIFIED → `-` line then `+` line | Modified lines |

## Unit Tests: CLI (`test_diff_stats.py` continued)

### P0 — CLI integration

| # | Test | Validates |
|---|------|-----------|
| 35 | `--stats` all equal → exit 0 | Exit code |
| 36 | `--stats` any change → exit 1 | Exit code |
| 37 | `--stats` daemon error → exit 2 + error message | Error handling |
| 38 | `--stats` default output is TSV | Default format |
| 39 | `--stats --shortstat` → single summary line | Shortstat flag |
| 40 | `--stats --json` → JSON array output | JSON flag |
| 41 | `--stats --format unified` → unified diff | Format flag |
| 42 | `--stats --no-header` → no header row in TSV | No-header flag |

### P1 — Removed stub

| # | Test | Validates |
|---|------|-----------|
| 43 | `--stats` no longer prints "not yet implemented" | Stub removed |

## GPU Integration (`test_daemon_handlers_real.py`)

| # | Test | Validates |
|---|------|-----------|
| 44 | Self-diff `hello_triangle.rdc --stats` → all EQUAL, exit 0 | Real API |
| 45 | Pass count in diff matches standalone `stats()` result | Consistency |

## Regression

```bash
pixi run lint && pixi run test
```
