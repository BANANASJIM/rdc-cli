# Tasks: remote texture export via GetTextureData

## Phase A: Mock infrastructure

- [x] `tests/mocks/mock_renderdoc.py`: `ResourceFormat` supports a non-Regular `type` and a
  `Name()` so packed/block/typeless tests can be expressed
- [x] `tests/mocks/mock_renderdoc.py`: `ResourceFormat.BGRAOrder()` plus
  `MockReplayController._texture_data` / `GetTextureData`, `MockPipeState`, and `Descriptor`
  for the remote export paths; existing handler tests still pass

## Phase B: Decode helpers (TDD)

- [x] Write the remote-decode unit tests in `tests/unit/test_tex_stats_handler.py` before
  implementing the helpers
- [x] Implement `_decode_dtype(rd, comp_type, comp_byte_width) -> str | None` in
  `src/rdc/handlers/_helpers.py`: a `(CompType, compByteWidth)` -> numpy-dtype table
  covering Float16/32, UNorm8/16, UNormSRGB8, SNorm8/16, UInt8/16, Depth8/16/32; returns
  `None` (reject) for Typeless / SInt / UScaled / SScaled / exotic widths
- [x] Implement `_decode_texture_png(rd, tex, raw, mip, *, is_depth) -> bytes | None` in
  `src/rdc/handlers/_helpers.py`:
  - Empty `raw` -> `None`
  - Guard: `tex.format.type != rd.ResourceFormatType.Regular` -> `None`
  - Guard: `tex.msSamp > 1` -> `None`
  - Mip dimension: `w = max(1, tex.width >> mip)`, `h = max(1, tex.height >> mip)`
  - Defensive length check: `len(raw) != h * w * compCount * compByteWidth` -> `None`
  - Dtype/scale by `(compType, compByteWidth)`: Float `clip+sRGB-OETF`, UNorm8/UNormSRGB8/
    UInt8 pass-through, UNorm16/UInt16 `/257`, SNorm signed-remap `[-1,1]->[0,255]`
  - `BGRAOrder()` (with `cc >= 3`) channel swap to RGBA
  - Color channel expand: cc=1 repeat->RGB + A=255, cc=2 RG0+A, cc=3 +A; always RGBA output
  - Depth path (`is_depth=True`): channel-0 auto-contrast -> mode `L`
  - Return PNG bytes
- [x] Verify color/reject decode cases pass

## Phase C: tex_export remote branch

- [x] `src/rdc/handlers/texture.py`: add `_export_remote(...)` helper that calls
  `GetTextureData`, guards empty/`None` data (`"no texture data returned"`), calls
  `_decode_texture_png`, emits `-32002` `"format <Name> not supported for remote decode"`
  on `None`, and writes the PNG returning `{"path", "size"}`
- [x] `_handle_tex_export`: route through `_export_remote` under `if state.is_remote:`
- [x] Keep the existing `SaveTexture` branch unchanged for local mode
- [x] Remove the old remote-rejected guard for `tex_export`
- [x] Verify `tex_export` remote + local-regression cases pass

## Phase D: rt_export and rt_depth remote branches

- [x] `_handle_rt_export` remote branch: resolve `Descriptor.resource` ->
  `state.tex_map[int(resource)]`; route through `_export_remote`; error if resource not in
  `tex_map`
- [x] `_handle_rt_depth` remote branch: same pattern, passing `is_depth=True` so depth ->
  mode `L` PNG
- [x] Keep both `SaveTexture` local branches unchanged
- [x] Remove the old remote-rejected guards for `rt_export` and `rt_depth`
- [x] Verify `rt_export` / `rt_depth` remote cases pass

## Phase E: Regression + rt_overlay guard

- [x] Confirm `rt_overlay` remote guard is intact (`test_rt_overlay_remote_still_rejected`)
- [x] Replace the old `test_*_remote_rejected` tests with cases asserting a PNG is produced
- [x] Run full unit suite — all green
- [x] Run `pixi run check` (lint + typecheck + tests)

## Phase F: Code review + merge

- [ ] Code review
- [ ] Open PR targeting `master`
- [ ] Manual GPU proxy check (see test-plan manual section) after PR is up
- [ ] Archive this OpenSpec folder after merge
