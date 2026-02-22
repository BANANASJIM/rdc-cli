# Tasks: diff-completeness — --draws, --passes, and summary mode

## Tasks

- [ ] Create `src/rdc/diff/summary.py` with `SummaryRow` dataclass, `diff_summary()`, `render_text()`, `render_json()`
- [ ] Create `tests/unit/test_diff_summary.py` with tests S-01 through S-14
- [ ] Implement `_handle_draws()` in `src/rdc/commands/diff.py` — query `draws` RPC, build records, diff, render
- [ ] Implement `_handle_passes()` in `src/rdc/commands/diff.py` — query `stats` RPC, extract `per_pass`, diff via `diff_stats()`, render
- [ ] Implement `_handle_summary()` in `src/rdc/commands/diff.py` — query `stats` RPC + `resources` RPC, compute four deltas, render
- [ ] Remove `_MODE_STUBS` set and wire the three new handlers in `diff_cmd` dispatch block
- [ ] Update `tests/unit/test_diff_command.py` — fix tests C-01/C-02 (remove stub assertions); add tests C-03 through C-20
- [ ] Add GPU integration tests G-01 through G-07 in `tests/integration/test_daemon_handlers_real.py`
- [ ] Run `pixi run lint && pixi run test` — zero failures
