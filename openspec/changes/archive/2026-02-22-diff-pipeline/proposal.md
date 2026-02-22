# Proposal: diff-pipeline

## Summary

Implement `rdc diff <a.rdc> <b.rdc> --pipeline <marker_path>` to compare
pipeline state at a matching draw call between two captures.

## Motivation

`rdc diff --draws` identifies *which* draw calls changed; `--pipeline` answers
*how* they changed at the GPU pipeline level. An agent debugging a visual
regression can pinpoint whether the root cause is a blend mode, a rasterizer
setting, or a viewport difference — without opening the GUI.

This is Phase 3B (Diff primitives) as defined in `规划/Roadmap.md`.

## Design

### Marker-based lookup (not EID)

`--pipeline GBuffer/Floor` accepts a **marker_path**, not an EID. EIDs are
per-capture and not portable across captures. The alignment infrastructure
(`src/rdc/diff/alignment.py`) maps marker_path → EID pair using LCS alignment.

### Flow

```
1. query_both(ctx, "draws", {})
       → draws_a: list[dict], draws_b: list[dict]
2. build_draw_records(draws_a) → list[DrawRecord]
   build_draw_records(draws_b) → list[DrawRecord]
3. align_draws(records_a, records_b) → aligned pairs
4. find_pair(aligned, marker_path) → (DrawRecord_a, DrawRecord_b)
       error exit 2 if not found in either capture
5. query_each_sync(ctx, calls_a, calls_b)
       → each side gets its own EID in params (2×13 threads)
       calls_a = [("pipe_topology", {"eid": eid_a}), ...]
       calls_b = [("pipe_topology", {"eid": eid_b}), ...]
6. diff_sections(results_a, results_b) → list[PipeFieldDiff]
7. render output (TSV / JSON)
```

### New helper: `query_each_sync` in `diff_service.py`

`query_both_sync` sends identical params to both daemons. Pipeline diff needs
**per-side EIDs** (eid_a ≠ eid_b). Add `query_each_sync`:

```python
def query_each_sync(
    ctx: DiffContext,
    calls_a: list[tuple[str, dict[str, Any]]],
    calls_b: list[tuple[str, dict[str, Any]]],
    *,
    timeout_s: float = 30.0,
) -> tuple[list[dict[str, Any] | None], list[dict[str, Any] | None], str]:
    """Send N calls to daemon A and M calls to daemon B concurrently."""
```

This is the only addition to `diff_service.py`.

### `draws` RPC response schema

`_handle_draws` returns:
```json
{
    "draws": [
        {"eid": 12, "type": "Draw", "triangles": 3, "instances": 1,
         "pass": "GBuffer", "marker": "GBuffer/Floor"}
    ],
    "summary": "..."
}
```

`marker` maps to `DrawRecord.marker_path`. `shader_hash` and `topology` are not
in the `draws` response — default to `""` for alignment (marker-based path does
not require them).

### Pipeline sections queried

All 13 `pipe_*` methods, each called with `{"eid": <eid>}`:

| Section key      | RPC method          | Top-level result key  |
|------------------|---------------------|-----------------------|
| `topology`       | `pipe_topology`     | `topology`            |
| `viewport`       | `pipe_viewport`     | `x/y/width/height/...`|
| `scissor`        | `pipe_scissor`      | `x/y/width/height/...`|
| `blend`          | `pipe_blend`        | `blends` (list)       |
| `stencil`        | `pipe_stencil`      | `front/back` (dicts)  |
| `vinputs`        | `pipe_vinputs`      | `inputs` (list)       |
| `samplers`       | `pipe_samplers`     | `samplers` (list)     |
| `vbuffers`       | `pipe_vbuffers`     | `vbuffers` (list)     |
| `ibuffer`        | `pipe_ibuffer`      | flat dict fields      |
| `push_constants` | `pipe_push_constants` | `push_constants` (list) |
| `rasterizer`     | `pipe_rasterizer`   | flat dict fields      |
| `depth_stencil`  | `pipe_depth_stencil`| flat dict fields      |
| `msaa`           | `pipe_msaa`         | flat dict fields      |

### Diffing strategy

Each section result is a dict (or list of dicts). Fields are compared
recursively by value after stripping the `eid` key.

- Flat sections (topology, viewport, scissor, ibuffer, rasterizer,
  depth_stencil, msaa): field-by-field scalar comparison.
- List sections (blend, vinputs, samplers, vbuffers, push_constants): compare
  element-by-element by index; flag length mismatch as a change.
- Nested dicts (stencil front/back): compare sub-fields.

A `PipeFieldDiff` carries: `section`, `field`, `value_a`, `value_b`.

Only changed fields are shown by default; `--verbose` shows all fields.

### Output format

Default (TSV):
```
SECTION         FIELD           A                       B
topology        topology        TriangleList            TriangleStrip   <- changed
rasterizer      cullMode        Back                    None            <- changed
```

`--json`: JSON array of `PipeFieldDiff` objects (all fields, with `changed` bool).

### Error handling

| Scenario                         | Exit |
|----------------------------------|------|
| No differences found             | 0    |
| Differences found                | 1    |
| Daemon startup failed            | 2    |
| Draws fetch failed (both daemons)| 2    |
| Marker not found in capture A    | 2    |
| Marker not found in capture B    | 2    |
| Pipe section RPC failed          | warn to stderr, section skipped |

Marker-not-found message: `error: marker 'GBuffer/Floor' not found in <capture>`

### Repeated marker handling

If a marker appears more than once, the CLI accepts `marker_path[N]` syntax
(0-indexed) matching the `sequential_index` from `make_match_keys`. Without
index suffix, index 0 is used and a warning is printed if duplicates exist.

## Files

### New

- `src/rdc/diff/pipeline.py` — `build_draw_records`, `find_aligned_pair`,
  `diff_pipeline_sections`, `PipeFieldDiff`, `render_pipeline_tsv`,
  `render_pipeline_json`
- `tests/unit/test_diff_pipeline.py` — unit tests

### Modified

- `src/rdc/commands/diff.py` — remove `"pipeline"` from `_MODE_STUBS`; add
  handler call dispatching to `pipeline.py` logic
- `src/rdc/services/diff_service.py` — add `query_each_sync` helper

## Not in scope

- Diffing compute pipeline (only graphics pipeline sections covered)
- Cross-API comparison (both captures must use the same API)
- VFS route for pipeline diff output
- `--shortstat` for pipeline mode
- GPU integration test (unit-only for this feature; real GPU test deferred)
