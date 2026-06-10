# Tasks: 2026-06-09-depth-export-consistency

## T1: Handler — unify `_handle_rt_depth`

- [x] In `src/rdc/handlers/texture.py`, remove the `is_remote` branch in
  `_handle_rt_depth`. Replace both branches with a single code path:
  1. Look up `tex = state.tex_map.get(int(depth.resource))`.
  2. If not found, return -32001 "depth target not found in tex_map".
  3. Call `_export_remote(..., is_depth=True)`.
  4. If `_export_remote` returned -32002 **and** `state.is_remote is False`:
     fall back to `SaveTexture` via `_make_texsave` + `controller.SaveTexture`.
  5. Return the result.
- [x] No changes to `_export_remote` itself — it contains no `is_remote`
  logic (verified texture.py:66-96); the fallback decision lives entirely in
  `_handle_rt_depth` (branch on error code -32002 in the returned response,
  see proposal "Contract note").
- [x] Update snapshot.py comment on the `rt_depth` call (line ~63):
  "depth decode unsupported (combined depth-stencil or MSAA in remote mode)".

## T2: Unit tests

- [x] In `tests/unit/test_tex_stats_handler.py`, add:
  - `test_rt_depth_local_calls_gettexturedata` (D32_FLOAT, local, SaveTexture
    must not be called, output mode-L)
  - `test_rt_depth_local_produces_grayscale_L` (D16, local, mode-L, pixel values)
  - `test_rt_depth_local_d24s8_fallback_uses_savetexture` (D24S8, local,
    SaveTexture called, result present)
  - `test_rt_depth_remote_d24s8_no_fallback` (D24S8, remote, -32002 returned,
    SaveTexture never called)
  - `test_rt_depth_local_remote_byte_identical_d16` (same D16 mock data, both
    modes, identical PNG bytes)
- [x] In `tests/unit/test_binary_daemon.py`, update `_make_handler_state`:
  add a depth `TextureDescription` (ResourceId 500, Regular depth format such
  as D16) to `textures`/`tex_map` — currently only texture 42 is present and
  the depth target ResourceId(500) would return -32001 "not found" — and make
  the existing `GetTextureData` stub return correctly-sized bytes for it.
  Keep the `SaveTexture` stub (still used by rt_export and the fallback path).
- [x] Run `pixi run test` — all pass, including pre-existing remote grayscale
  tests (`test_rt_depth_remote_decodes_grayscale`,
  `test_rt_depth_remote_d16_decodes_grayscale`).

## T3: Golden file update

- [x] Golden scan done at spec time (2026-06-09, f36b41e): no `depth*.png`
  reference files and no golden PNGs exist under `tests/`; no e2e test asserts
  depth red-channel content. Nothing to regenerate.
- [ ] Verify `pixi run test-e2e` (or equivalent golden-file CI target) passes.
  (gpu-gated; not run in this environment. No golden depth PNG assets exist, so
  no regeneration is required.)

## T4: Docs / changelog

- [ ] Add entry to `CHANGELOG.md` under the next release:
  "depth export: local mode now produces grayscale mode-L PNG (min-max stretch)
  matching remote mode; previously produced RGBA with depth in red channel."
- [ ] Run `pixi run gen-commands` and `pixi run gen-skill-ref` if depth export
  is mentioned in any auto-generated reference (unlikely, but verify).

## T5: Manual real-GPU verify

- [ ] Follow test-plan.md Step 1-3: local and remote depth PNGs byte-identical
  for vkcube D16 capture.
- [ ] Follow test-plan.md Step 4 if a D24S8 capture is available: fallback
  produces a file, no error.
