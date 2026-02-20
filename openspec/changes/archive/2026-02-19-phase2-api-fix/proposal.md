# Proposal: Fix Real RenderDoc API Mismatch

## Summary

GPU integration tests revealed that our Phase 2 binary export code uses incorrect
assumptions about the RenderDoc Python API. The mock module and all consumers must
be updated to match the real API data model discovered via v1.41 live testing.

See: `Obsidian/调研/调研-资源数据结构.md` for full reference.

## Problem

Three fundamental mismatches between our code and the real RenderDoc API:

1. **ResourceDescription has no geometry attributes.** Our code reads `width`,
   `height`, `mips`, `format`, `arraysize` from `ResourceDescription` — these
   fields don't exist. They live on separate `TextureDescription` (from
   `GetTextures()`) and `BufferDescription` (from `GetBuffers()`).

2. **Resource classification by type is wrong.** Our mock `ResourceType` has
   `Buffer=1, Texture2D=3`. Real API: `Texture=4, Buffer=5, SwapchainImage=8`.
   Swapchain images (type=8) appear in `GetTextures()` but not as type=4.
   Cannot filter `GetResources()` by type — must use `GetTextures()`/`GetBuffers()`.

3. **TextureSave construction is wrong.** `slice` is a `TextureSliceMapping` object
   (not int), `destType` defaults to DDS(0) not PNG, `FileType.PNG=1` (not 0).
   `GetTextureData` requires a `Subresource` object (not `None`).

## Scope

### In scope

- Fix `mock_renderdoc.py`: correct enums, add `TextureDescription`/`BufferDescription`/
  `Subresource`, add `GetTextures()`/`GetBuffers()` to controller
- Fix `adapter.py`: add `get_textures()`/`get_buffers()` methods
- Fix `tree_cache.py`: accept `textures`/`buffers` lists directly
- Fix `daemon_server.py`: lookup from tex/buf maps, fix TextureSave, fix all 7 handlers
- Fix all affected unit tests
- Verify GPU integration tests pass

### Out of scope

- New features or VFS paths
- Changes to CLI commands or export.py (only daemon-side fixes)

## Design

### Data flow

```
_load_replay():
  textures = adapter.get_textures()    # → TextureDescription[]
  buffers  = adapter.get_buffers()     # → BufferDescription[]
  resources = adapter.get_resources()  # → ResourceDescription[] (for names)

  res_names = {int(r.resourceId): r.name for r in resources}

  state.vfs_tree = build_vfs_skeleton(
      actions, resources, textures, buffers, sf
  )
  state.tex_map = {int(t.resourceId): t for t in textures}
  state.buf_map = {int(b.resourceId): b for b in buffers}
  state.res_names = res_names
```

### Handler lookup pattern

```python
# tex_info handler
tex = state.tex_map.get(res_id)
if tex is None:
    return error("texture not found")
name = state.res_names.get(res_id, "")
return {
    "id": res_id,
    "name": name,
    "width": tex.width,
    "height": tex.height,
    ...
}
```

### TextureSave construction

```python
# Use renderdoc module TextureSave when available, else mock-compatible
texsave = type("TextureSave", (), {
    "resourceId": tex.resourceId,
    "mip": mip,
    "slice": type("Slice", (), {"sliceIndex": 0})(),
    "destType": 1,  # PNG
})()
```

### build_vfs_skeleton new signature

```python
def build_vfs_skeleton(
    actions: list[Any],
    resources: list[Any],
    textures: list[Any],
    buffers: list[Any],
    sf: Any = None,
) -> VfsTree:
```

## Files changed

### Modified
- `tests/mocks/mock_renderdoc.py` — fix enums, add types, add controller methods
- `src/rdc/adapter.py` — add `get_textures()`, `get_buffers()`
- `src/rdc/vfs/tree_cache.py` — new signature, use textures/buffers directly
- `src/rdc/daemon_server.py` — tex_map/buf_map, fix all handlers, fix TextureSave
- `tests/unit/test_binary_daemon.py` — update mock setup to use new types
- `tests/unit/test_vfs_tree_cache.py` — update to pass textures/buffers
- `tests/integration/test_daemon_handlers_real.py` — pass textures/buffers to skeleton
