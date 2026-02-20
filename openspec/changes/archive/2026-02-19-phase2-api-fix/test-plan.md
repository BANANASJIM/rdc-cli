# Test Plan: Fix Real RenderDoc API Mismatch

## Scope

- **In scope**: All existing Phase 2 binary tests must pass with corrected API model.
  GPU integration tests must pass against real RenderDoc v1.41.
- **Out of scope**: New test cases. This is a fix, not a feature.

## Test Matrix

| Layer | GPU? | What |
|-------|------|------|
| Unit | No | All existing tests in test_binary_daemon.py with corrected mock types |
| Unit | No | All existing tests in test_vfs_tree_cache.py with textures/buffers lists |
| Unit | No | All existing tests in test_vfs_router.py (no changes expected) |
| Unit | No | All existing tests in test_export_commands.py (no changes expected) |
| Integration | Yes | All tests in test_daemon_handlers_real.py against real API |

## Key Assertions

### tex_info handler
- `result["width"] > 0` — now reads from TextureDescription, not ResourceDescription
- `result["height"] > 0`
- `result["mips"] >= 1`
- `result["format"]` is non-empty string (from `format.Name()` method call)
- All fields present: id, name, type, dimension, width, height, depth, mips,
  array_size, format, byte_size, creation_flags, cubemap, ms_samp

### tex_export handler
- Mip validation uses `TextureDescription.mips`
- TextureSave has `resourceId`, `mip`, `slice` (object with `sliceIndex`), `destType=1` (PNG)
- SaveTexture `texsave` argument has `resourceId` attribute (regression guard)

### buf_info handler
- `result["length"]` from `BufferDescription.length` (not `ResourceDescription.width`)
- All fields present: id, name, length, creation_flags, gpu_address

### tree_cache
- `/textures/` children populated from GetTextures() resourceIds
- `/buffers/` children populated from GetBuffers() resourceIds
- Mip count from `TextureDescription.mips`
- No ResourceType filtering used

### Mock module
- `ResourceType` enum matches real: Texture=4, Buffer=5
- `FileType.PNG = 1` (not 0)
- `ResourceDescription` has NO width/height/mips/format fields
- `TextureDescription` has all geometry fields
- `BufferDescription` has length field
- `GetTextures()`/`GetBuffers()` on MockReplayController

## Risks & Rollback

- Risk: Changing mock enum values may break non-binary tests that use ResourceType
  → Mitigate: grep for all uses of ResourceType, update all
- Risk: Changing ResourceDescription fields may break query_service.py
  → Check: query_service only uses resourceId and name from ResourceDescription
- Rollback: revert commits on feat/phase2-vfs-binary branch
