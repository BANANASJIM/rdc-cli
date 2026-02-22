# Proposal: diff-framebuffer

## Summary

Implement `rdc diff <a.rdc> <b.rdc> --framebuffer`: pixel-level comparison of
render targets at the last draw event (or a specific EID) between two captures.
Uses the existing `query_both` dual-daemon infrastructure and `compare_images()`
from `src/rdc/image_compare.py`.

## Design References

- `设计/命令总览.md` — `rdc diff --framebuffer [--target N] [--threshold N] [--eid EID]`
- `设计/设计原则.md` — exit codes: 0=identical, 1=different, 2=error
- `设计/交互模式.md` — `rt_export`, `rt_depth` RPC methods

## Assumptions

- diff-infrastructure exists (`DiffContext`, `query_both`, `stop_diff_session`).
- `src/rdc/image_compare.py` (`compare_images`, `CompareResult`) is merged.
- Both daemons run on localhost: temp file paths returned by `rt_export` are
  directly accessible from the CLI process.

## Changes

### New files

| File | Description |
|------|-------------|
| `src/rdc/diff/framebuffer.py` | `compare_framebuffers()` — query + compare logic |
| `tests/unit/test_diff_framebuffer.py` | Unit tests |

### Modified files

| File | Change |
|------|--------|
| `src/rdc/commands/diff.py` | Remove `"framebuffer"` from `_MODE_STUBS`; add `--target`, `--threshold`, `--eid`, `--diff-output` options; wire handler |

## Implementation Details

### `src/rdc/diff/framebuffer.py`

```python
@dataclass(frozen=True)
class FramebufferDiffResult:
    identical: bool
    diff_pixels: int
    total_pixels: int
    diff_ratio: float      # percentage
    diff_image: Path | None
    eid_a: int
    eid_b: int
    target: int
```

```python
def compare_framebuffers(
    ctx: DiffContext,
    *,
    target: int = 0,
    threshold: float = 0.0,
    eid_a: int | None = None,
    eid_b: int | None = None,
    diff_output: Path | None = None,
    timeout_s: float = 30.0,
) -> tuple[FramebufferDiffResult | None, str]:
```

Steps:
1. Build `rt_export` params: `{"target": target}`. If `eid` is specified, add `"eid": eid`.
   When `eid` is omitted, `rt_export` defaults to `state.current_eid` which is the last
   event after capture load — no separate "last event" query needed.
2. Query `rt_export` from both daemons concurrently via `query_both(ctx, "rt_export", params)`.
3. Extract `path` strings from both responses; return error if either failed.
4. Call `compare_images(Path(path_a), Path(path_b), threshold, diff_output)`.
5. Return `FramebufferDiffResult(...)` populated from `CompareResult`.

### Error conditions

| Condition | Returned error string |
|-----------|----------------------|
| Either daemon `rt_export` fails | `"rt_export failed: <daemon A or B error>"` |
| `compare_images` raises `ValueError` | `"size mismatch: <details>"` |
| `compare_images` raises `FileNotFoundError` | `"export file not found: <path>"` |
| `compare_images` raises `PIL.UnidentifiedImageError` | `"invalid image: <path>"` |

### CLI wiring (`src/rdc/commands/diff.py`)

New options (added to `diff_cmd`):
```python
@click.option("--target",      default=0,    type=int,   help="Color target index (default 0)")
@click.option("--threshold",   default=0.0,  type=float, help="Max diff ratio %% to count as identical")
@click.option("--eid",         default=None, type=int,   help="Compare at specific EID (default: last draw)")
@click.option("--diff-output", default=None, type=click.Path(path_type=Path), help="Write diff PNG here")
```

`--eid` sets both `eid_a` and `eid_b` to the same value (cross-capture alignment
by event ID; separate `--eid-a`/`--eid-b` are out of scope for this phase).

Framebuffer handler path:
```python
if mode == "framebuffer":
    result, err = compare_framebuffers(
        ctx,
        target=target,
        threshold=threshold,
        eid_a=eid,
        eid_b=eid,
        diff_output=diff_output,
        timeout_s=timeout,
    )
    if result is None:
        click.echo(f"error: {err}", err=True)
        sys.exit(2)
    _render_framebuffer(result, output_json=output_json)
    sys.exit(0 if result.identical else 1)
```

### Output

**Default (text):**
```
identical                          # if identical
diff: 1234/307200 pixels (0.40%)   # if different
  eid_a=247 eid_b=247 target=0
  diff image: /tmp/diff.png        # only if --diff-output given
```

**`--json`:**
```json
{
  "identical": false,
  "diff_pixels": 1234,
  "total_pixels": 307200,
  "diff_ratio": 0.40,
  "diff_image": "/tmp/diff.png",
  "eid_a": 247,
  "eid_b": 247,
  "target": 0,
  "threshold": 0.5
}
```

## Not in Scope

- Depth target comparison (`rt_depth`): deferred to a follow-on spec.
- Separate `--eid-a` / `--eid-b` for independent EID selection.
- Per-channel (RGBA) diff breakdown.
- Streaming / tiled comparison for very large textures.
- Non-localhost daemon deployments (remote file paths are inaccessible).

## Scope

| Component | Lines |
|-----------|-------|
| `src/rdc/diff/framebuffer.py` | ~80 |
| `src/rdc/commands/diff.py` additions | ~45 |
| `tests/unit/test_diff_framebuffer.py` | ~150 |
| GPU integration test addition | ~25 |
| **Total** | **~300** |
