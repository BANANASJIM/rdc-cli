# Phase 8: Pass Analysis Enhancement — Tasks

## Wave 1 (parallel, no dependencies)

- [ ] **T1+T2**: `rdc passes` surface existing data + load/store extraction
  - [ ] `_parse_load_store_ops(begin_name, end_name)` in `query_service.py`
    - Regex: `r'(C|D|S|DS)=([^,)]+)'`
    - Returns `list[tuple[str, str]]` to handle multi-RT duplicate keys
  - [ ] Integrate into `_build_pass_list()` — attach load_ops/store_ops per pass
  - [ ] `get_pass_hierarchy()` — stop discarding dispatches/triangles/eid range/load_store
  - [ ] `_handle_passes()` — pass through new fields
  - [ ] `passes_cmd` — add TSV columns DISPATCHES, TRIANGLES, BEGIN_EID, END_EID
  - [ ] Tests: regex parsing (Clear/Load/Store/Don't Care/None/DS= compound key)
  - [ ] Tests: multi-RT duplicate C= keys → list accumulation (not dict overwrite)
  - [ ] Tests: dynamic rendering (`vkCmdBeginRendering`)
  - [ ] Tests: update existing passes tests for new columns

- [ ] **T7**: `rdc stats` Largest Resources section
  - [ ] `_handle_stats()` — collect top N resources by byte size
  - [ ] `stats_cmd` — render third section
  - [ ] Tests: stats output with largest resources
  - [ ] Tests: fewer than 5 resources → show all available

## Wave 2 (depends on Wave 1)

- [ ] **T3**: `rdc passes --deps --table` per-pass I/O
  - [ ] `build_pass_deps()` — return per_pass list with reads/writes/load/store
  - [ ] `_handle_pass_deps()` — include per_pass in response
  - [ ] `_passes_deps` — new `--table` flag rendering (mutually exclusive with --dot/--graph)
  - [ ] `--json` response includes both edges and per_pass
  - [ ] Tests: table output format, json schema, mutual exclusion errors

- [ ] **T4**: `rdc pass <name>` attachment detail
  - [ ] `_handle_pass()` — enrich existing target dicts with name/format/dims from tex_map
  - [ ] `_handle_pass()` — include per-attachment-type load/store from pass data (T1+T2)
  - [ ] `pass_cmd` — render enriched attachment blocks
  - [ ] Tests: pass detail with attachment info, unknown resource fallback

- [ ] **T5**: GL/GLES/D3D11 synthetic pass inference (#195)
  - [ ] `mock_renderdoc.py` — add `outputs: list[ResourceId]` (8 elements, default all-zero) and `depthOut: ResourceId` (default zero) to `ActionDescription`
  - [ ] New `_build_synthetic_pass_list(actions)` in `query_service.py`
  - [ ] RT-switch detection: `tuple(int(x) for x in a.outputs) + (int(a.depthOut),)` change = pass boundary
  - [ ] Ignore zero-valued ResourceId slots (unused RT slots ≠ pass boundary)
  - [ ] Pass naming: marker stack primary, RT-info-based `_friendly_pass_name()` fallback
  - [ ] `_SYNTHETIC_MARKER_IGNORE` filter for engine-internal markers
  - [ ] Fallback in `get_pass_hierarchy()` when `_build_pass_list()` returns empty
  - [ ] Tests: RT-switch grouping, marker naming, empty capture, zero-padded outputs equality, D3D11

## Wave 3 (depends on T3 for T6, depends on T5 for T8)

- [ ] **T6**: `rdc unused-targets` command (#196)
  - [ ] New `commands/unused.py` — Click command with TSV/JSON/quiet output
  - [ ] New `handlers/unused.py` — daemon handler
  - [ ] Register handler in handler dispatch (HANDLERS dict or `_all_handlers()`)
  - [ ] Service function in `query_service.py`: swapchain reachability → wave-based pruning
  - [ ] Register command in `cli.py`
  - [ ] Tests: command, handler, service (empty/no-unused/multi-wave scenarios)

- [ ] **T8**: `rdc passes --switches` — event-level RT switch detection
  - [ ] Reuse T5's `(outputs[0:8], depthOut)` detection, scoped within each pass
  - [ ] `_count_rt_switches(actions, begin_eid, end_eid)` in `query_service.py`
  - [ ] `--switches` flag on `passes_cmd` — add RT_SWITCHES column
  - [ ] `--json` includes `rt_switches: [{eid, from_targets, to_targets}]` per pass
  - [ ] Handler: iterate pass actions, compare consecutive RT tuples
  - [ ] Tests: pass with 0 switches, pass with multiple switches, synthetic pass switches
