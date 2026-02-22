# Tasks: diff-draws

## Phase A — Unit tests: alignment

- [ ] Create `tests/unit/test_diff_alignment.py`
- [ ] DrawRecord construction tests (2)
- [ ] has_markers tests (4)
- [ ] make_match_keys tests (4)
- [ ] make_fallback_keys tests (3)
- [ ] lcs_align tests (7)
- [ ] align_draws tests (6)

## Phase B — Unit tests: comparison + renderers

- [ ] Create `tests/unit/test_diff_draws.py`
- [ ] compare_draw_pair tests (10)
- [ ] diff_draws integration tests (8)
- [ ] render_unified tests (7)
- [ ] render_shortstat tests (3)
- [ ] render_json tests (4)

## Phase C — Unit tests: CLI

- [ ] Create `tests/unit/test_diff_draws_cmd.py`
- [ ] --draws output, exit codes, --shortstat, --json, error, fallback (7)

## Phase D — Implementation: `src/rdc/diff/`

- [ ] Create `src/rdc/diff/__init__.py`
- [ ] Create `src/rdc/diff/alignment.py` — DrawRecord, keys, lcs_align, align_draws
- [ ] Create `src/rdc/diff/draws.py` — DiffStatus, DrawDiffRow, comparison, renderers
- [ ] Verify Phase A + B tests pass

## Phase E — Implementation: CLI --draws

- [ ] Wire --draws in `src/rdc/commands/diff.py`
- [ ] _build_draw_records helper
- [ ] Fallback mode pipeline RPC for shader_hash + topology
- [ ] Verify Phase C tests pass

## Phase F — GPU integration + final

- [ ] GPU test: self-diff hello_triangle.rdc
- [ ] `pixi run lint && pixi run test`
- [ ] Code review → archive → PR
