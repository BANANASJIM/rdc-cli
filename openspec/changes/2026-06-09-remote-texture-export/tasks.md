# Tasks: remote texture export via GetTextureData

## Phase A: Mock infrastructure

- [ ] `tests/mocks/mock_renderdoc.py`: add `ResourceFormatType` IntEnum
  (`Regular=0, R10G10B10A2=12, R11G11B10=13, R5G6B5=14, R9G9B9E5=16, D16S8=19, D24S8=20, D32S8=21, S8=22, A8=28`)
- [ ] `tests/mocks/mock_renderdoc.py`: ensure `ResourceFormat` has `type=0` default and
  `BGRAOrder()` / `SRGBCorrected()` methods; verify existing handler tests still pass

## Phase B: Decode helper (TDD)

- [ ] Write unit tests (cases 1-12 in test-plan) in `tests/unit/test_tex_stats_handler.py`
  before implementing the helper; confirm they fail as expected
- [ ] Implement `_decode_texture_to_png(rd, tex, raw, mip, out_path)` in
  `src/rdc/handlers/texture.py` (or `src/rdc/handlers/_helpers.py`):
  - Mip dimension: `w = max(1, tex.width >> mip)`, `h = max(1, tex.height >> mip)`
  - Guard: `tex.format.type != rd.ResourceFormatType.Regular` → return `False` (caller emits -32002)
  - Guard: `tex.msSamp > 1` → return `False`
  - Defensive length check: `len(raw) != h * w * compCount * compByteWidth` → return `False`
  - Dtype/scale matrix by `(compType, compByteWidth)`: uint8 pass-through, uint16 `/257`,
    float16/float32 `clip+sRGB-OETF`, depth float32 auto-contrast
  - `BGRAOrder()` channel swap `[..., [2,1,0]]`
  - Channel expand to RGBA / mode `L` for single-channel
  - `PIL.Image.fromarray(...).save(out_path, format='PNG')`; return `True`
- [ ] Verify cases 1-12 pass

## Phase C: tex_export remote branch

- [ ] `src/rdc/handlers/texture.py` `_handle_tex_export`: add `if state.is_remote:` branch
  calling `controller.GetTextureData(tex.resourceId, sub)` then `_decode_texture_to_png`;
  emit `-32002` if helper returns `False`; return `{"path": str(out_path), "size": ...}`
- [ ] Keep existing `SaveTexture` branch unchanged under `else:`
- [ ] Remove (or convert) the existing remote-rejected guard for `tex_export`
- [ ] Verify test cases 1-12, 16 pass

## Phase D: rt_export and rt_depth remote branches

- [ ] `_handle_rt_export` remote branch: resolve `Descriptor.resource` →
  `state.tex_map[int(resource)]`; call `GetTextureData` + `_decode_texture_to_png`; emit
  error if resource not in `tex_map` or helper returns `False`
- [ ] `_handle_rt_depth` remote branch: same pattern; pass depth TextureDescription;
  helper auto-contrasts D32_FLOAT → mode `L` PNG
- [ ] Keep both `SaveTexture` local branches unchanged
- [ ] Remove (or convert) existing remote-rejected guards for `rt_export` and `rt_depth`
- [ ] Verify test cases 13-15, 17 pass

## Phase E: Regression + rt_overlay guard

- [ ] Confirm `rt_overlay` remote guard is intact (test case 18)
- [ ] Replace the three existing `test_*_remote_rejected` tests in `test_tex_stats_handler.py`
  (L298-317) with the new cases that assert a PNG is produced
- [ ] Run full unit suite: `pixi run test` — all green
- [ ] Run `pixi run check` (lint + typecheck + tests)

## Phase F: Code review + merge

- [ ] Code review
- [ ] Open PR targeting `master`
- [ ] Manual GPU proxy check (see test-plan manual section) after PR is up
- [ ] Archive this OpenSpec folder after merge
