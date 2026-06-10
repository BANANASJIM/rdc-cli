# Test Plan: remote texture export via GetTextureData

## Scope

### In scope
- `_decode_dtype` table + `_decode_texture_png` helper: format coverage, channel fixups,
  signed remap, length guard, empty-data guard
- `tex_export` in remote mode: PNG written locally
- `rt_export` in remote mode: PNG written locally
- `rt_depth` in remote mode: grayscale PNG written locally
- Regression: local (non-remote) mode still routes through `SaveTexture` unchanged
- Regression: `rt_overlay` still returns an error in remote mode
- `mock_renderdoc.py` extensions required for the above

### Out of scope
- `rt_overlay` correctness (guard is unchanged)
- Block-compressed / packed formats (returns -32002; negative tests cover the class)
- MSAA textures (guarded; one negative test)
- Live GPU proxy (manual only; see below)

## Test Matrix

| Layer | Type | File |
|-------|------|------|
| Unit | `_decode_texture_png` + export handlers (mock) | `tests/unit/test_tex_stats_handler.py` |
| Unit | mock infrastructure | `tests/mocks/mock_renderdoc.py` |

## Mock infrastructure (prerequisite)

`tests/mocks/mock_renderdoc.py` provides, for the remote-decode tests:

- `ResourceFormat(name, compByteWidth, compCount, compType, type=...)` with `BGRAOrder()`
  and `Name()`; `type` defaults to Regular and is set non-Regular for packed/block tests.
- `MockReplayController._texture_data[rid]` pre-populated by each test with the raw bytes;
  `GetTextureData(rid, sub)` returns it (and can return `b""` to exercise the empty guard).
- `MockPipeState(output_targets=..., depth_target=...)` and `Descriptor(resource=...)` for
  the `rt_export` / `rt_depth` paths.

## Unit test cases

All remote cases run with `is_remote=True`; no real GPU, no `SaveTexture` call.
Test names are the actual functions present in `tests/unit/test_tex_stats_handler.py`.

### Color decode — accepted formats

1. `test_tex_export_remote_rgba8` — R8G8B8A8_UNORM 4x2: valid PNG, size (4,2), mode RGBA.
2. `test_tex_export_remote_bgra_swaps_channels` — B8G8R8A8_UNORM 1x1: input B,G,R,A bytes
   decode to RGBA pixel with R/B swapped.
3. `test_tex_export_remote_r8_grayscale` — R8_UNORM 2x2 (cc=1): single channel repeated to
   RGB (pixel `(10,10,10)`), output is RGBA.
4. `test_tex_export_remote_float16_hdr` — R16G16B16A16_FLOAT 1x1: value 2.0 clipped + sRGB
   encoded to 255; alpha 255.
5. `test_tex_export_remote_r16_unorm_scales_by_257` — R16_UNORM: 65535/257=255, 32896/257=128.
6. `test_tex_export_remote_rgba32f_hdr_clip` — R32G32B32A32_FLOAT 1x1: 5.0 clipped to 1.0 ->
   sRGB -> 255; 0.0 -> 0; alpha 255.
7. `test_tex_export_remote_snorm_remaps_signed` — R8G8B8A8_SNORM read as int8: -1->0,
   0->~128, +1->255.
8. `test_tex_export_remote_uint8_passthrough` — R8G8B8A8_UINT 1x1: bytes pass through to RGBA.

### Color decode — rejected formats (→ -32002)

9. `test_tex_export_remote_length_mismatch_errors` — 4x4 RGBA8 with 4 bytes only -> -32002.
10. `test_tex_export_remote_special_format_rejected` — BC1_UNORM (non-Regular) ->
    "not supported".
11. `test_tex_export_remote_sint_rejected` — R8G8B8A8_SINT (no display mapping) ->
    "not supported".
12. `test_tex_export_remote_typeless_rejected` — R8G8B8A8_TYPELESS -> -32002.
13. `test_tex_export_remote_uscaled_rejected` — R8G8B8A8_USCALED -> -32002.
14. `test_tex_export_remote_packed_format_rejected` — R11G11B10_FLOAT (packed, non-Regular)
    -> "not supported".
15. `test_tex_export_remote_msaa_rejected` — RGBA8_UNORM with `msSamp=4` -> -32002.
16. `test_tex_export_remote_no_data_rejected` — `GetTextureData` returns `b""` ->
    "no texture data", no `len(None)` crash.

### `rt_export` remote mode

17. `test_rt_export_remote_decodes_png` — `MockPipeState` output target -> B8G8R8A8_SRGB 2x2
    `TextureDescription` in `tex_map`; result path is a valid PNG, mode RGBA.

### `rt_depth` remote mode

18. `test_rt_depth_remote_decodes_grayscale` — D32_FLOAT 2x2 depth target: mode `L`, min
    depth -> 0, max depth -> 255, mid depth ~64.
19. `test_rt_depth_remote_d16_decodes_grayscale` — D16 (uint16 depth, compType=Depth) 2x2:
    mode `L`, 0 -> 0, 65535 -> 255, 16384 -> ~64.

### Regression: local mode + rt_overlay

20. `test_rt_overlay_remote_still_rejected` — `rt_overlay` remote -> -32002, "remote mode".
21. `test_tex_export_local_uses_savetexture` — `is_remote=False`: `SaveTexture` is called
    exactly once (local path unchanged, not routed through the decode helper).

## Manual / GPU proxy check

The following cannot run in CI (requires a live remote daemon + real GPU):

- Connect client to a remote daemon replaying a vkcube capture; call `tex_export` on a
  known color target; verify the local PNG opens correctly and matches the texture as
  displayed in the RenderDoc GUI.
- Same for `rt_export` and `rt_depth`.
- Verify a BC7-compressed texture returns `-32002` (not a garbled PNG).

## Run command

```bash
pytest tests/unit/test_tex_stats_handler.py -q
```

Optional (explicit interpreter / renderdoc module path used during development):

```bash
RENDERDOC_PYTHON_PATH=/usr/lib/python3.14/site-packages ./.venv-236/bin/python -m pytest tests/unit/test_tex_stats_handler.py -q
```

Full gate: `pixi run check` (lint + typecheck + unit tests).
