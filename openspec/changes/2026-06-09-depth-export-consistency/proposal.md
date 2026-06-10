# OpenSpec: 2026-06-09-depth-export-consistency

## Summary

Unify local and remote depth export so both modes produce identical grayscale
mode-L PNG files with min-max normalisation. Local mode currently calls
`SaveTexture`, producing an RGBA PNG with raw linear depth in the red channel;
remote mode uses `GetTextureData` + `_decode_texture_png(is_depth=True)`,
producing grayscale mode-L. Same capture, different file per mode.

## Context and Motivation

The divergence was introduced unintentionally: the remote path added in PR #237
chose `_decode_texture_png` for cross-host portability (no filesystem access on
the remote GPU machine), but the local path was left on the original
`SaveTexture` route. Consequences:

- `rdc assert-image` golden comparisons break when the reference was captured
  in one mode and the assertion runs in the other.
- Users inspecting depth PNGs in local mode see RGBA files (depth in red
  channel, G=B=0) rather than grayscale, which is surprising and
  undocumented.
- vkcube real capture example: local produces R 243-255 / G=0 / B=0 RGBA;
  remote produces grayscale 0-255. Both are technically lossless depth
  representations but visually and structurally incompatible.

The fix is straightforward: make `_handle_rt_depth` use
`GetTextureData` + `_decode_texture_png(is_depth=True)` regardless of
`state.is_remote`, matching the precedent already set by `_handle_tex_raw`
which calls `GetTextureData` without an `is_remote` guard.

Color export (`_handle_rt_export`, `_handle_tex_export`) keeps `SaveTexture`
locally; this change is scoped to depth only.

## Behaviour Change (changelog-worthy)

**Before**: `rdc rt <EID> --depth -o depth.png` in local mode writes an RGBA
PNG. Depth occupies the R channel as linear float-to-8-bit. G and B channels
are zero. Alpha is 255.

**After**: same command writes a grayscale mode-L PNG with min-max stretch
(same format as remote mode). Cross-mode golden files are now byte-identical
for decodable formats.

This is a breaking change for any script that reads the R channel of a
locally-exported depth PNG. It is changelog-worthy and must appear in the
release notes.

## Design

### Primary path: unified GetTextureData

In `_handle_rt_depth`, replace the local `SaveTexture` branch with the same
call used by `_export_remote`:

```python
# current local branch (remove)
texsave = _make_texsave(state.rd, depth.resource)
success = state.adapter.controller.SaveTexture(texsave, str(temp_path))
...

# replacement (both local and remote)
tex = state.tex_map.get(int(depth.resource))
if tex is None:
    return _error_response(..., "depth target not found in tex_map"), True
return _export_remote(request_id, state, tex, depth.resource, temp_path, 0, is_depth=True)
```

`_export_remote` already calls `GetTextureData` + `_decode_texture_png` and is
mode-agnostic: it uses `state.adapter.controller` which is available in local
mode. The function does not check `state.is_remote`. The existing remote branch
in `_handle_rt_depth` is removed; there is now one branch.

### Fallback: combined depth-stencil formats

`_decode_texture_png` returns `None` for non-Regular formats (except the
packed HDR color formats R11G11B10/R9G9B9E5 added in #240, which never occur
as depth targets). The combined depth-stencil formats (`D16S8`, `D24S8`,
`D32S8`, `S8`) are all non-Regular (mock values 19-22 in
`ResourceFormatType`). When `_export_remote`
returns -32002 for such a format in local mode, `SaveTexture` can still export
them (RenderDoc handles the split internally). To preserve this local
capability:

In `_handle_rt_depth`, after `_export_remote` returns, inspect the result:

- If `_export_remote` succeeded, return it.
- If it returned -32002 **and** `state.is_remote is False`: fall back to
  `SaveTexture` on `depth.resource` and return that result.
- If it returned -32002 **and** `state.is_remote is True`: return the -32002
  error unchanged (remote behaviour is unchanged).

Contract note (verified against `texture.py:66-96`): `_export_remote` writes
the PNG to `temp_path` itself and returns a complete JSON-RPC response tuple
`(dict, True)`; the handler inspects `resp.get("error", {}).get("code")`. All
`_export_remote` failure modes share code -32002 — GetTextureData exception,
empty data, decode rejection (`_decode_texture_png` returning `None`), and
file-write `OSError` — so the local fallback intentionally triggers on **any**
of them, not only decode rejection. This is acceptable: it subsumes the
pre-change local behaviour (SaveTexture only), and the worst case is a second
failure ("SaveTexture failed") replacing the original error message.
Distinguishing decode rejection specifically would require splitting
`_export_remote` into fetch/decode steps or adding a structured error reason;
that refactor is deliberately not done.

Remote behaviour is therefore identical to pre-change. Local behaviour for
decodable formats changes (grayscale instead of RGBA). Local behaviour for
combined depth-stencil formats is preserved via SaveTexture fallback (result is
still RGBA, but these formats were never part of any cross-mode golden workflow
since remote could not decode them at all).

The fallback does not need to be documented as stable API; it exists purely to
avoid a regression on combined depth-stencil formats.

### `snapshot.py` comment

The existing comment on the `rt_depth` call in `snapshot.py` (line 63) already
reads "surface a warning when remote depth decode is unsupported (e.g. D24S8 or
MSAA)". After this change, D24S8 will succeed locally via fallback; the comment
should be updated to "depth decode unsupported (combined depth-stencil or MSAA
in remote mode)".

## Regression Risk: Formats Where `_decode_texture_png` Returns None

The following formats currently export locally via `SaveTexture` but will be
routed through `_decode_texture_png` first. Formats where the decoder returns
`None` will fall back to `SaveTexture` (hybrid behaviour). Formats where the
decoder succeeds will switch to grayscale output.

| Format | ResourceFormatType | Regular? | Decoder result | After change |
|--------|--------------------|----------|----------------|--------------|
| D16 | Regular (compType=Depth, cbw=2) | Yes | succeeds | grayscale L (behaviour change) |
| D32_FLOAT | Regular (compType=Depth, cbw=4) | Yes | succeeds | grayscale L (behaviour change) |
| D24_UNORM (pure, no stencil) | Regular (compType=Depth, cbw=4) | Yes | succeeds | grayscale L (behaviour change) |
| D16S8 | D16S8 (type=19) | No | None → -32002 | SaveTexture fallback (unchanged) |
| D24S8 | D24S8 (type=20) | No | None → -32002 | SaveTexture fallback (unchanged) |
| D32S8 | D32S8 (type=21) | No | None → -32002 | SaveTexture fallback (unchanged) |
| S8 | S8 (type=22) | No | None → -32002 | SaveTexture fallback (unchanged) |
| MSAA depth | Regular (msSamp > 1) | Yes but MSAA | None → -32002 | SaveTexture fallback (local only) |

The MSAA depth fallback is a local-only preservation and a **documented
divergence**: local MSAA depth stays on SaveTexture (RGBA output), remote MSAA
depth stays -32002, exactly as before this change. This divergence is accepted
and does not need unification.

D24_UNORM pure depth (no stencil) is Regular and goes through the same decode
path as D16/D32_FLOAT; it needs **no special capture verification** beyond the
unit tests — manual real-GPU verification on D16 covers the Regular depth
path.

## Risks

- **Unit test `test_tex_export_local_uses_savetexture`** (test_tex_stats_handler.py
  line 802) tests that tex_export routes through SaveTexture locally. This is
  unchanged. However `TestRtDepth.test_happy_path` (test_binary_daemon.py line
  403) will break differently than a missing-stub failure: `_make_handler_state`
  already stubs `GetTextureData` (returning 1024 filler bytes), but its
  `tex_map` contains only texture 42 while the pipe's depth target is
  ResourceId(500). After this change the handler hits the `tex_map` lookup
  first and returns -32001 "depth target not found". The fix is to add a depth
  `TextureDescription` (ResourceId 500, Regular depth format, e.g. D16) to the
  mock's textures/tex_map and make `GetTextureData` return correctly-sized
  bytes for it.

- **tex_map miss in local mode**: the unified path requires the depth resource
  to be present in `state.tex_map` (built from `GetTextures()` at
  daemon_server.py:446); the old local path did not. A miss returns -32001 and
  does **not** trigger the SaveTexture fallback (which keys on -32002). Real
  captures always enumerate depth targets as textures, so this is a
  mock-environment concern only, but tests must keep tex_map consistent.

- **assert-image golden files**: scan result (2026-06-09, f36b41e):
  `find tests -iname "*depth*"` finds no depth PNG assets; the repo contains no
  golden PNGs under `tests/`; no e2e or assert-image test reads the red channel
  of a depth PNG (snapshot e2e asserts only `color0.png` exists). **No golden
  update is required.** Any user-side goldens captured in local mode will
  differ; covered by the changelog entry.

- **Docs**: release notes entry required.

## Out of Scope

- Color export unification (`_handle_rt_export`, `_handle_tex_export`): no
  change.
- Remote behaviour: no change for any format.
- `rdc rt --depth` CLI flag (covered by 2026-06-09-rt-depth-flag).
