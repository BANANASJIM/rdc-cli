# Test Plan: 2026-06-09-depth-export-consistency

## Scope

### In scope
- Local `rt_depth` calls `GetTextureData` (not `SaveTexture`) for decodable formats
- Local `rt_depth` falls back to `SaveTexture` for D24S8 (non-Regular format)
- Remote path unchanged: `GetTextureData` + `_decode_texture_png(is_depth=True)`
- `rdc snapshot` depth file still written when depth target is decodable
- Grayscale mode-L PNG produced locally for D16 and D32_FLOAT formats
- Local and remote output byte-identical for the same decodable depth format

### Out of scope
- Color export paths (`rt_export`, `tex_export`)
- `--depth` CLI flag routing (covered by 2026-06-09-rt-depth-flag)
- Remote MSAA depth (already -32002 before change)

## Test Matrix

| Layer | Test Type | File |
|-------|-----------|------|
| Unit | local rt_depth calls GetTextureData | `tests/unit/test_tex_stats_handler.py` |
| Unit | local rt_depth produces grayscale L PNG | `tests/unit/test_tex_stats_handler.py` |
| Unit | local D24S8 falls back to SaveTexture | `tests/unit/test_tex_stats_handler.py` |
| Unit | remote path unchanged (D32_FLOAT grayscale) | `tests/unit/test_tex_stats_handler.py` (existing, must still pass) |
| Unit | remote D24S8 still returns -32002, no SaveTexture fallback | `tests/unit/test_tex_stats_handler.py` (new) |
| Unit | local == remote byte-identical for D16 (same mock data) | `tests/unit/test_tex_stats_handler.py` (new) |
| Unit | binary daemon happy path still works | `tests/unit/test_binary_daemon.py` (update mock) |
| Unit | snapshot depth.png written for decodable format | `tests/unit/test_snapshot_command.py` (update mock) |
| Manual | vkcube D16: local == remote byte-identical | see below |

## Unit Cases

### `test_rt_depth_local_calls_gettexturedata`

In `tests/unit/test_tex_stats_handler.py`, new test. Construct a D32_FLOAT
format (`compType=Depth`, `compByteWidth=4`, `ResourceFormatType.Regular`).
Build a local state (`is_remote=False`) with a `MockReplayController` whose
`GetTextureData` returns 4 packed float32 bytes `[0.0, 0.25, 0.75, 1.0]` for
a 2x2 texture, and whose `SaveTexture` raises `AssertionError` if called.
Call `_handle_rt_depth`. Assert:
- `result` is present (no error).
- The PNG at `result["path"]` is mode-L (grayscale).
- Pixel (0,0) == 0, pixel (1,1) == 255.
- `SaveTexture` was not called.

### `test_rt_depth_local_produces_grayscale_L`

Simplified variant: verify mode and min-max range for D16 (`compType=Depth`,
`compByteWidth=2`). Raw bytes: `struct.pack("<4H", 0, 16384, 49152, 65535)`.
Assert output PNG mode is `"L"`, pixel (0,0)==0, pixel (1,1)==255.

### `test_rt_depth_local_d24s8_fallback_uses_savetexture`

Construct a `D24S8` format (`ResourceFormatType.D24S8 = 20`, non-Regular).
Build local state. Stub `GetTextureData` to return 8 bytes of zeros (decoder
will return None because type is non-Regular). Stub `SaveTexture` to write a
valid PNG and record that it was called. Call `_handle_rt_depth`. Assert:
- `result` is present.
- `SaveTexture` was called exactly once.

This is the regression guard for combined depth-stencil fallback.

### `test_rt_depth_remote_d24s8_no_fallback` (new)

Construct a `D24S8` format (non-Regular), build a **remote** state
(`is_remote=True`) with `SaveTexture` stubbed to raise `AssertionError` if
called. Call `_handle_rt_depth`. Assert:
- response is an error with code -32002 (unchanged remote behaviour),
- `SaveTexture` was never called.

This pins the spec's "remote returns -32002 as-is" rule; no such test exists
today (existing remote depth tests cover the success path only).

### `test_rt_depth_local_remote_byte_identical_d16` (new)

Run `_handle_rt_depth` twice against the same D16 mock data and depth target,
once with `is_remote=False` and once with `is_remote=True`. Read both output
files and assert the PNG bytes are identical. This is the unit-level mirror of
manual Step 3.

### `test_rt_depth_remote_unchanged` (existing tests, must still pass)

Existing tests `test_rt_depth_remote_decodes_grayscale` and
`test_rt_depth_remote_d16_decodes_grayscale` in `test_tex_stats_handler.py`
must continue to pass unchanged. No modifications to these tests.

### Update `TestRtDepth.test_happy_path` in `test_binary_daemon.py`

`_make_handler_state` already stubs `GetTextureData` (1024 filler bytes), but
its `tex_map` holds only texture 42 while the pipe's depth target is
ResourceId(500); after the change the handler would return -32001 "depth
target not found". Update `_make_handler_state`: add a depth
`TextureDescription` (ResourceId 500, Regular D16-style format) to
`textures`/`tex_map` and make `GetTextureData` return correctly-sized bytes
for it (length must match `width * height * compCount * compByteWidth` or the
decoder rejects it). Keep the `SaveTexture` stub (still used by rt_export and
the fallback path).

### Update snapshot mock in `test_snapshot_command.py`

The `rt_depth` mock used by snapshot tests returns a pre-created PNG path.
This mock operates at the `call` level above the daemon handler, so it is
format-agnostic and does not need changes. Verify all existing snapshot tests
pass without modification.

## Manual Real-GPU Verify

Prerequisite: a vkcube capture with at least one draw event that has a D16
depth attachment (any 3D draw should qualify; `rdc rt <EID> --depth -o /dev/null`
to confirm).

### Step 1 — Local depth PNG

```sh
rdc open capture.rdc
rdc rt <EID> --depth -o /tmp/depth_local.png
```

Assert:
- exit code 0
- `/tmp/depth_local.png` is a valid PNG
- `python3 -c "from PIL import Image; img = Image.open('/tmp/depth_local.png'); print(img.mode)"` prints `L`
- Image is non-constant (visible grayscale gradient, not all-zero or all-one)

### Step 2 — Remote proxy depth PNG

```sh
rdc open capture.rdc --proxy host:port
rdc rt <EID> --depth -o /tmp/depth_remote.png
```

Assert:
- exit code 0
- `/tmp/depth_remote.png` exists and is non-empty

### Step 3 — Byte-identical comparison

```sh
diff /tmp/depth_local.png /tmp/depth_remote.png && echo "IDENTICAL"
```

Assert: prints `IDENTICAL`. Both files produced from the same capture at the
same EID must be byte-for-byte equal after this change.

### Step 4 — D24S8 fallback (if GPU has a D24S8 capture available)

```sh
rdc open d24s8_capture.rdc
rdc rt <EID> --depth -o /tmp/depth_d24s8.png
```

Assert:
- exit code 0 (fallback to SaveTexture, no error)
- `/tmp/depth_d24s8.png` exists (RGBA from SaveTexture; grayscale not guaranteed)
