# Test Plan: diff-draws

## Unit Tests: alignment (`test_diff_alignment.py`)

| # | Test | Validates |
|---|------|-----------|
| 1 | DrawRecord from _handle_draws row | Construction |
| 2 | Missing marker defaults to "-" | Default |
| 3-6 | has_markers: all present/absent/mixed/empty | Detection |
| 7-10 | make_match_keys: unique pairs/repeated/mixed/empty | Sequential index |
| 11-13 | make_fallback_keys: distinct/same-type-diff-topo/identical | Fallback keys |
| 14-20 | lcs_align: identical/added/deleted/all-diff/swap/empty-a/empty-b/both-empty | Core LCS |
| 21-26 | align_draws: marker identical/added/deleted/fallback/grouping/no-slash | Full alignment |

## Unit Tests: comparison + renderers (`test_diff_draws.py`)

| # | Test | Validates |
|---|------|-----------|
| 27-35 | compare_draw_pair: equal/tri-diff/inst-diff/type-diff/added/deleted/confidence | Classification |
| 36 | Both None → ValueError | Error |
| 37-44 | diff_draws: identical/added/deleted/modified/all-diff/empty-a/empty-b/both-empty/fallback | Integration |
| 45-51 | render_unified: header/equal/deleted/added/modified/mixed/empty | Unified format |
| 52-54 | render_shortstat: all-equal/mixed/empty | Summary line |
| 55-58 | render_json: schema/nulls/valid-json/empty | JSON format |

## Unit Tests: CLI (`test_diff_draws_cmd.py`)

| # | Test | Validates |
|---|------|-----------|
| 59 | Default output — unified diff | Format |
| 60 | Exit 0 all equal | Exit code |
| 61 | Exit 1 changed | Exit code |
| 62 | --shortstat | Single line |
| 63 | --json valid | JSON output |
| 64 | Daemon error → exit 2 | Error handling |
| 65 | Fallback mode → confidence in JSON | Fallback |

## GPU Integration

| # | Test | Validates |
|---|------|-----------|
| 66 | Self-diff hello_triangle.rdc → all EQUAL | Real API |
| 67 | Record count matches standalone draws | Consistency |

## Regression

```bash
pixi run lint && pixi run test
```
