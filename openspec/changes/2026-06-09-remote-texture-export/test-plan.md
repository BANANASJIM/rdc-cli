# Test Plan: remote texture export via GetTextureData

## Scope

### In scope
- `_decode_texture_to_png` helper: format coverage, channel fixups, length guard
- `tex_export` in remote mode: PNG written locally
- `rt_export` in remote mode: PNG written locally
- `rt_depth` in remote mode: grayscale PNG written locally
- Regression: local (non-remote) mode still routes through `SaveTexture` unchanged
- Regression: `rt_overlay` still returns an error in remote mode
- `mock_renderdoc.py` extensions required for the above

### Out of scope
- `rt_overlay` correctness (guard is unchanged)
- Block-compressed / packed formats (v1 returns -32002; one negative test covers the class)
- MSAA textures (guarded; one negative test)
- Live GPU proxy (manual only; see below)

## Test Matrix

| Layer | Type | File |
|-------|------|------|
| Unit | `_decode_texture_to_png` + export handlers (mock) | `tests/unit/test_tex_stats_handler.py` (extend) |
| Unit | mock infrastructure | `tests/mocks/mock_renderdoc.py` (extend) |

## Mock infrastructure (prerequisite)

Extend `tests/mocks/mock_renderdoc.py` before writing handler tests:

- Add `ResourceFormatType` as an `IntEnum`:
  `Regular=0, R10G10B10A2=12, R11G11B10=13, R5G6B5=14, R9G9B9E5=16, D16S8=19, D24S8=20, D32S8=21, S8=22, A8=28`.
- Ensure `ResourceFormat` defaults: `type=0` (Regular), `compType=2` (UNorm), `compByteWidth=1`,
  `compCount=4`, `BGRAOrder()` returns `False`, `SRGBCorrected()` returns `False`.
- `MockReplayController._texture_data[rid]` must be pre-populated by each test with bytes of
  length `h * w * compCount * compByteWidth`; `GetTextureData(rid, sub)` returns it.

## Unit test cases

All cases: `is_remote=True`, controller has no GPU, no `SaveTexture` called.

### Format coverage (`tex_export` or helper, one test per format class)

1. **RGBA8_UNORM** (`compType=UNorm=2, compByteWidth=1, compCount=4, BGRAOrder=False`):
   supply `h*w*4` bytes of known pattern; assert output PNG is valid (`magic == b'\x89PNG'`),
   pixel at (0,0) matches expected RGBA value.

2. **BGRA8_UNORM** (`BGRAOrder=True, compCount=4`): supply bytes with B,G,R,A channel
   pattern; assert output PNG pixel has R and B swapped vs input bytes.

3. **BGRA8_SRGB** (`compType=UNormSRGB=9, BGRAOrder=True`): assert sRGB bytes pass through
   unchanged (no double-gamma), output PNG pixel matches direct uint8 reorder.

4. **R8_UNORM** (`compCount=1`): supply `h*w` bytes; assert output PNG is mode `L` or has
   repeated grayscale channels.

5. **R8G8_UNORM** (`compCount=2`): supply `h*w*2` bytes; assert output PNG has zero B channel
   and A=255.

6. **R16G16B16A16_UNORM** (`compByteWidth=2, compType=UNorm=2`): supply `h*w*8` uint16 little-
   endian bytes (max value 65535); assert PNG pixel channels are `round(65535/257)` = 255.

7. **R16G16B16A16_FLOAT** (`compByteWidth=2, compType=Float=1`): supply `h*w*8` bytes encoding
   known float16 values in `[0, 1]`; assert output PNG pixel is within ±2 of expected sRGB-
   encoded value.

8. **R32G32B32A32_FLOAT** (`compByteWidth=4, compType=Float=1`): supply `h*w*16` bytes
   encoding float32 `[0.0, 1.0, 0.5, 1.0]` per pixel; assert PNG pixel matches sRGB OETF
   applied to those values.

9. **D32_FLOAT depth** (`compCount=1, compByteWidth=4, compType=Depth=8 or Float=1`):
   supply `h*w*4` float32 bytes spanning a known `[d_min, d_max]` range; assert PNG mode `L`,
   pixel at minimum depth is 0, pixel at maximum depth is 255.

10. **Non-Regular format rejected**: set `tex.format.type = ResourceFormatType.D24S8 (=20)`;
    assert response is a JSON-RPC error with code `-32002` and message containing
    `"not supported for remote decode"`.

11. **Length mismatch guard**: supply raw bytes of length `h*w*4 - 1` (one byte short);
    assert response is a JSON-RPC error (not a crash / `ValueError`).

12. **MSAA rejected**: set `tex.msSamp = 2`; assert JSON-RPC error (mirror `tex_stats` guard).

### `rt_export` remote mode

13. Configure `MockPipeState` with an `output_targets` list containing a `Descriptor` whose
    `resource` maps to a `TextureDescription` (RGBA8_UNORM, 4×4) in `state.tex_map`; set
    `ctrl._texture_data[id]` accordingly.  Call `rpc_request('rt_export', {})`.  Assert
    `resp['result']['path']` points to a file whose first 4 bytes are `b'\x89PNG'`.

14. **rt_export target not in tex_map**: supply a `Descriptor.resource` id not present in
    `state.tex_map`; assert JSON-RPC error, no file created.

### `rt_depth` remote mode

15. Configure `MockPipeState` with a `depth_target` Descriptor mapping to a D32_FLOAT
    `TextureDescription` (4×4) in `state.tex_map`; supply `ctrl._texture_data[id]` as float32
    bytes. Assert response has a `path` pointing to a valid PNG file.

### Regression: local mode unchanged

16. Set `is_remote=False`; call `rpc_request('tex_export', {'id': id})` with a standard
    mock setup.  Assert `controller.SaveTexture` was called (not `GetTextureData`).  Assert
    no `_decode_texture_to_png` call.

17. Same for `rt_export` and `rt_depth` with `is_remote=False`.

### Regression: `rt_overlay` still blocked in remote mode

18. Set `is_remote=True`; call `rpc_request('rt_overlay', {'overlay': 'wireframe'})`.
    Assert JSON-RPC error with code indicating remote overlay is unsupported.

## Manual / GPU proxy check

The following cannot run in CI (requires a live remote daemon + real GPU):

- Connect client to a remote daemon replaying a vkcube capture; call `tex_export` on a
  known color target (e.g. resource id=96); verify the local PNG opens correctly and matches
  the texture as displayed in RenderDoc GUI.
- Same for `rt_export` and `rt_depth`.
- Verify a BC7-compressed texture returns `-32002` (not a garbled PNG).

## Run command

```
RENDERDOC_PYTHON_PATH=/usr/lib/python3.14/site-packages ./.venv-236/bin/python -m pytest tests/unit/test_tex_stats_handler.py -q
```

Full gate: `pixi run check` (lint + typecheck + unit tests).
