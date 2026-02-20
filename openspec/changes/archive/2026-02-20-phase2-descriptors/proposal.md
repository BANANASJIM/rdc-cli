# OpenSpec #7: phase2-descriptors

## Summary

Expose all used descriptor bindings for a draw call via a new VFS leaf node
`/draws/<eid>/descriptors`, returning a flat TSV of active resource bindings.

## Motivation

Debugging resource binding errors (wrong texture bound, missing sampler, stale UAV) requires
knowing which descriptors are actually active at a given draw. The existing pipeline state
routes expose IA layout and blend state but not the bound resources. `GetAllUsedDescriptors`
provides a single flat list covering all stages and all descriptor types in one call, making
this the lowest-cost path to full binding visibility.

## Design

### VFS Route

| Path | Kind | Handler | API |
|------|------|---------|-----|
| `/draws/<eid>/descriptors` | leaf | `descriptors` | `pipe_state.GetAllUsedDescriptors(True)` |

The leaf hangs directly under the existing `/draws/<eid>` dir. Static node registered in
`build_vfs_skeleton` (like `postvs`, `vbuffer`). No `populate_draw_subtree` change needed.
Access via `rdc cat /draws/<eid>/descriptors`.

### Daemon Handler

Method name: `descriptors`

Steps (same pattern as `pipe_topology`, `pipe_viewport`, etc.):
1. Validate `state.adapter is not None` (else `-32002`)
2. `_set_frame_event(state, eid)` (else `-32002`)
3. `pipe_state = state.adapter.get_pipeline_state()`
4. `used = pipe_state.GetAllUsedDescriptors(True)` — `onlyUsed=True` filters statically-unused
5. Format each `UsedDescriptor` into a response dict
6. Return `{"eid": eid, "descriptors": [...]}`

### Data Shape

`GetAllUsedDescriptors` returns `UsedDescriptor[]`. Each element has three nested objects:

| Object | Fields extracted |
|--------|----------------|
| `.access` (DescriptorAccess) | `stage.name`, `type.name`, `index`, `arrayElement` |
| `.descriptor` (Descriptor) | `resource` → `int()`, `format.Name()`, `byteSize` |
| `.sampler` (SamplerDescriptor) | `addressU`, `addressV`, `addressW`, `filter`, `compareFunction`, `minLOD`, `maxLOD`, `mipBias`, `maxAnisotropy` |

Notes:
- `access.type` is `DescriptorType` enum (ConstantBuffer, Sampler, ImageSampler, Image, etc.)
- `descriptor.type` is an `int` — do NOT use it; use `access.type` for the descriptor category
- Sampler fields are only included for `Sampler` / `ImageSampler` type entries
- `sampler.filter` is an opaque type in real API; extract with `str(getattr(s, 'filter', ''))`

### Daemon Response

```json
{"eid": 42, "descriptors": [
  {"stage": "Vertex", "type": "ConstantBuffer", "index": 0, "array_element": 0,
   "resource_id": 42, "format": "", "byte_size": 256},
  {"stage": "Pixel", "type": "Sampler", "index": 1, "array_element": 0,
   "resource_id": 0, "format": "", "byte_size": 0,
   "sampler": {"address_u": "Wrap", "address_v": "Wrap", "address_w": "Wrap",
               "filter": "Linear", "compare_function": "", "min_lod": 0.0,
               "max_lod": 1000.0, "mip_bias": 0.0, "max_anisotropy": 1}}
]}
```

### TSV Output (7 columns)

```
STAGE	TYPE	INDEX	ARRAY_EL	RESOURCE	FORMAT	BYTE_SIZE
Vertex	ConstantBuffer	0	0	42		256
Pixel	Sampler	1	0	0		0
```

| Column | Source |
|--------|--------|
| `STAGE` | `access.stage.name` |
| `TYPE` | `access.type.name` |
| `INDEX` | `access.index` |
| `ARRAY_EL` | `access.arrayElement` |
| `RESOURCE` | `int(descriptor.resource)` |
| `FORMAT` | `descriptor.format.Name()` or empty |
| `BYTE_SIZE` | `descriptor.byteSize` |

Sampler details are only in JSON mode (`--json`), not in TSV. Use `rdc cat --json` for
full sampler info.

## Out of Scope

- Resource name resolution (cross-ref with `GetResources`)
- Per-descriptor raw data export (use `/buffers/<id>/data`, `/textures/<id>/image.png`)
- Filtering by stage/type via VFS path segments (use shell `grep` on TSV)
- `GetDescriptorStores` / `GetDescriptors` / `GetDescriptorLocations` — lower-level store
  enumeration; not needed when `GetAllUsedDescriptors` covers the common case
- `bind_name` / logical binding name — requires `GetDescriptorLocations`, future feature

## Dependencies

- OpenSpec #3 (phase2-pipeline-state): same `_set_frame_event` + `get_pipeline_state()` pattern
- No binary output, no temp files
- SWIG auto-converts returned `rdcarray<UsedDescriptor>` to iterable Python sequence
