# Phase 8: Pass Analysis Enhancement — Test Plan

## Unit tests

### T1: passes surface existing data
- `rdc passes` TSV output includes DISPATCHES, TRIANGLES, BEGIN_EID, END_EID columns
- `rdc passes --json` includes all fields per pass
- `rdc passes --no-header` omits header row
- `rdc passes --quiet` outputs only pass names
- `rdc passes --jsonl` outputs one JSON object per line per pass
- Backward compat: existing tests still pass with new columns

### T2: load/store extraction
- `_parse_load_store_ops("vkCmdBeginRenderPass(C=Clear, D=Load)", "vkCmdEndRenderPass(C=Store, DS=Don't Care)")` → `{"load": {"C": "Clear", "D": "Load"}, "store": {"C": "Store", "DS": "Don't Care"}}`
- Dynamic rendering: `vkCmdBeginRendering(C=Clear, D=Clear)` format
- Missing end pass name → store_ops is empty dict
- No load/store in name (GL/GLES) → both dicts empty
- Aggregated "Different load ops" → preserved as-is
- Edge case: `DS=` combined key vs separate `D=`/`S=` keys

### T3: passes --deps --table
- Default output unchanged (SRC/DST/RESOURCES edges)
- `--table` outputs PASS/READS/WRITES/LOAD/STORE per pass
- `--table --json` includes per_pass array alongside edges
- `--table` + `--dot` → UsageError
- `--table` + `--graph` → UsageError
- Empty capture → empty table
- Single pass with no deps → pass row with empty reads

### T4: pass detail attachment enrichment
- `rdc pass GBuffer` includes resource name, format, dimensions per attachment
- `rdc pass GBuffer --json` includes load/store fields
- Attachment with unknown resource ID → graceful fallback (ID only)
- Pass with no color attachments → only depth shown
- Pass with no depth → depth section omitted

### T5: synthetic pass inference
- GL capture with marker stacks → synthetic passes inferred
- Vulkan capture with BeginPass/EndPass → `_build_pass_list()` used (no fallback)
- Empty action tree → empty pass list
- Nested markers → outermost non-filtered marker used as pass name
- Engine markers (Unity RenderLoop.Draw) → filtered out

### T6: unused-targets
- No unused targets → exit 0, empty output
- One unused RT → single row with resource ID, name, written_by, reason
- Multi-wave pruning: wave 1 removes leaf, wave 2 removes newly-orphaned
- Swapchain image → always live (never reported)
- Depth-only pass feeding nothing → conservative keep (not reported)
- `--json` → structured output with waves
- `-q` → one resource ID per line, no header

### T7: stats largest resources
- `rdc stats` includes "Largest Resources" section
- Top 5 resources by byte size
- Resource with zero byte size → excluded
- `rdc stats --json` includes `largest_resources` array

## Integration tests

- `pixi run rdc open tests/fixtures/vkcube.rdc` → `rdc passes` shows new columns
- `rdc passes --deps --table` shows per-pass I/O for vkcube
- `rdc pass <name>` shows enriched attachments
- `rdc unused-targets` runs without error

## Manual tests

- Verify load/store columns with a known Vulkan capture
- Verify synthetic pass inference with a GL/GLES capture (if fixture available)
- Verify `rdc passes --deps --table | grep` pipeline works
- Verify `rdc unused-targets -q | xargs -I{} rdc usage {}` pipeline
