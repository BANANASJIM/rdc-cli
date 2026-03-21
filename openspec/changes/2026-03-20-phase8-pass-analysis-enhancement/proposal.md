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

New `_parse_load_store_ops(begin_name, end_name)` function. Regex: `r'(C|D|S|DS)=([^,)]+)'`.
Returns `load_ops`/`store_ops` as `list[dict]` (not dict — multi-RT captures repeat
`C=` keys, e.g., `C=Store, C=Don't Care`). Attach to each pass in `_build_pass_list()`.

Note: `C`/`D`/`S`/`DS` are per-attachment-type keys (C=Color, D=Depth, S=Stencil),
not per-individual-color-attachment. A single `C=Clear` may apply to all color targets.

### T3: `rdc passes --deps --table` — per-pass I/O view

`build_pass_deps()` already computes per-pass `reads[i]`/`writes[i]` sets but discards
them after computing edges. Return them alongside edges.

New `--table` flag renders the design spec's PASS/READS/WRITES/LOAD_STORE table.
Edge view remains the default. `--json` always includes both.
`--table` is mutually exclusive with `--dot`/`--graph` (UsageError if combined).

### T4: `rdc pass <name>` — attachment detail

Enrich each attachment with name, format, dimensions from `state.tex_map`.
Include per-attachment-type load/store from T2 (C/D/S/DS keys, not per-individual-
color-attachment since a single `C=Clear` may apply to all color targets).

### T5: GL/GLES/D3D11 synthetic pass inference (#195)

Key discovery: `ActionDescription.outputs[]` (8-tuple color RTs) and `depthOut` are
**API-agnostic** fields populated on all APIs (Vulkan/GL/GLES/D3D11/D3D12/Metal).
RenderDoc comment: "very coarse bucketing of actions into similar passes by their outputs."

New `_build_synthetic_pass_list(actions)` using **RT-switch hybrid approach**:
1. Primary grouping: `(outputs[0:8], depthOut)` tuple change = pass boundary
2. Pass naming: marker stack (nearest PushMarker) as primary, `_friendly_pass_name()`
   from RT info as fallback. Filter `_SYNTHETIC_MARKER_IGNORE` engine-internal markers
3. GL/GLES load/store: marked `"unknown"` (no BeginPass name to regex)
4. Trigger: `_build_pass_list()` returns empty + action tree has draw calls

Does NOT modify `walk_actions()`. Fallback at `get_pass_hierarchy()` level only.

Prerequisites: `mock_renderdoc.py` must add `outputs: list[ResourceId]` (8 elements,
default all-zero) and `depthOut: ResourceId` (default zero) to `ActionDescription`.
RT tuple comparison: `tuple(int(x) for x in a.outputs) + (int(a.depthOut),)`.

### T6: `rdc unused-targets` — new command (#196)

Separate command — output entity is **resource**, not pass. Different schema requires
different command (Unix: `perf report` vs `perf annotate`).

Reuses `build_pass_deps()` per-pass reads/writes. Swapchain images as roots,
reverse reachability marks live resources, remainder is unused.
Recursive wave pruning. `-q` outputs resource IDs only (pipeable).

### T7: `rdc stats` — Largest Resources section

Design spec's third section. Iterate resources, sort by byte size, top N.

### T8: `rdc passes --switches` — event-level RT switch detection

Pass-level analysis (T1-T7) assumes BeginPass/EndPass = hardware boundaries. This is
true for Vulkan, but misses intra-pass RT switches in two scenarios:
1. Vulkan subpasses that change attachments within a single render pass
2. T5-produced synthetic passes that span multiple RT switches (e.g., SSAO pass with
   intermediate blur targets)

FrankyLin2's core insight (#194): "logical pass ≠ hardware pass" — TBR flush costs
come from RT switches, not pass boundaries.

Reuses T5's `(outputs[0:8], depthOut)` detection primitive, but scoped **within**
each pass rather than globally:
- For each pass, iterate its actions and detect RT tuple changes
- `rdc passes --switches` adds RT_SWITCHES column (count per pass)
- `--json` includes `rt_switches: [{eid, from_targets, to_targets}]` per pass
- Passes with 0 switches are TBR-friendly; high counts indicate flush risk

This is the pass-scoped version of PR #193's segment analysis — no new command needed.

## Risks

- **load/store regex**: aggregated ops (`C=Clear`) don't distinguish per-attachment.
  Per-attachment requires SDChunk parsing — deferred as stretch goal.
- **GL/GLES captures**: no BeginPass/EndPass → no load/store data. T5 provides pass
  structure but load/store columns will be empty. Acceptable.
- **Performance**: T3 adds per-pass resource sets to the pass_deps response. For
  captures with many resources this may increase response size. Mitigate with
  `--table` flag (only compute when requested).
- **T8 replay cost**: detecting intra-pass RT switches requires reading `outputs[]`/
  `depthOut` from action objects (already in memory after action tree walk — no extra
  replay seek). Cost is O(actions), same as `walk_actions()`.

## Non-goals

- `rdc tbr` top-level command
- Modifying `walk_actions()` global behavior
- SDChunk deep parsing for per-attachment loadOp/storeOp
- Tile-level analysis (requires vendor-specific tools)
