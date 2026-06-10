# Remote texture export via GetTextureData + local decode

## Problem

Issue #236: `tex_export`, `rt_export`, and `rt_depth` all fail in remote mode.

The three export handlers unconditionally call `controller.SaveTexture(ts, path)`, which
writes a file on the **remote** daemon host's filesystem.  The client receives a path that
does not exist locally and cannot fetch it.  In the prior codebase all three handlers were
pre-emptively blocked by the `is_remote` guard (introduced alongside remote replay), so
callers received a JSON-RPC error before any file I/O is attempted.  The result is that
remote sessions have no supported path to export rendered targets — a major capability gap
for headless/cloud workflows where the daemon runs on a GPU server.

## Root Cause

`SaveTexture` is a RenderDoc API that writes to the path it is given, which in a remote
session is a path on the remote host.  There is no `SaveTexture`-over-network mode in the
RenderDoc Python API.  The `rt_overlay` handler is blocked for a related but distinct
reason: rendering overlays (Overdraw, Wireframe, etc.) requires GPU draw submission, which
is not safe over the remote JSON-RPC channel, so that guard is correct and must stay.

## Solution

Replace the `SaveTexture` call with `controller.GetTextureData(resource_id, sub)`, which
returns the raw texel bytes over JSON-RPC to the **client** process.  The client decodes the
bytes locally using numpy and Pillow (both already runtime dependencies) and writes the
result as a PNG at the caller-supplied path.

Two private helpers live in `handlers/_helpers.py`:

- `_decode_dtype(rd, comp_type, comp_byte_width) -> str | None` — a pure lookup table that
  maps a `(CompType, compByteWidth)` pair to a numpy dtype name, or `None` to reject pairs
  with no unambiguous 8-bit display mapping.
- `_decode_texture_png(rd, tex, raw, mip, *, is_depth) -> bytes | None` — decodes the tightly
  packed bytes into PNG bytes, or returns `None` when the format cannot be displayed.  It
  does not touch the filesystem; the caller writes the returned bytes.

A small handler-side helper `_export_remote(...)` in `handlers/texture.py` wraps the wire
fetch: it calls `GetTextureData`, guards against empty/`None` data, calls
`_decode_texture_png`, and writes the PNG.  Each export handler routes through it under
`if state.is_remote:`; the existing `SaveTexture` branch is left untouched for local mode.

### Decode behavior

- Only `ResourceFormatType.Regular` formats are decoded; every non-Regular format returns a
  clear `-32002` error `"format <Name> not supported for remote decode"`.
- Mip-level dimensions: `w = max(1, tex.width >> mip)`, `h = max(1, tex.height >> mip)`.
- Byte layout from `GetTextureData` is tightly packed, top-down (no row padding, no Y-flip).
- Dtype and 8-bit conversion are selected per `(compType, compByteWidth)` via `_decode_dtype`:
  - Float16 / Float32 (HDR linear) → tonemap: `clip(x, 0, 1)`, sRGB OETF, `*255`, uint8.
    Documented as contrast-clamped, not a raw dump.
  - UNorm8 / UNormSRGB8 → uint8 pass-through (sRGB bytes are display-ready, no extra gamma).
  - UNorm16 → uint16, scaled to 8-bit via divide-by-257.
  - SNorm8 / SNorm16 → read as the signed integer width, remapped `[-1, 1] -> [0, 255]`
    using the signed-int max as the divisor (normal-map friendly).
  - UInt8 / UInt16 → treated as display values (UInt16 also `/257`).
  - Depth8 / Depth16 / Depth32 → handled by the depth path (below).
- `BGRAOrder() == True` with `cc >= 3` → swap to RGBA channel order before save.
- Channel expansion for the COLOR path: cc=1 → repeat the single channel to RGB and add
  A=255 (full RGBA, **not** mode `L`); cc=2 → RG0 + A=255; cc=3 → add A=255; cc=4 → RGBA
  as-is.  Output is always RGBA.
- Depth path (`is_depth=True`, used only by `rt_depth`): take channel 0, auto-contrast via
  `(d - d_min) / (d_max - d_min)`, then `*255` uint8, written as mode `L`.  This matches
  RenderDoc's contrast-stretched depth display; it is not a raw depth dump — use `tex_raw`
  for exact bytes.

### Cleanly rejected (→ `-32002`, never a garbled image)

- `_decode_dtype` returns `None` for: Typeless, SInt, UScaled, SScaled, and any exotic
  component width not in the table.
- Non-`Regular` `ResourceFormatType`: block-compressed (BC1-7, ASTC), packed
  (R11G11B10, R10G10B10A2, R9G9B9E5, R5G6B5), and combined depth-stencil (D24S8, D32S8).
- MSAA (`msSamp > 1`).
- Length mismatch: `len(raw) != h * w * compCount * compByteWidth`.
- Empty / `None` data: `_decode_texture_png` returns `None` on empty input, and
  `_export_remote` additionally guards the `GetTextureData` return so a `None`/empty result
  yields `"no texture data returned"` rather than a `len(None)` crash.

### What stays blocked

`rt_overlay` remote guard is unchanged: overlay rendering requires GPU submission and cannot
be made safe over remote JSON-RPC.

### Known limitation / follow-up

Local mode (`SaveTexture`) renders depth with a RED colormap, while the remote path renders
depth as GRAY (mode `L`).  This local(RED)/remote(GRAY) depth-visualization inconsistency is
an accepted limitation for this change; aligning the two colormaps is deferred to a
follow-up.

### Scope

- In scope: `tex_export`, `rt_export`, `rt_depth` in remote mode; 3D textures (`depth > 1`)
  are exported by tiling depth slices vertically into one image.
- Out of scope: block-compressed formats; packed formats (R11G11B10, R10G10B10A2, R9G9B9E5,
  R5G6B5, D24S8, D32S8); MSAA (`msSamp > 1`); local mode (unchanged byte-for-byte).

## Risks

| Risk | Mitigation |
|------|------------|
| Double sRGB correction | UNormSRGB bytes pass through uint8 unchanged; only linear Float formats get the sRGB OETF. |
| BGRA channel swap missed | Gate on `BGRAOrder()` (with `cc >= 3`) and reorder to RGBA before `Image.fromarray`. |
| Signed data read as unsigned | SNorm is read at the signed integer width and remapped `[-1,1] -> [0,255]`; SInt is rejected outright. |
| Row-padding assumption | Defensive `len(raw) != expected` check; bail to clear `-32002` rather than corrupt reshape. |
| Y-flip added by mistake | `GetTextureData` is top-down; Pillow `fromarray` is top-down — do NOT flip. |
| MSAA ambiguity | Reject `msSamp > 1` (mirror `tex_stats` guard) in remote decode path. |
| Mip dimension off-by-one | Use `max(1, dim >> mip)` per level; `tex.width`/`tex.height` are mip-0 only. |
| Packed/block format garbage | Guard `tex.format.type == ResourceFormatType.Regular`; emit `-32002` for the rest. |
| Empty/None texture data crash | `_export_remote` guards the `GetTextureData` return before decode; empty → `-32002`. |
| rt_export/rt_depth lack TextureDescription | Resolve `Descriptor.resource` → `state.tex_map[int(resource)]` to obtain width/height/format. |
| Local-mode regression | All new decode logic is strictly under `if state.is_remote:`; existing `SaveTexture` branch is byte-for-byte unchanged. |
| Depth normalization is relative | Document that remote depth PNG is contrast-stretched for visibility; raw bytes available via `tex_raw`. |
| Local/remote depth colormap diverge | Accepted limitation (local RED vs remote GRAY); colormap alignment deferred to follow-up. |
