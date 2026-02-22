# Test Plan: diff-framebuffer

## Scope

### In scope
- `compare_framebuffers()`: `rt_export` fan-out, `compare_images` delegation
- `FramebufferDiffResult` dataclass fields and values
- Error paths: daemon failure, size mismatch, file-not-found, invalid image
- `--eid` flag forwarding to both daemons
- `--target N` forwarded to `rt_export` params
- `--threshold N` forwarded to `compare_images`
- `--diff-output PATH` forwarded; result `diff_image` populated
- CLI default text output (identical / diff line)
- CLI `--json` output schema
- Exit codes: 0=identical, 1=different, 2=error
- `"framebuffer"` removed from `_MODE_STUBS` (no longer exits 2 as stub)

### Out of scope
- `rt_depth` comparison
- Separate `--eid-a` / `--eid-b`
- Non-localhost daemons

## Test Matrix

| Layer | File | Runner |
|-------|------|--------|
| Unit — library | `tests/unit/test_diff_framebuffer.py` | pytest |
| Unit — CLI | `tests/unit/test_diff_framebuffer.py` | pytest + CliRunner |
| GPU | `tests/integration/test_daemon_handlers_real.py` | pytest -m gpu |

## Cases

### `compare_framebuffers()` — happy paths

| # | Description | Input | Expected |
|---|-------------|-------|----------|
| 1 | Identical renders | Mock `rt_export` returns same PNG on both sides; `compare_images` returns `identical=True, diff_pixels=0` | Returns `FramebufferDiffResult(identical=True, diff_pixels=0, ...)`, error string `""` |
| 2 | Different renders | `compare_images` returns `identical=False, diff_pixels=100` | Returns `FramebufferDiffResult(identical=False, diff_pixels=100, ...)` |
| 3 | Default EID (omitted) | `eid=None`; no `eid` key in `rt_export` params | `rt_export` called without `eid` param (daemon uses `state.current_eid` = last event) |
| 4 | Explicit `--eid` | `eid=50` | `rt_export` called with `eid=50` on both daemons |
| 5 | `--target 1` | `target=1` | `rt_export` params include `target=1` |
| 6 | `--threshold 0.5` | `threshold=0.5` | `compare_images` called with `threshold=0.5` |
| 7 | `--diff-output` path | `diff_output=Path("/tmp/d.png")`; `compare_images` returns `diff_image=Path("/tmp/d.png")` | `result.diff_image == Path("/tmp/d.png")` |
| 8 | `diff_image=None` when identical | `diff_output` given but `compare_images` returns `diff_pixels=0` → `diff_image=None` | `result.diff_image is None` |
| 9 | `FramebufferDiffResult` fields | See case 1 | `eid_a`, `eid_b`, `target`, `total_pixels`, `diff_ratio` all correctly populated |

### `compare_framebuffers()` — error paths

| # | Description | Input | Expected |
|---|-------------|-------|----------|
| 10 | Daemon A `rt_export` fails | Mock returns `(None, None, "both daemons failed")` | Returns `(None, "rt_export failed: ...")` |
| 11 | Daemon B `rt_export` fails | Mock returns `(resp_a, None, "")` | Returns `(None, "rt_export failed: ...")` |
| 12 | Size mismatch | `compare_images` raises `ValueError("size mismatch: ...")` | Returns `(None, "size mismatch: ...")` |
| 13 | Export file vanishes | `compare_images` raises `FileNotFoundError` | Returns `(None, "export file not found: ...")` |
| 14 | Invalid image file | `compare_images` raises `PIL.UnidentifiedImageError` | Returns `(None, "invalid image: ...")` |

### CLI — output format

| # | Description | Input | Expected |
|---|-------------|-------|----------|
| 15 | Identical — default text | `compare_framebuffers` returns `identical=True` | stdout `"identical\n"`, exit 0 |
| 16 | Different — default text | `identical=False, diff_pixels=1234, total_pixels=307200, diff_ratio=0.40` | stdout contains `"diff: 1234/307200 pixels (0.40%)"`, exit 1 |
| 17 | EID info printed | `eid_a=50, eid_b=50` | stdout contains `"eid_a=50"` and `"eid_b=50"` |
| 18 | `--diff-output` shown | `diff_image=Path("/tmp/d.png")` | stdout contains `"diff image: /tmp/d.png"` |
| 19 | No `--diff-output` line | `diff_image=None` | stdout does NOT contain `"diff image:"` |
| 20 | `--json` identical | `identical=True` | stdout is valid JSON with `"identical": true`, exit 0 |
| 21 | `--json` different | `identical=False` | stdout JSON has `"diff_pixels"`, `"diff_ratio"`, `"eid_a"`, `"eid_b"`, `"target"`, `"threshold"`, exit 1 |
| 22 | `--json` diff_image null | `diff_image=None` | JSON `"diff_image": null` |
| 23 | Error path → exit 2 | `compare_framebuffers` returns `(None, "size mismatch: ...")` | stderr contains error message, exit 2 |
| 24 | `_MODE_STUBS` no longer exits 2 | Invoke `diff_cmd` with `--framebuffer`, mock returns `identical=True` | Does NOT print "not yet implemented", exits 0 |

### CLI — option forwarding

| # | Description | Expected |
|---|-------------|----------|
| 25 | `--target 2` forwarded | `compare_framebuffers` called with `target=2` |
| 26 | `--threshold 1.5` forwarded | Called with `threshold=1.5` |
| 27 | `--eid 100` forwarded | Called with `eid=100` forwarded |
| 28 | `--diff-output /tmp/d.png` forwarded | Called with `diff_output=Path("/tmp/d.png")` |
| 29 | No `--eid` → `None` forwarded | Called with `eid=None` |

## GPU Integration

| # | Description | Expected |
|---|-------------|----------|
| 30 | Self-diff same capture `--framebuffer` | `identical=True`, `diff_pixels=0`, no error |
| 31 | `--target 0` resolves default EID | `rt_export` succeeds, export path exists on disk |

## Assertions

### Exit codes
- `0`: `result.identical is True`
- `1`: `result.identical is False`
- `2`: error (daemon failure, size mismatch, file error)

### JSON schema (`--json` success)
```json
{
  "identical": "<bool>",
  "diff_pixels": "<int, >= 0>",
  "total_pixels": "<int, > 0>",
  "diff_ratio": "<float, 0.0-100.0>",
  "diff_image": "<str | null>",
  "eid_a": "<int | null>",
  "eid_b": "<int | null>",
  "target": "<int, >= 0>",
  "threshold": "<float, >= 0.0>"
}
```

## Risks & Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| `rt_export` temp file deleted between RPC return and `compare_images` | `FileNotFoundError` | Treat as error, propagate clear message |
| Different image sizes across captures | `ValueError` from Pillow | Caught and returned as error string |
| Rollback | — | Revert branch; `_MODE_STUBS` re-addition restores stub behavior |
