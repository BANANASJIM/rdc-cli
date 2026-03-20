# Phase 8: Pass Analysis Enhancement — Tasks

## Wave 1 (parallel, no dependencies)

- [ ] **T1**: `rdc passes` surface existing data
  - [ ] `get_pass_hierarchy()` — stop discarding dispatches/triangles/eid range
  - [ ] `_handle_passes()` — pass through new fields
  - [ ] `passes_cmd` — add TSV columns DISPATCHES, TRIANGLES, BEGIN_EID, END_EID
  - [ ] Tests: update existing passes tests for new columns

- [ ] **T2**: load/store extraction from action names
  - [ ] New `_parse_load_store_ops(begin_name, end_name)` in `query_service.py`
  - [ ] Integrate into `_build_pass_list()` — attach load_ops/store_ops to pass dict
  - [ ] Tests: regex parsing unit tests (Clear/Load/Store/Don't Care/None variants)
  - [ ] Tests: passes with dynamic rendering (`vkCmdBeginRendering`)

- [ ] **T7**: `rdc stats` Largest Resources section
  - [ ] `_handle_stats()` — collect top N resources by byte size
  - [ ] `stats_cmd` — render third section
  - [ ] Tests: stats output with largest resources

## Wave 2 (depends on Wave 1)

- [ ] **T3**: `rdc passes --deps --table` per-pass I/O
  - [ ] `build_pass_deps()` — return per_pass list with reads/writes/load/store
  - [ ] `_handle_pass_deps()` — include per_pass in response
  - [ ] `_passes_deps` — new `--table` flag rendering
  - [ ] `--json` response includes both edges and per_pass
  - [ ] Tests: table output format, json schema

- [ ] **T4**: `rdc pass <name>` attachment detail
  - [ ] `_handle_pass()` — enrich attachments with name/format/dims from tex_map
  - [ ] `_handle_pass()` — include load/store from pass data (T2)
  - [ ] `pass_cmd` — render enriched attachment blocks
  - [ ] Tests: pass detail with attachment info

- [ ] **T5**: GL/GLES synthetic pass inference (#195)
  - [ ] New `_build_synthetic_pass_list()` in `query_service.py`
  - [ ] Marker stack grouping with engine marker filtering
  - [ ] Fallback in `get_pass_hierarchy()` when `_build_pass_list()` returns empty
  - [ ] Tests: synthetic pass from marker stacks, empty capture, mixed markers

## Wave 3 (depends on T3)

- [ ] **T6**: `rdc unused-targets` command (#196)
  - [ ] New `commands/unused.py` — Click command with TSV/JSON/quiet output
  - [ ] New handler in `query.py` or new `handlers/unused.py`
  - [ ] Service function: swapchain reachability → wave-based pruning
  - [ ] Register in `cli.py`
  - [ ] Tests: command, handler, service (empty/no-unused/multi-wave scenarios)
