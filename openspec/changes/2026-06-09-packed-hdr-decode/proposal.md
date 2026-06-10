# Proposal: packed HDR format decode for remote texture export

## Motivation

Issue #236 named R11G11B10_FLOAT and R9G9B9E5_SHAREDEXP as formats to support.
PR #237 (621528f) scoped them out: `_decode_texture_png` rejects all non-Regular
`ResourceFormatType`s with `-32002 "format not supported for remote decode"`.

Both formats are common HDR render-target and light-probe formats:
- R11G11B10_FLOAT is the standard G-buffer emission/radiance target in UE5, Unity HDRP,
  and most modern engines. Its 32 bits-per-pixel with no sign makes it a first-class RT.
- R9G9B9E5_SHAREDEXP appears as HDR skybox / IBL texture storage.

Both are closed-form bit-unpackable in numpy with no GPU round-trip, so they can follow
the same local-decode path already used for Regular Float formats.

## Design

### Entry point

`_decode_texture_png` currently has a hard gate at the top:

```python
if fmt.type != rd.ResourceFormatType.Regular:
    return None
```

The fix adds two explicit branches **before** this gate, keyed on
`fmt.type == rd.ResourceFormatType.R11G11B10` and
`fmt.type == rd.ResourceFormatType.R9G9B9E5`. Each branch:
1. Length-checks `len(raw) != width * height * depth_lvl * 4` (4 bytes/pixel, fixed).
2. Reinterprets `raw` as `uint32` LE and extracts float32 RGB via numpy bitops.
3. Feeds the result into the existing Float display path: `nan_to_num`, `clip(0,1)`,
   `_srgb_encode`, alpha=255 opaque, output RGBA PNG.

The Regular gate is unchanged; every other non-Regular format still returns `None`.

### Unpack functions

Two private helpers (in `_helpers.py` alongside the existing helpers):

**`_unpack_r11g11b10(words: np.ndarray) -> np.ndarray`**

Input: uint32 array shape `(N,)`. Output: float32 array shape `(N, 3)` — R, G, B.

Bit extraction (all shifts on the uint32 word):
- R 11-bit: `words & 0x7FF`         (bits [0:11))
- G 11-bit: `(words >> 11) & 0x7FF` (bits [11:22))
- B 10-bit: `(words >> 22) & 0x3FF` (bits [22:32))

For 11-bit component `x` (exp=5 bits, mant=6 bits, no sign):
- `exp = x >> 6`, `mant = x & 0x3F`
- exp == 0  → subnormal: `value = (mant / 64.0) * 2**-14`
- exp == 31 → Inf/NaN (handled by nan_to_num downstream)
- else      → normal: `value = (1.0 + mant / 64.0) * 2**(exp - 15)`

For 10-bit component `x` (exp=5 bits, mant=5 bits, no sign):
- `exp = x >> 5`, `mant = x & 0x1F`
- exp == 0  → subnormal: `value = (mant / 32.0) * 2**-14`
- exp == 31 → Inf/NaN
- else      → normal: `value = (1.0 + mant / 32.0) * 2**(exp - 15)`

Vectorised implementation: build `exp` and `mant` arrays, apply numpy `where` for the
three cases (subnormal / inf-nan / normal). The inf/nan case can emit `np.inf` or any
non-finite value — `nan_to_num` in the display path sanitises them.

**`_unpack_r9g9b9e5(words: np.ndarray) -> np.ndarray`**

Input: uint32 array shape `(N,)`. Output: float32 array shape `(N, 3)`.

Bit extraction:
- R mantissa 9-bit: `words & 0x1FF`           (bits [0:9))
- G mantissa 9-bit: `(words >> 9) & 0x1FF`    (bits [9:18))
- B mantissa 9-bit: `(words >> 18) & 0x1FF`   (bits [18:27))
- Shared exponent 5-bit: `(words >> 27) & 0x1F` (bits [27:32))

Decode: `value_c = mant_c * 2.0**(exp - 24)` (equivalent to `mant_c / 512.0 * 2^(exp-15)`).
No Inf/NaN possible (the exponent has no reserved value in this format); shared exponent
E=31 is valid and just produces large values which clip to 1 in the display path.

### Integration into `_decode_texture_png`

IMPORTANT (ordering): in the current code the `ResourceFormatType.Regular` gate
(`if fmt.type != rd.ResourceFormatType.Regular: return None`) comes FIRST, and the MSAA
guard (`if getattr(tex, "msSamp", 1) > 1: return None`) comes AFTER it. Packed formats are
non-Regular, so they are rejected by the Regular gate before ever reaching the MSAA guard.
The packed branch MUST therefore be inserted **before** the Regular gate, and it MUST:
(a) perform its own MSAA check (the existing guard is below the Regular gate and is
unreachable for non-Regular formats), and (b) compute `width`/`height`/`depth_lvl`
locally, because those locals are not yet defined this early in the function.

Insert immediately after `fmt = tex.format` (and after the `if not raw: return None`
check), before the Regular gate:

```python
# Packed HDR formats: 4 bytes/pixel, closed-form numpy decode.
if fmt.type in (rd.ResourceFormatType.R11G11B10, rd.ResourceFormatType.R9G9B9E5):
    if getattr(tex, "msSamp", 1) > 1:
        return None
    width = max(1, tex.width >> mip)
    height = max(1, tex.height >> mip)
    depth_lvl = max(1, getattr(tex, "depth", 1) >> mip)
    if len(raw) != width * height * depth_lvl * 4:
        return None
    words = np.frombuffer(raw, dtype=np.dtype("<u4")).reshape((depth_lvl * height, width))
    flat = words.ravel()
    if fmt.type == rd.ResourceFormatType.R11G11B10:
        rgb = _unpack_r11g11b10(flat)
    else:
        rgb = _unpack_r9g9b9e5(flat)
    rgb_img = rgb.reshape((depth_lvl * height, width, 3))
    # Reuse Float display path.
    sanitized = np.nan_to_num(rgb_img, nan=0.0, posinf=1.0, neginf=0.0)
    f = np.clip(sanitized, 0.0, 1.0)
    alpha = np.full((depth_lvl * height, width, 1), 255, np.uint8)
    rgb8 = (_srgb_encode(f) * 255.0).round().astype(np.uint8)
    out = np.concatenate([rgb8, alpha], axis=2)
    buf = io.BytesIO()
    Image.fromarray(out, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()
```

Notes:
- `depth_lvl * height` matches the 3D tiling logic already in the Regular path.
- `BGRAOrder()` does not apply (R11G11B10 and R9G9B9E5 have no BGRA variant).
- `is_depth` never applies (these are color formats; callers do not set it for HDR RTs).
- MSAA is rejected by the explicit `msSamp` check inside this branch (the function's other
  MSAA guard sits below the Regular gate and never sees non-Regular formats).
- The length check uses `* 4` not `* cc * cbw` because `compCount`/`compByteWidth` are
  not meaningful for packed formats — only `ElementSize()` (which equals 4) matters.

### What is NOT changed

- Local mode `SaveTexture` path: unchanged.
- The `_decode_dtype` table: unchanged (packed formats never reach it).
- All other non-Regular formats: still rejected via the existing gate.
- `rt_overlay` guard: still blocked.
- `_export_remote` and call sites in `texture.py`: no change needed; they already pass
  `raw` to `_decode_texture_png` and propagate `None` → `-32002`.

## Risks

| Risk | Mitigation |
|------|------------|
| Bit-extraction off-by-one | Hand-computed known-value unit tests with exact uint32 words. |
| numpy `where` for subnormal/normal wrong | Explicit test case for subnormal (exp=0, mant=1) — value must be ~9.5e-7, not zero. |
| Inf/NaN leaked to Image.fromarray | `nan_to_num` is applied before clip; verified by existing NaN test pattern on Float path. |
| Length check wrong (using cc*cbw) | Spec explicitly mandates `* 4`; length test covers wrong-size rejection. |
| Regression on existing Regular formats | New branches are fully guarded by `fmt.type`; Regular path code is untouched. |
