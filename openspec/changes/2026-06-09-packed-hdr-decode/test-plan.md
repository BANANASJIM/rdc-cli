# Test plan: packed HDR format decode

All tests follow the pattern in `tests/unit/test_tex_stats_handler.py`:
`_remote_state(tex, raw, tmp_path)` + `_handle_request(rpc_request("tex_export", {...}), state)`.
Format fields use `rd.ResourceFormat(type=..., compByteWidth=4, compCount=3, compType=1)`.
- `rd.ResourceFormatType.R11G11B10 = 13`
- `rd.ResourceFormatType.R9G9B9E5 = 16`

---

## Bit-vector construction reference

### R11G11B10_FLOAT

Per-pixel layout in a little-endian uint32:
- R 11-bit: bits [0:11) — 5-bit exponent (bits 6-10), 6-bit mantissa (bits 0-5), no sign.
- G 11-bit: bits [11:22).
- B 10-bit: bits [22:32) — 5-bit exponent (bits 27-31 of the full word), 5-bit mantissa.

Decode of an 11-bit component `x`:
- exp = x >> 6, mant = x & 0x3F
- exp == 0: value = (mant / 64) * 2^-14  (subnormal)
- exp == 31: Inf (mant==0) or NaN (mant!=0)
- else: value = (1 + mant/64) * 2^(exp-15)

Decode of the 10-bit B component `x`:
- exp = x >> 5, mant = x & 0x1F
- exp == 0: value = (mant / 32) * 2^-14
- exp == 31: Inf/NaN
- else: value = (1 + mant/32) * 2^(exp-15)

**Known-value uint32 words (LE):**

| Color (R, G, B) | uint32 word | LE bytes | Notes |
|-----------------|-------------|----------|-------|
| (1.0, 0.5, 0.25) | `0x681C03C0` | `[0xC0,0x03,0x1C,0x68]` | R: exp=15 mant=0; G: exp=14 mant=0; B: exp=13 mant=0 |
| max finite (all ch) | `0xF7FDFFBF` | `[0xBF,0xFF,0xFD,0xF7]` | R,G: exp=30 mant=63; B: exp=30 mant=31 |
| Inf (all ch) | `0xF83E07C0` | `[0xC0,0x07,0x3E,0xF8]` | R,G: exp=31 mant=0; B: exp=31 mant=0 |
| NaN (all ch) | `0xF87E0FC1` | `[0xC1,0x0F,0x7E,0xF8]` | R,G: exp=31 mant=1; B: exp=31 mant=1 |
| subnormal (mant=1 all) | `0x00400801` | `[0x01,0x08,0x40,0x00]` | R,G: exp=0 mant=1; B: exp=0 mant=1 |

### R9G9B9E5_SHAREDEXP

Per-pixel layout in a little-endian uint32:
- R mantissa 9-bit: bits [0:9)
- G mantissa 9-bit: bits [9:18)
- B mantissa 9-bit: bits [18:27)
- Shared exponent 5-bit: bits [27:32)

Decode: `value_c = mant_c * 2.0^(exp - 24)` (= `mant_c / 512 * 2^(exp-15)`).
No reserved exponent values; no Inf/NaN possible.

**Known-value uint32 words (LE):**

| Color (R, G, B) | uint32 word | LE bytes | Build (E, rm, gm, bm) |
|-----------------|-------------|----------|-----------------------|
| (1.0, 1.0, 1.0) | `0xC0040201` | `[0x01,0x02,0x04,0xC0]` | E=24, m=1 each: `1 * 2^0 = 1.0` |
| (1.0, 0.5, 0.25) | `0xB0040404` | `[0x04,0x04,0x04,0xB0]` | E=22, rm=4, gm=2, bm=1: `4*2^-2=1, 2*2^-2=0.5, 1*2^-2=0.25` |

**Expected sRGB output bytes** (after clip + `_srgb_encode`):
- 1.0 → 255, 0.5 → 188, 0.25 → 137, 0.0 → 0

---

## R11G11B10_FLOAT unit tests

**TC-1: happy path (1.0, 0.5, 0.25)**
- `fmt`: type=13, compByteWidth=4, compCount=3, compType=1, name="R11G11B10_FLOAT"
- `tex`: 1×1, msSamp=1
- `raw`: `struct.pack("<I", 0x681C03C0)` (4 bytes)
- `rpc`: `tex_export`, id=<tex_id>
- Assert: `resp["result"]` present; PNG RGBA; pixel[0,0][0]==255, pixel[0,0][1]` ≈ 188 (±2), pixel[0,0][2]` ≈ 137 (±2), alpha==255

**TC-2: Inf clips to white**
- `raw`: `struct.pack("<I", 0xF83E07C0)` (all-Inf)
- Assert: pixel[0,0] == (255, 255, 255, 255)

**TC-3: NaN renders black**
- `raw`: `struct.pack("<I", 0xF87E0FC1)` (all-NaN)
- Assert: pixel[0,0][0] == 0, pixel[0,0][1] == 0, pixel[0,0][2] == 0, alpha == 255

**TC-4: subnormal is non-negative and very small**
- `raw`: `struct.pack("<I", 0x00400801)` (exp=0 mant=1 for R,G,B)
- Assert: `resp["result"]` present; pixel[0,0] == (0, 0, 0, 255) (sRGB(~1.5e-19) rounds to 0); no error

**TC-5: wrong length rejected**
- `tex`: 2×2
- `raw`: `b"\x00" * 4` (should be 16 bytes)
- Assert: `resp["error"]["code"] == -32002`

**TC-6: MSAA rejected**
- `tex`: 1×1, msSamp=4
- `raw`: `struct.pack("<I", 0x681C03C0)`
- Assert: `resp["error"]["code"] == -32002`

**TC-7: 3D tiled (depth=2)**
- `tex`: 1×1, depth=2
- `raw`: `struct.pack("<2I", 0x681C03C0, 0x00000000)` (8 bytes = 2 slices)
- Assert: `resp["result"]` present; PNG size == (1, 2); pixel[0,0] ≈ (255, 188, 137, 255); pixel[0,1] == (0, 0, 0, 255)

---

## R9G9B9E5_SHAREDEXP unit tests

**TC-8: happy path (1.0, 1.0, 1.0)**
- `fmt`: type=16, compByteWidth=4, compCount=3, compType=1, name="R9G9B9E5_SHAREDEXP"
- `tex`: 1×1
- `raw`: `struct.pack("<I", 0xC0040201)` (4 bytes)
- Assert: `resp["result"]` present; pixel[0,0] == (255, 255, 255, 255)

**TC-9: happy path (1.0, 0.5, 0.25)**
- `raw`: `struct.pack("<I", 0xB0040404)`
- Assert: pixel[0,0][0] == 255, pixel[0,0][1] ≈ 188 (±2), pixel[0,0][2] ≈ 137 (±2), alpha == 255

**TC-10: zero value**
- `raw`: `struct.pack("<I", 0x00000000)` (E=0, all m=0)
- Assert: pixel[0,0] == (0, 0, 0, 255) — `0 * 2^(0-24) = 0`

**TC-11: wrong length rejected**
- `tex`: 2×2
- `raw`: `b"\x00" * 4`
- Assert: `resp["error"]["code"] == -32002`

**TC-12: 3D tiled (depth=2)**
- `tex`: 1×1, depth=2
- `raw`: `struct.pack("<2I", 0xC0040201, 0x00000000)` (8 bytes)
- Assert: PNG size == (1, 2); pixel[0,0] == (255, 255, 255, 255); pixel[0,1] == (0, 0, 0, 255)

**TC-12b: max shared exponent (E=31, mantissa=511) clips to white**
- `raw`: `struct.pack("<I", 0xFFFFFFFF)` (E=31, all mantissas=511 → each ch = 65408.0)
- Assert: pixel[0,0] == (255, 255, 255, 255). Confirms E=31 is a valid (non-reserved)
  exponent that produces large finite values clipped to 1, not Inf/NaN.

---

## Regression guard

**TC-13: existing Regular Float format still works**
- `fmt`: type=0 (Regular), compByteWidth=4, compCount=4, compType=1 (R32G32B32A32_FLOAT)
- Verify that an existing test (e.g. `test_tex_export_remote_rgba32f_hdr_clip`) still passes
  unchanged — confirms the new branches do not interfere with the Regular path.

**TC-14: BC1 (block-compressed) still rejected**
- `fmt`: type=2 (BC1), compByteWidth=0, compCount=4
- Assert: `-32002 "not supported"` — confirms the non-Regular gate is intact for BC.

**TC-15: repurpose the existing rejection test (MANDATORY — currently broken by this change)**
- The existing `test_tex_export_remote_packed_format_rejected` (in
  `tests/unit/test_tex_stats_handler.py`) builds an R11G11B10 (`type=13`) texture and
  asserts `-32002 "not supported"`. After this change R11G11B10 **decodes**, so that test
  WILL FAIL as written.
- Required action: repurpose it. Replace the `type=13` fixture with a still-unsupported
  non-Regular format that retains the rejection-test role — e.g. `R5G6B5` (`type=14`) or
  `R10G10B10A2` (`type=12`), both present in the mock enum and not decoded by this change.
  Keep the `-32002 "not supported"` assertion. Rename the test accordingly (e.g.
  `test_tex_export_remote_unsupported_packed_format_rejected`).
- Note: TC-14 (BC1) already guards the block-compressed path; TC-15 specifically preserves
  coverage of a still-unsupported *packed* non-Regular type after R11G11B10/R9G9B9E5 became
  decodable.

---

## Manual / real-GPU verification

1. Find or create a RenderDoc capture that contains R11G11B10_FLOAT or R9G9B9E5_SHAREDEXP
   render targets. Any modern engine HDR G-buffer pass or light probe capture works.
   If no capture is available locally, generate one from a Vulkan sample (e.g. Sascha Willems
   `hdr` sample) with `rdc capture`.

2. Open the capture in remote-replay mode: `rdc open capture.rdc --proxy host:port`.

3. Run `rdc rt <eid> -o /tmp/hdr_rt.png` for a draw event whose primary RT has one
   of the packed formats. Verify:
   - Command exits 0.
   - The PNG file exists and opens in an image viewer showing a plausible HDR scene
     (bright highlights clipped to white, not garbled noise).
   - `file /tmp/hdr_rt.png` reports PNG, `identify /tmp/hdr_rt.png` (ImageMagick) reports
     geometry matching the RT dimensions.

4. Cross-check: use `SaveTexture` in local mode on the same event/resource. Compare the
   two PNGs visually; they should be perceptually similar (same content, slight gamma
   difference acceptable since local mode may use a different display mapping).

5. If a capture is unavailable: fallback is unit vectors only (TC-1 through TC-12 above).
   Mark the real-GPU step as DEFERRED and file a tracking comment in the PR.
