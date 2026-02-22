# Fix: phase2.7-bug-filters

## Summary

Five bugs were discovered during real-world testing with Vulkan captures (hello_triangle,
render_passes, hdr, msaa, subpasses). All bugs relate to filtering and display correctness
in `rdc shaders`, `rdc draws`, and pipeline state output. The fixes are surgical: no new
public API, no new commands, no schema changes. Each fix is self-contained and correctable
in isolation.

The root causes are: one filter param silently ignored in the daemon, one filter comparing
incompatible name spaces (API name vs. semantic name), one summary computed from the wrong
dataset, one pass name left as raw API text when no markers exist, and one SWIG enum
serialized as a raw integer instead of its name string.

## Problem

### Bug 1: `rdc shaders --stage` filter silently ignored

`src/rdc/daemon_server.py` lines 358-366 handle the `"shaders"` method. The handler calls
`shader_inventory(pipe_states)` and returns the full unfiltered row list. It never reads
`params.get("stage")` even though `src/rdc/commands/pipeline.py` lines 317-319 always
forwards the `stage` param when the user passes `--stage`. The CLI option has no effect.

### Bug 2: `rdc draws --pass` filter never matches semantic pass names

`src/rdc/services/query_service.py` lines 142-145 implement `filter_by_pass`. It compares
`a.pass_name` (set by `walk_actions` at line 100 from `BeginPass` API names like
`"vkCmdBeginRenderPass(C=Load, D=Clear)"`) against the user-supplied name string.

`_build_pass_list` (lines 526-582) builds a richer pass list using marker group names
(e.g. `"Opaque objects"`, `"UI"`). The user naturally types these semantic names after
seeing `rdc passes` output, but `filter_by_pass` compares against the raw API name, so
no draw ever matches.

`src/rdc/daemon_server.py` lines 1858-1860 call `filter_by_pass(flat, pass_name)` without
passing `actions` or `sf`, so the EID-range fallback path cannot be taken.

### Bug 3: `rdc draws` summary always uses unfiltered stats

`src/rdc/daemon_server.py` lines 1878-1883 build the summary string from `all_stats`,
which is computed from the unfiltered `all_flat` list (line 1856). When `--pass` or
`--type` filters are active, the summary reports the total for the entire frame rather
than for the filtered subset. Users see a mismatch between the number of rows returned
and the count in the summary line.

### Bug 4: Pass names are raw API text when no debug markers exist

`src/rdc/services/query_service.py` lines 575-576 call `_window_stats(a, window, sf)`,
which sets `"name"` directly from `begin.GetName(sf)` (line 464). When no marker groups
are present (common in unoptimized or stripped captures), the name propagated to `rdc
passes` output and used by `filter_by_pass` is the raw Vulkan API string
`"vkCmdBeginRenderPass(C=Load, D=Clear)"`. This is neither readable nor stable across
driver versions.

### Bug 5: TOPOLOGY field displays a raw integer

`src/rdc/services/query_service.py` line 326 sets `"topology"` with
`str(pipe_state.GetPrimitiveTopology())`. For SWIG-wrapped enums returned by the real
RenderDoc Python API, `str()` produces `"3"` instead of `"TriangleList"`. The same enum
pattern is handled correctly elsewhere in the codebase using
`getattr(v, "name", str(v))`.

## Fix Design

### Fix 1: Apply stage post-filter in shaders handler

In `src/rdc/daemon_server.py`, after `rows = shader_inventory(pipe_states)` (line 365),
read `params.get("stage")` and filter `rows` in-place:

```python
stage_filter = params.get("stage")
if stage_filter:
    stage_filter = stage_filter.lower()
    rows = [r for r in rows if stage_filter in r["stages"].lower().split(",")]
```

The `"stages"` field in each row is a comma-separated string produced by
`shader_inventory` (e.g. `"vs,ps"`). Lowercasing both sides makes the comparison
case-insensitive and consistent with the CLI's normalization.

### Fix 2: EID-range pass filtering via `_build_pass_list`

Change `filter_by_pass` signature in `src/rdc/services/query_service.py` to accept
optional `actions` and `sf` parameters:

```python
def filter_by_pass(
    flat: list[FlatAction],
    pass_name: str,
    actions: list[Any] | None = None,
    sf: Any = None,
) -> list[FlatAction]:
    if actions is not None:
        passes = _build_pass_list(actions, sf)
        target = next((p for p in passes if p["name"].lower() == pass_name.lower()), None)
        if target:
            return [a for a in flat if target["begin_eid"] <= a.eid <= target["end_eid"]]
    lower = pass_name.lower()
    return [a for a in flat if a.pass_name.lower() == lower]
```

Update the call site in `src/rdc/daemon_server.py` lines 1858-1860 to pass the action
tree and string factory:

```python
if pass_name:
    actions = state.adapter.get_root_actions()
    sf = state.structured_file
    flat = filter_by_pass(flat, pass_name, actions=actions, sf=sf)
```

### Fix 3: Summary from filtered stats

In `src/rdc/daemon_server.py` lines 1855-1883, compute summary from the pass-filtered
action list (before `filter_by_type`). The key insight: `flat` at line 1857 is already
filtered to draw-type only, so `aggregate_stats(flat)` would always show 0 dispatches
and 0 clears. Instead, apply pass filter to `all_flat` first, then compute stats:

```python
all_flat = _get_flat_actions(state)
pass_name = params.get("pass")
if pass_name:
    actions = state.adapter.get_root_actions()
    sf = state.structured_file
    all_flat = filter_by_pass(all_flat, pass_name, actions=actions, sf=sf)
stats = aggregate_stats(all_flat)
flat = filter_by_type(all_flat, "draw")
# ... sort/limit on flat ...
summary = (
    f"{stats.total_draws} draw calls "
    f"({stats.indexed_draws} indexed, "
    f"{stats.dispatches} dispatches, "
    f"{stats.clears} clears)"
)
```

This ensures summary counts dispatches/clears within the filtered pass, not just draws.

### Fix 4: Friendly pass names when no debug markers

Add `_friendly_pass_name(api_name: str, index: int) -> str` to
`src/rdc/services/query_service.py`. This helper is called inside
`_build_pass_list_recursive` for any pass whose name was taken from the raw API name
rather than a marker group:

```python
def _friendly_pass_name(api_name: str, index: int) -> str:
    color_count = api_name.count("C=")
    has_depth = "D=" in api_name
    parts = []
    if color_count:
        parts.append(f"{color_count} Target{'s' if color_count > 1 else ''}")
    if has_depth:
        parts.append("Depth")
    suffix = f" ({' + '.join(parts)})" if parts else ""
    return f"Colour Pass #{index + 1}{suffix}"
```

Apply in `_window_stats` and the `_subtree_stats(a, sf)` call-site at line 558 where
no marker groups exist: replace the raw `name` with `_friendly_pass_name(name, index)`
where `index` is the zero-based pass number within the current recursive context.

### Fix 5: Topology enum name via getattr

In `src/rdc/services/query_service.py` line 326, change:

```python
"topology": str(pipe_state.GetPrimitiveTopology()),
```

to:

```python
"topology": getattr(pipe_state.GetPrimitiveTopology(), "name", str(pipe_state.GetPrimitiveTopology())),
```

This is consistent with the existing pattern used throughout the codebase for SWIG enums
(e.g. `pipelineType`, `AddressMode`).

## Scope

### In scope
- `src/rdc/daemon_server.py`: Fix 1 (shaders stage filter), Fix 2 call-site (pass actions arg), Fix 3 (summary from filtered stats)
- `src/rdc/services/query_service.py`: Fix 2 `filter_by_pass` signature, Fix 4 `_friendly_pass_name` helper, Fix 5 topology enum name
- Unit tests covering all 5 fixes (mock-only, no GPU required)
- GPU regression tests on `hello_triangle.rdc` confirming each fix

### Out of scope
- Any new CLI options or commands
- Changes to JSON-RPC schema or VFS routes
- Pass dependency graphs or diff features
- Changes to `rdc passes` display format beyond name friendliness
