# Proposal: Phase 5 — tex-stats

## Problem

Inspecting texture value ranges requires exporting the texture and running an
external tool. There is no built-in way to answer "what are the min/max values
in this texture?" or "how are values distributed across channels?" directly from
the CLI.

## Solution

Add `rdc tex-stats <resource_id> [eid]` command that:
1. Calls `GetMinMax` to return per-channel min/max as a tab-separated table.
2. Optionally calls `GetHistogram` per channel to return 256-bucket bucket
   counts when `--histogram` is requested.
3. Supports `--json` for machine-readable output.

## Design

### CLI Signature

```
rdc tex-stats <resource_id> [eid] [--mip N] [--slice N] [--histogram] [--json]
```

| Argument / Option | Type | Default | Description |
|---|---|---|---|
| `resource_id` | int | required | Texture resource ID |
| `eid` | int | optional | Event ID (defaults to current) |
| `--mip` | int | 0 | Mip level |
| `--slice` | int | 0 | Array slice |
| `--histogram` | flag | off | Append 256-bucket histogram |
| `--json` | flag | off | JSON output |

### Default Output (min/max table)

```
CHANNEL	MIN	MAX
R	0.0000	1.0000
G	0.0000	0.8500
B	0.0100	0.9200
A	1.0000	1.0000
```

### Histogram Output (`--histogram`)

```
BUCKET	R	G	B	A
0	150	200	100	0
1	120	180	90	0
...
255	10	5	8	1024
```

### JSON Output (`--json`)

```json
{
  "id": 42,
  "eid": 100,
  "mip": 0,
  "slice": 0,
  "min": {"r": 0.0, "g": 0.0, "b": 0.01, "a": 1.0},
  "max": {"r": 1.0, "g": 0.85, "b": 0.92, "a": 1.0},
  "histogram": [
    {"bucket": 0, "r": 150, "g": 200, "b": 100, "a": 0},
    ...
  ]
}
```

`histogram` key is absent unless `--histogram` is passed.

### Handler: `_handle_tex_stats` in `src/rdc/handlers/texture.py`

```python
def _handle_tex_stats(request_id, params, state):
    # 1. Guard: adapter, rd
    # 2. Resolve texture from tex_map
    # 3. _set_frame_event if eid provided
    # 4. Build Subresource(mip, slice)
    # 5. comp_type = rd.CompType.Typeless
    # 6. min_val, max_val = controller.GetMinMax(tex.resourceId, sub, comp_type)
    # 7. Extract floatValue[0..3] for r/g/b/a
    # 8. If histogram requested:
    #    For each channel index (0-3):
    #      buckets = controller.GetHistogram(tex.resourceId, sub, comp_type,
    #                  min_f, max_f, channel_mask)
    #      Accumulate per channel into 256-element list
    # 9. Return result dict
```

`channel_mask` for channel `i` is `[i==0, i==1, i==2, i==3]`.
`GetHistogram` returns a flat list of 256 bucket counts for the masked
channel(s). Calling once per channel with a single-channel mask isolates each
channel's distribution.

#### Error cases

| Condition | JSON-RPC error code | Message |
|---|---|---|
| `state.adapter is None` | -32002 | `"no replay loaded"` |
| `state.rd is None` | -32002 | `"renderdoc module not available"` |
| texture ID not in `tex_map` | -32001 | `"texture {id} not found"` |
| eid out of range | -32002 | from `_set_frame_event` |

### Command: `src/rdc/commands/tex_stats.py`

```python
@click.command("tex-stats")
@click.argument("resource_id", type=int)
@click.argument("eid", required=False, type=int)
@click.option("--mip", default=0, type=int)
@click.option("--slice", "array_slice", default=0, type=int)
@click.option("--histogram", is_flag=True)
@click.option("--json", "use_json", is_flag=True)
def tex_stats_cmd(resource_id, eid, mip, array_slice, histogram, use_json):
    params = {"id": resource_id, "mip": mip, "slice": array_slice,
              "histogram": histogram}
    if eid is not None:
        params["eid"] = eid
    result = _daemon_call("tex_stats", params)
    if use_json:
        write_json(result)
        return
    # Print CHANNEL/MIN/MAX table
    # If histogram in result: print BUCKET/R/G/B/A table
```

### Mock additions in `tests/mocks/mock_renderdoc.py`

Add to `MockReplayController.__init__`:
```python
self._min_max_map: dict[int, tuple[PixelValue, PixelValue]] = {}
self._histogram_map: dict[tuple[int, int], list[int]] = {}
# Key: (resource_id, channel_index) where 0=R, 1=G, 2=B, 3=A
```

Add methods:
```python
def GetMinMax(self, tex_id, sub, comp_type):
    rid = int(tex_id)
    return self._min_max_map.get(rid, (PixelValue(), PixelValue()))

def GetHistogram(self, tex_id, sub, comp_type, min_val, max_val, channels):
    rid = int(tex_id)
    ch = next((i for i, c in enumerate(channels) if c), 0)
    return self._histogram_map.get((rid, ch), [0] * 256)
```

Note: `_make_subresource` from `_helpers.py` only supports `mip`, not `slice`.
The handler must build the Subresource manually:
```python
sub = rd.Subresource()
sub.mip = mip
sub.slice = array_slice
sub.sample = 0
```

## Files Changed

| File | Change |
|---|---|
| `src/rdc/commands/tex_stats.py` | NEW — command |
| `src/rdc/handlers/texture.py` | ADD `_handle_tex_stats`, register in `HANDLERS` |
| `src/rdc/cli.py` | ADD `tex_stats_cmd` import and `main.add_command` |
| `tests/mocks/mock_renderdoc.py` | ADD `_min_max_map`, `_histogram_map`, `GetMinMax`, `GetHistogram` |
| `tests/unit/test_tex_stats.py` | NEW — unit tests |
| `tests/integration/test_daemon_handlers_real.py` | ADD GPU integration tests |

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| `GetHistogram` SWIG channel mask type | Use plain Python `list[bool]`; if rejected at runtime, wrap with `rdcfixedarray` |
| MSAA textures unsupported by `GetMinMax` | Return error `-32001` with `"MSAA textures not supported"` when `tex.msSamp > 1` |
| Empty texture (width/height == 0) | Propagate API error; do not crash |
