# Phase 8: Pass Analysis Enhancement — Proposal

## Motivation

External PR #193 proposed a `rdc tbr` command for TBR optimization triage. While the
use case is real (mobile GPU performance analysis), the implementation duplicates
existing `pass_deps` logic and adds a top-level command that overlaps with `rdc passes`.

Investigation revealed that the existing pass analysis commands fall significantly
short of the design spec:

| Command | Current | Design spec gap |
|---------|---------|-----------------|
| `rdc passes` | NAME, DRAWS (2 cols) | Missing DISPATCHES, TRIANGLES, EID range, attachments, load/store |
| `rdc passes --deps` | SRC, DST, RESOURCES (edges only) | Missing per-pass READS/WRITES/LOAD_STORE table |
| `rdc pass <name>` | Bare resource IDs | Missing name, format, dimensions, load/store per attachment |
| `rdc stats` | Per-pass breakdown | Missing "Largest Resources" section |

Bridging these gaps makes the TBR analysis use case solvable with existing commands
and Unix pipes — no new top-level command needed.

## Key discovery: load/store ops in action names

RenderDoc encodes loadOp/storeOp in the BeginPass/EndPass action name string:

```
vkCmdBeginRenderPass(C=Clear, D=Load)
vkCmdEndRenderPass(C=Store, DS=Don't Care)
```

`_build_pass_list()` already captures these names. A regex extracts the ops — no
structured data parsing required for the common case.

## Design

### T1: `rdc passes` — surface existing data

`_build_pass_list()` already computes dispatches, triangles, begin_eid, end_eid.
`get_pass_hierarchy()` currently discards all of them. Stop discarding.

Default TSV adds columns: DISPATCHES, TRIANGLES, BEGIN_EID, END_EID.
`--json` includes load/store ops.

### T2: load/store extraction

New `_parse_load_store_ops(begin_name, end_name)` function. Regex: `r'([CDS]+)=([^,)]+)'`.
Attach `load_ops`/`store_ops` dicts to each pass in `_build_pass_list()`.

### T3: `rdc passes --deps --table` — per-pass I/O view

`build_pass_deps()` already computes per-pass `reads[i]`/`writes[i]` sets but discards
them after computing edges. Return them alongside edges.

New `--table` flag renders the design spec's PASS/READS/WRITES/LOAD_STORE table.
Edge view remains the default. `--json` always includes both.

### T4: `rdc pass <name>` — attachment detail

Enrich each attachment with name, format, dimensions from `state.tex_map`.
Include load/store from T2 (aggregated level, not per-attachment).

### T5: GL/GLES synthetic pass inference (#195)

New `_build_synthetic_pass_list()` when `_build_pass_list()` returns empty.
Infers passes from marker stacks. Does NOT modify `walk_actions()`.
Fallback at `get_pass_hierarchy()` level only.

### T6: `rdc unused-targets` — new command (#196)

Separate command — output entity is **resource**, not pass. Different schema requires
different command (Unix: `perf report` vs `perf annotate`).

Reuses `build_pass_deps()` per-pass reads/writes. Swapchain images as roots,
reverse reachability marks live resources, remainder is unused.
Recursive wave pruning. `-q` outputs resource IDs only (pipeable).

### T7: `rdc stats` — Largest Resources section

Design spec's third section. Iterate resources, sort by byte size, top N.

## Risks

- **load/store regex**: aggregated ops (`C=Clear`) don't distinguish per-attachment.
  Per-attachment requires SDChunk parsing — deferred as stretch goal.
- **GL/GLES captures**: no BeginPass/EndPass → no load/store data. T5 provides pass
  structure but load/store columns will be empty. Acceptable.
- **Performance**: T3 adds per-pass resource sets to the pass_deps response. For
  captures with many resources this may increase response size. Mitigate with
  `--table` flag (only compute when requested).

## Non-goals

- `rdc tbr` top-level command
- Modifying `walk_actions()` global behavior
- SDChunk deep parsing for per-attachment loadOp/storeOp
- Tile-level analysis (requires vendor-specific tools)
