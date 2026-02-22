# Tasks: diff-stats

## Phase A — Unit tests: logic

- [ ] Create `tests/unit/test_diff_stats.py`
- [ ] Core diff_stats tests: identical/modified-draws/modified-dispatches/modified-triangles (4)
- [ ] ADDED/DELETED/empty-a/empty-b/both-empty tests (5)
- [ ] Name matching: case-insensitive + whitespace strip (2)
- [ ] Mixed multi-pass integration test (1)
- [ ] Delta formatting tests: positive/negative/zero/null fields (5)

## Phase B — Unit tests: renderers

- [ ] TSV renderer: header/no-header/EQUAL/MODIFIED/ADDED/DELETED rows (6)
- [ ] Shortstat renderer: all-equal/mixed/additions-only (3)
- [ ] JSON renderer: valid JSON/schema/null fields (3)
- [ ] Unified diff renderer: header/equal/deleted/added/modified (5)

## Phase C — Unit tests: CLI

- [ ] CLI exit codes: 0=equal/1=changed/2=error (3)
- [ ] CLI format flags: default TSV/--shortstat/--json/--format unified/--no-header (5)
- [ ] Verify stub removal: --stats no longer prints "not yet implemented" (1)

## Phase D — Implementation: `src/rdc/diff/stats.py`

- [ ] Define `PassDiffRow` dataclass (status, name, draws_a/b/delta, tri_a/b/delta, disp_a/b/delta)
- [ ] Implement `diff_stats(a_passes, b_passes) -> list[PassDiffRow]`
  - Case-insensitive name matching
  - EQUAL/MODIFIED/ADDED/DELETED classification
  - Signed delta strings (`+N`, `-N`, `0`, `-` for None side)
- [ ] Implement `render_tsv(rows, *, no_header) -> str`
- [ ] Implement `render_shortstat(rows) -> str`
- [ ] Implement `render_json(rows) -> str`
- [ ] Implement `render_unified(rows, capture_a, capture_b) -> str`
- [ ] Verify Phase A + B tests pass

## Phase E — Implementation: CLI wire-up

- [ ] Remove `"stats"` from `_MODE_STUBS` in `src/rdc/commands/diff.py`
- [ ] Add `--stats` handler: `query_both(ctx, "stats", {})` → extract `per_pass` → `diff_stats()` → render → exit 0/1
- [ ] Respect `--shortstat`, `--json`, `--format`, `--no-header` flags in stats path
- [ ] Verify Phase C tests pass

## Phase F — GPU integration + final

- [ ] Add GPU tests to `tests/gpu/test_daemon_handlers_real.py`:
  - Self-diff `hello_triangle.rdc --stats` → all EQUAL
  - Pass count consistency check
- [ ] `pixi run lint && pixi run test`
- [ ] Code review → archive openspec → update `进度跟踪.md` → PR
