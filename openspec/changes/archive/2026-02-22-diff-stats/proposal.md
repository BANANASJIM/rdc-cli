# Proposal: diff-stats

## Summary

Implement `rdc diff a.rdc b.rdc --stats`: per-pass statistics comparison between
two captures. Matches passes by name, computes draw/dispatch/triangle deltas, and
renders a summary. Exit code: 0=no change, 1=changes found, 2=error.

## Design References

- `设计/命令总览.md` — `rdc diff --stats` spec
- `设计/设计原则.md` — exit codes, output philosophy
- `设计/交互模式.md` — `stats()` and `passes()` RPC method signatures

## Assumptions

Assumes diff-infrastructure exists: dual daemon lifecycle, `DiffContext`,
`query_both`. Both daemons expose `stats()` returning `per_pass` list.

## Approach

Query `stats()` from both daemons concurrently via `query_both`. Match pass
entries by name (case-insensitive, strip whitespace). Compute per-field deltas.
Classify each pass as EQUAL / MODIFIED / ADDED / DELETED. Render output and
set exit code.

### Matching Rules

- Primary key: `name.strip().lower()`
- Present only in A → DELETED
- Present only in B → ADDED
- Present in both → compare `draws`, `dispatches`, `triangles`; EQUAL if all
  match, otherwise MODIFIED
- Ordering: A-order for matched/deleted, B-only appended at end

### Pass Comparison Fields

| Field | Source |
|-------|--------|
| draws | `per_pass[i]["draws"]` |
| dispatches | `per_pass[i]["dispatches"]` |
| triangles | `per_pass[i]["triangles"]` |

RT dimensions (`rt_w`, `rt_h`) are informational only; not used for EQUAL/MODIFIED
classification (can legitimately differ without being a regression).

### Output Formats

**TSV (default):**
```
STATUS  PASS            DRAWS_A  DRAWS_B  DRAWS_DELTA  TRI_A    TRI_B    TRI_DELTA  DISP_A  DISP_B  DISP_DELTA
=       GBuffer         12       12       0            3840     3840     0          0       0       0
~       Lighting        4        6        +2           0        0        0          4       6       +2
-       SSAO            2        -        -            192      -        -          0       -       -
+       TAA             -        3        -            -        432      -          0       0       -
```

**`--shortstat`:**
```
2 passes changed, 1 added, 1 deleted; +2 draws, +240 triangles, +2 dispatches
```

**`--json`:** Array of `PassDiffRow` objects with all fields including `status`,
`name`, `draws_a`, `draws_b`, `draws_delta`, `tri_a`, `tri_b`, `tri_delta`,
`disp_a`, `disp_b`, `disp_delta`.

**`--format unified`:**
```
--- a/a.rdc
+++ b/b.rdc
 GBuffer draws=12 tri=3840 disp=0
-SSAO draws=2 tri=192 disp=0
+TAA draws=3 tri=432 disp=0
-Lighting draws=4 tri=0 disp=4
+Lighting draws=6 tri=0 disp=6
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All passes EQUAL |
| 1 | Any MODIFIED / ADDED / DELETED |
| 2 | RPC error or both daemons failed |

## Changes

### New files

| File | Description |
|------|-------------|
| `src/rdc/diff/stats.py` | `PassDiffRow`, `diff_stats`, 4 renderers |
| `tests/unit/test_diff_stats.py` | Unit + CLI tests |

### Modified files

| File | Change |
|------|--------|
| `src/rdc/commands/diff.py` | Remove `"stats"` from `_MODE_STUBS`; wire `--stats` handler |

## Not in Scope

- RT dimension change detection
- `top_draws` comparison (separate sub-mode)
- Fuzzy/renamed pass matching (only exact name match)
- Pass reordering detection beyond ADDED/DELETED
