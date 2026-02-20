# Tasks: Fix Real RenderDoc API Mismatch

## Phase 1: Foundation (mock + adapter)

### 1a. Fix mock_renderdoc.py
- [x] Fix `ResourceType` enum: Texture=4, Buffer=5, SwapchainImage=8
- [x] Fix `FileType` enum: DDS=0, PNG=1, JPG=2
- [x] Remove width/height/depth/mips/arraysize/format/creationFlags from `ResourceDescription`
- [x] Add `TextureType` enum (Texture2D=4, Texture3D=9, etc.)
- [x] Add `TextureCategory` IntFlag (ShaderRead=1, ColorTarget=2, DepthTarget=4, etc.)
- [x] Add `BufferCategory` IntFlag (Vertex=1, Index=2, Constants=4, etc.)
- [x] Add `TextureDescription` dataclass (resourceId, width, height, depth, mips, arraysize, dimension, format, type, byteSize, creationFlags, cubemap, msQual, msSamp)
- [x] Add `BufferDescription` dataclass (resourceId, length, creationFlags, gpuAddress)
- [x] Add `Subresource` dataclass (mip=0, slice=0, sample=0)
- [x] Add `TextureSliceMapping` dataclass (sliceIndex=-1)
- [x] Fix `TextureSave`: add resourceId field, slice as TextureSliceMapping object
- [x] Add `GetTextures()` / `GetBuffers()` to `MockReplayController`
- [x] Verify: `pixi run test -k "not gpu"`

### 1b. Fix adapter.py
- [x] Add `get_textures()` → `controller.GetTextures()`
- [x] Add `get_buffers()` → `controller.GetBuffers()`
- [x] Verify: `pixi run test -k "not gpu"`

## Phase 2: Tree cache + daemon (parallel)

### 2a. Fix tree_cache.py
- [x] Change `build_vfs_skeleton()` signature: add `textures` and `buffers` params
- [x] Remove ResourceType-based classification code
- [x] Populate `/textures/` from textures list (by resourceId)
- [x] Populate `/buffers/` from buffers list (by resourceId)
- [x] Get mip count from `TextureDescription.mips`
- [x] Update tests in `test_vfs_tree_cache.py` to pass textures/buffers lists
- [x] Verify: `pixi run test -k test_vfs_tree_cache`

### 2b. Fix daemon_server.py
- [x] Add `tex_map`, `buf_map`, `res_names`, `rd` fields to `DaemonState`
- [x] Fix `_load_replay()`: call `get_textures()`/`get_buffers()`, build maps, store `rd` module
- [x] Replace `_find_resource_by_id()` with tex_map/buf_map lookup
- [x] Fix `tex_info`: read from TextureDescription + res_names; output all fields
- [x] Fix `tex_export`: use `_make_texsave(state.rd, ...)` for SWIG-compatible TextureSave
- [x] Fix `tex_raw`: use `_make_subresource(state.rd)` for SWIG-compatible Subresource
- [x] Fix `buf_info`: read length from BufferDescription
- [x] Fix `buf_raw`: lookup from buf_map
- [x] Fix `rt_export`/`rt_depth`: use `_make_texsave(state.rd, ...)`
- [x] Update tests in `test_binary_daemon.py` to use new mock types + set `state.rd`
- [x] Verify: `pixi run test -k test_binary_daemon`

## Phase 3: Integration

### 3a. Fix integration tests
- [x] Update `test_daemon_handlers_real.py` `_make_state()` to pass textures/buffers + set `state.rd`
- [x] Verify: `pixi run test` (all 511 unit tests pass)
- [x] Verify: `pixi run test-gpu` (all 26 GPU integration tests pass)
- [x] Verify: `pixi run lint` (clean)
