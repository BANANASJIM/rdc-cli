# Test Plan: phase2-descriptors

## Scope

### In scope
- Daemon handler `descriptors`: accepts `eid`, calls `pipe_state.GetAllUsedDescriptors(True)`,
  returns `{"eid": <int>, "descriptors": [...]}`
- VFS route `/draws/<eid>/descriptors` → leaf, handler `"descriptors"`
- Tree cache: `"descriptors"` added to `_DRAW_CHILDREN`, static leaf in `build_vfs_skeleton`
- VFS extractor: `rdc cat /draws/<eid>/descriptors` → TSV output
- Mock additions: `DescriptorType`, `AddressMode` enums; `DescriptorAccess`, `SamplerDescriptor`,
  `UsedDescriptor` dataclasses in `mock_renderdoc.py`
- Mock API sync: new struct/enum pairs in `test_mock_api_sync.py`

### Out of scope
- CLI convenience command (VFS-only via `rdc cat`)
- Binary output (text TSV/JSON only)
- `GetDescriptorAccess()` / `GetDescriptors()` / `GetDescriptorLocations()` low-level APIs
- `bind_name` / logical binding name (requires `GetDescriptorLocations`)

## Test Matrix

| Layer | Scope | File |
|-------|-------|------|
| Unit | Daemon handler with mock adapter | `test_descriptors_daemon.py` (new) |
| Unit | VFS route resolution | `test_vfs_router.py` |
| Unit | Tree cache draw children | `test_vfs_tree_cache.py` |
| Unit | VFS `rdc cat` TSV output | `test_vfs_commands.py` |
| Integration | Mock struct field sync | `test_mock_api_sync.py` |
| GPU | Real capture on hello_triangle.rdc | `test_daemon_handlers_real.py` |
| GPU | Real capture with image+sampler | `test_daemon_handlers_real.py` |

## Cases

### Daemon handler: `descriptors`

1. **Happy path — ConstantBuffer only**: 2 CBV descriptors (VS + PS) → `result["eid"]` matches,
   `len(result["descriptors"]) == 2`, each entry has keys: `stage`, `type`, `index`,
   `array_element`, `resource_id`, `format`, `byte_size`; `type == "ConstantBuffer"`.

2. **Mixed types**: 1 ConstantBuffer + 1 Image + 1 Sampler → 3 entries with distinct `type`
   values: `"ConstantBuffer"`, `"Image"`, `"Sampler"`.

3. **Sampler includes sampler sub-dict**: entry with `type == "Sampler"` has `"sampler"` key
   containing `address_u`, `address_v`, `address_w`, `filter`, `compare_function`, `min_lod`,
   `max_lod`, `mip_bias`, `max_anisotropy`. Non-sampler entries do NOT have `"sampler"` key.

4. **Empty result**: `GetAllUsedDescriptors(True)` returns `[]` → `result["descriptors"] == []`,
   not an error.

5. **No adapter loaded**: `state.adapter is None` → JSON-RPC error `-32002`.

6. **EID out of range**: `_set_frame_event` fails → JSON-RPC error `-32002`.

### VFS route

7. **Valid path**: `resolve_path("/draws/42/descriptors")` → `PathMatch(kind="leaf",
   handler="descriptors", args={"eid": 42})`.

8. **Non-integer eid**: `resolve_path("/draws/abc/descriptors")` → `None`.

### VFS tree cache

9. **Draw children include descriptors**: after `build_vfs_skeleton`, `/draws/<eid>` node has
   `"descriptors"` in `children`; `/draws/<eid>/descriptors` is a `VfsNode(kind="leaf")`.

### VFS extractor (`rdc cat`)

10. **TSV output**: `rdc cat /draws/<eid>/descriptors` with 2 CBV descriptors → stdout first
    line is `STAGE\tTYPE\tINDEX\tARRAY_EL\tRESOURCE\tFORMAT\tBYTE_SIZE`, followed by 2 data
    rows, each with 7 tab-separated fields; exit code 0.

11. **Empty result**: `[]` → header-only output, no data rows, exit code 0.

### Mock API sync

12. **`DescriptorAccess` struct**: fields match real API; validated by `test_struct_fields_match`.

13. **`UsedDescriptor` struct**: fields `.access`, `.descriptor`, `.sampler` match real API.

### GPU integration

14. **hello_triangle.rdc**: known draw eid → `result["descriptors"]` has >= 2 entries, all
    `type == "ConstantBuffer"`, `resource_id > 0`, `byte_size > 0`.

15. **Sampler capture** (separate_image_sampler or skip): at least 3 entries covering
    ConstantBuffer + Image + Sampler types; Sampler entry has `"sampler"` dict with non-empty
    `filter`. Skip test if capture not available.

16. **VFS cat GPU**: `rdc cat /draws/<eid>/descriptors` on hello_triangle → exit code 0, TSV
    first line matches header.

## Assertions

### Exit codes
- 0: success (including empty descriptor list)
- 1: runtime error (no session, no adapter, eid not found)

### TSV contract
- Header: exactly `STAGE\tTYPE\tINDEX\tARRAY_EL\tRESOURCE\tFORMAT\tBYTE_SIZE` (7 columns)
- Each data row: exactly 7 tab-separated fields
- `STAGE`: shader stage name string (e.g. `"Vertex"`, `"Pixel"`)
- `TYPE`: descriptor type string (e.g. `"ConstantBuffer"`, `"Image"`, `"Sampler"`)
- `INDEX`: decimal integer string
- `ARRAY_EL`: decimal integer string
- `RESOURCE`: decimal integer string (0 = null resource)
- `FORMAT`: string (format name or empty)
- `BYTE_SIZE`: decimal integer string (0 if not applicable)
- No blank lines between rows

### JSON mode (daemon response)
```json
{"eid": <int>, "descriptors": [
  {"stage": <str>, "type": <str>, "index": <int>, "array_element": <int>,
   "resource_id": <int>, "format": <str>, "byte_size": <int>},
  {"stage": <str>, "type": <str>, "index": <int>, "array_element": <int>,
   "resource_id": <int>, "format": <str>, "byte_size": <int>,
   "sampler": {"address_u": <str>, "address_v": <str>, "address_w": <str>,
               "filter": <str>, "compare_function": <str>, "min_lod": <float>,
               "max_lod": <float>, "mip_bias": <float>, "max_anisotropy": <int>}}
]}
```
- `descriptors` is always a list (empty is valid)
- `sampler` key present only on Sampler/ImageSampler entries
- `resource_id` >= 0 (0 = null)
- `byte_size` >= 0

### Error response (JSON-RPC)
- `-32002`: no adapter / eid out of range
- `"message"` is non-empty string

## Risks & Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| `GetAllUsedDescriptors` signature differs across versions | Handler crash | Guard with `hasattr`; GPU test probes signature |
| `UsedDescriptor` field names unstable | Wrong fields | `test_mock_api_sync.py` struct sync catches renames |
| `sampler.filter` is opaque SWIG type, not plain string | Handler crash | Use `str(getattr(s, 'filter', ''))` coercion |
| `int(resourceId)` SWIG compat | Wrong type | Same `int()` cast as all other handlers |
| hello_triangle has no Sampler descriptors | GPU sampler test fails | Use separate_image_sampler capture or `pytest.skip` |
| `"descriptors"` in `_DRAW_CHILDREN` changes child order | Existing tree test breaks | Update expected list in `test_vfs_tree_cache.py` |
| Rollback | — | Revert branch; no master changes until squash-merge |
