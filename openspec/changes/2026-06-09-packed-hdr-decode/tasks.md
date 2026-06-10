# Tasks: packed-hdr-decode

## Phase A: unpack helpers

- [x] Add `_unpack_r11g11b10(words: np.ndarray) -> np.ndarray` to
  `src/rdc/handlers/_helpers.py` (place adjacent to `_decode_dtype`).
  Vectorised numpy: extract R/G 11-bit and B 10-bit fields; apply subnormal /
  normal / inf-nan cases via `np.where`; return float32 shape `(N, 3)`.

- [x] Add `_unpack_r9g9b9e5(words: np.ndarray) -> np.ndarray` to the same file.
  Extract R/G/B 9-bit mantissas and 5-bit shared exponent; decode as
  `mant * 2.0**(exp - 24)`; return float32 shape `(N, 3)`.

## Phase B: hook into `_decode_texture_png`

- [x] In `_decode_texture_png`, insert the packed-HDR branch **before** the
  `ResourceFormatType.Regular` gate (the existing MSAA guard sits below that gate and is
  unreachable for non-Regular formats, so it cannot be relied on):
  - Guard on `fmt.type in (rd.ResourceFormatType.R11G11B10, rd.ResourceFormatType.R9G9B9E5)`
  - Own MSAA check: `if getattr(tex, "msSamp", 1) > 1: return None`
  - Compute `width`/`height`/`depth_lvl` locally (those locals are defined only after the
    Regular gate in the current code)
  - Length check: `len(raw) != width * height * depth_lvl * 4` → return None
  - Reinterpret as `uint32` LE, reshape to `(depth_lvl * height, width)`, ravel, call the
    appropriate unpack helper, reshape back to `(depth_lvl * height, width, 3)`
  - Apply Float display path: `nan_to_num`, `clip`, `_srgb_encode`, alpha=255, RGBA PNG

## Phase C: unit tests

- [x] Add TC-1 through TC-14 (from test-plan.md) to
  `tests/unit/test_tex_stats_handler.py`, following the `_remote_state` / `_handle_request`
  pattern used by the existing remote decode tests.
  - Use `struct.pack("<I", <word>)` to construct raw bytes for each test vector.
  - Pixel assertions use `img.getpixel((0, 0))` on the decoded PNG.
- [x] TC-15 (MANDATORY): repurpose the existing
  `test_tex_export_remote_packed_format_rejected` — it currently asserts R11G11B10
  (`type=13`) is rejected with `-32002`, which this change breaks. Swap its fixture to a
  still-unsupported non-Regular packed type (e.g. `R5G6B5` type=14 or `R10G10B10A2`
  type=12), keep the `-32002 "not supported"` assertion, and rename the test.

## Phase D: verification

- [x] Run `pixi run lint` — no new lint errors.
- [x] Run `pixi run test` — all existing tests pass; new TC-1 through TC-14 pass.
- [ ] Real-GPU verify step per test-plan.md section "Manual / real-GPU verification"
  (or mark DEFERRED with a tracking comment if no suitable capture is available).
