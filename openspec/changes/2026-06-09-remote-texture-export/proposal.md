# Remote texture export via GetTextureData + local decode

## Problem

Issue #236: `tex_export`, `rt_export`, and `rt_depth` all fail in remote mode.

The three export handlers unconditionally call `controller.SaveTexture(ts, path)`, which
writes a file on the **remote** daemon host's filesystem.  The client receives a path that
does not exist locally and cannot fetch it.  In the current codebase all three handlers are
pre-emptively blocked by the `is_remote` guard (introduced alongside remote replay), so
callers receive a JSON-RPC error before any file I/O is attempted.  The result is that
remote sessions have no supported path to export rendered targets — a major capability gap
for headless/cloud workflows where the daemon runs on a GPU server.

## Root Cause

`SaveTexture` is a RenderDoc API that writes to the path it is given, which in a remote
session is a path on the remote host.  There is no `SaveTexture`-over-network mode in the
RenderDoc Python API.  The `rt_overlay` handler is blocked for a related but distinct
reason: rendering overlays (Overdraw, Wireframe, etc.) requires GPU draw submission, which
is not safe over the remote JSON-RPC channel, so that guard is correct and must stay.

## Solution

Replace the `SaveTexture` call with `controller.GetTextureData(tex.resourceId, sub)`, which
returns the raw texel bytes over JSON-RPC to the **client** process.  The client decodes the
bytes locally using numpy and Pillow (both already runtime dependencies) and saves the result
as a PNG at the caller-supplied path.

A private helper `_decode_texture_to_png(rd, tex, raw, mip, out_path)` is added in
`handlers/texture.py` (or `handlers/_helpers.py`).  Each export handler calls it under
`if state.is_remote:`; the existing `SaveTexture` branch is left untouched for local mode.

### Decode logic (summary)

- Only `ResourceFormatType.Regular` formats are decoded in v1; non-Regular formats return
  a clear `-32002` error `"format <Name> not supported for remote decode"`.
- Mip-level dimensions: `w = max(1, tex.width >> mip)`, `h = max(1, tex.height >> mip)`.
- Byte layout from `GetTextureData` is tightly packed, top-down (no row padding, no Y-flip).
- Dtype and scaling are selected by `(compType, compByteWidth)`:
  - UNorm/UNormSRGB/Typeless 8-bit → `np.uint8`, no scale (sRGB bytes are display-ready,
    no additional gamma applied).
  - UNorm 16-bit → `np.uint16`, scale to 8-bit via divide-by-257.
  - Float16/Float32 (HDR linear) → tonemap: `clip(x, 0, 1)` then sRGB OETF, `*255`, uint8.
    Documented as contrast-clamped, not a raw dump.
  - Integer 8-bit → pass-through as uint8.
- `BGRAOrder() == True` → swap channels `[..., [2,1,0]]` before save.
- Defensive length check: `expected = h * w * compCount * compByteWidth`; if
  `len(raw) != expected`, return `False` and emit an error rather than crash on reshape.
- Channel expansion: cc=1 → grayscale (mode `L`); cc=2 → RG0 + A=255; cc=3 → add A=255;
  cc=4 → RGBA.
- Depth (`D32_FLOAT`): decode as `np.float32` single channel; auto-contrast via
  `(arr - arr.min()) / (arr.max() - arr.min())` then `*255` uint8 mode `L`.  This matches
  RenderDoc's own depth display (contrast-stretched for visibility; not a raw depth dump —
  use `tex_raw` for exact bytes).
- Packed depth-stencil (`D24S8`, `D32S8`, type != Regular) and block-compressed formats
  (BC1-7, ASTC, etc.) → return `-32002` in v1.

### What stays blocked

`rt_overlay` remote guard is unchanged: overlay rendering requires GPU submission and cannot
be made safe over remote JSON-RPC.

### Scope

- In scope: `tex_export`, `rt_export`, `rt_depth` in remote mode.
- Out of scope v1: block-compressed formats; packed formats (R11G11B10, R10G10B10A2,
  R9G9B9E5, R5G6B5, D24S8, D32S8); 3D textures (`depth > 1`); MSAA (`msSamp > 1`);
  local mode (unchanged byte-for-byte).

## Risks

| Risk | Mitigation |
|------|------------|
| Double sRGB correction | Branch on `SRGBCorrected()`: if True, bytes are already sRGB-encoded — do not re-apply gamma. |
| BGRA channel swap missed | Gate on `BGRAOrder()` and reorder to RGBA before `Image.fromarray`. vkcube color target is likely BGRA. |
| Row-padding assumption | Defensive `len(raw) != expected` check; bail to clear error rather than corrupt reshape. |
| Y-flip added by mistake | `GetTextureData` is top-down; Pillow `fromarray` is top-down — do NOT flip. |
| MSAA ambiguity | Reject `msSamp > 1` (mirror `tex_stats` guard) in remote decode path. |
| Mip dimension off-by-one | Use `max(1, dim >> mip)` per level; `tex.width`/`tex.height` are mip-0 only. |
| Packed/block format garbage | Guard `tex.format.type == ResourceFormatType.Regular`; emit `-32002` for the rest. |
| rt_export/rt_depth lack TextureDescription | Resolve `Descriptor.resource` → `state.tex_map[int(resource)]` to obtain width/height/format. |
| Mock divergence in tests | `mock_renderdoc.py` lacks `ResourceFormatType`; must add `ResourceFormatType` IntEnum and extend `ResourceFormat` before new unit tests run. |
| Local-mode regression | All new decode logic is strictly under `if state.is_remote:`; existing `SaveTexture` branch is byte-for-byte unchanged. |
| Depth normalization is relative | Document that remote depth PNG is contrast-stretched for visibility; raw bytes available via `tex_raw`. |
