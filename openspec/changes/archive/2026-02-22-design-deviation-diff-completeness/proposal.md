# Proposal: diff-completeness — implement --draws, --passes, and summary mode

## Problem

Three modes of `rdc diff` are design deviations from `命令总览.md`:

1. `rdc diff <a> <b> --draws` — exits with code 2 and "not yet implemented".
2. `rdc diff <a> <b> --passes` — exits with code 2 and "not yet implemented".
3. `rdc diff <a> <b>` (no mode flag) — falls through silently, exits 0 with no output.

The design specifies all three as first-class Phase 3 features.

## Solution

Implement all three modes end-to-end:

- **`--draws`**: query both daemons via the existing `draws` RPC, build `DrawRecord` lists, run `diff_draws()`, render output. Reuses the alignment and comparison logic already in `src/rdc/diff/draws.py`.
- **`--passes`**: query both daemons via the existing `passes` RPC, extract the `per_pass` list from each, run `diff_stats()` (which already compares per-pass name/draws/triangles/dispatches). Wire the existing `src/rdc/diff/stats.py` renderers to the CLI.
- **`summary` (no flag)**: query both daemons for `stats`, compute top-level deltas (event count, draw count, pass count, resource count), render a compact one-line-per-category output modelled on `git diff --stat`.

No new daemon-side handler is needed for any of these — all required RPCs (`draws`, `passes`, `stats`) already exist.

## Design

### `--draws` mode

**Data flow:**

```
CLI --draws
  → query_both(ctx, "draws", {})           # existing RPC
  → resp["result"]["draws"]                # list[dict] with eid/type/triangles/instances/pass/marker
  → build_draw_records(draws)              # existing fn in rdc.diff.pipeline
  → diff_draws(records_a, records_b)       # existing fn in rdc.diff.draws
  → render_{tsv,unified,json,shortstat}    # existing renderers in rdc.diff.draws
  → sys.exit(0 if all equal else 1)
```

`build_draw_records` (already in `src/rdc/diff/pipeline.py`) converts the RPC dict list to `DrawRecord` objects. The `marker` field from the `draws` RPC maps to `DrawRecord.marker_path`; `pass` maps to `DrawRecord.pass_name`.

**Output formats:** TSV (default), `--format unified`, `--format json`, `--shortstat`. Same flags already wired for `--resources` and `--stats`.

**TSV columns:** `STATUS`, `EID_A`, `EID_B`, `MARKER`, `TYPE`, `TRI_A`, `TRI_B`, `INST_A`, `INST_B`, `CONFIDENCE`

**Exit codes:** 0 = no differences, 1 = differences found, 2 = error.

### `--passes` mode

**Data flow:**

```
CLI --passes
  → query_both(ctx, "stats", {})           # existing RPC (returns per_pass list)
  → resp["result"]["per_pass"]             # list[dict] with name/draws/triangles/dispatches
  → diff_stats(passes_a, passes_b)         # existing fn in rdc.diff.stats
  → render_{tsv,unified,json,shortstat}    # existing renderers in rdc.diff.stats
  → sys.exit(0 if all equal else 1)
```

The `stats` RPC already returns `per_pass` with `name`, `draws`, `triangles`, `dispatches`. The `diff_stats()` function in `rdc.diff.stats` compares exactly this shape. No new RPC or module needed.

**Output formats:** TSV (default), `--format unified`, `--format json`, `--shortstat`.

**TSV columns:** `STATUS`, `PASS`, `DRAWS_A`, `DRAWS_B`, `DRAWS_DELTA`, `TRI_A`, `TRI_B`, `TRI_DELTA`, `DISP_A`, `DISP_B`, `DISP_DELTA`

**Exit codes:** 0 = no differences, 1 = differences found, 2 = error.

### `summary` mode (no flag)

**Data flow:**

```
CLI (no mode flag)
  → query_both(ctx, "stats", {})           # existing RPC
  → compute deltas from top-level stats fields
  → render compact text summary
  → sys.exit(0 if all equal else 1)
```

The `stats` RPC response also has top-level aggregate fields (`total_draws`, `indexed_draws`, `dispatches`, `clears`, etc.) embedded in `per_pass` data. For the summary we derive:

- **event count delta**: compare `max_eid` via a `status` RPC call on each daemon
- **draw count delta**: sum of `per_pass[i].draws` across all passes for each side
- **pass count delta**: `len(per_pass)` per side
- **resource count delta**: from an additional `query_both(ctx, "resources", {})` call

**Output format (text only, no `--format` needed for summary):**

```
draws:     42 → 45  (+3)
passes:     4 →  4  (=)
resources: 18 → 20  (+2)
events:   180 → 195 (+15)
```

One line per category. If all deltas are zero, print `identical` and exit 0. Otherwise exit 1.

`--json` flag outputs a JSON object with the same four keys plus raw a/b values.

## Files Changed

| File | Change |
|------|--------|
| `src/rdc/commands/diff.py` | Remove `_MODE_STUBS` set; add `_handle_draws()`, `_handle_passes()`, `_handle_summary()` functions; wire them in `diff_cmd` |
| `src/rdc/diff/summary.py` | New module: `SummaryRow` dataclass, `diff_summary()`, `render_text()`, `render_json()` |
| `tests/unit/test_diff_command.py` | Update tests #31, #33 to assert real output instead of stub errors; add format/shortstat variants |
| `tests/unit/test_diff_summary.py` | New: unit tests for `diff_summary()` and renderers |
| `tests/integration/test_daemon_handlers_real.py` | Add GPU integration tests for all three modes via real captures |
