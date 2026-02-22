# Proposal: image-compare (Phase 3A)

## Summary

Add `src/rdc/image_compare.py` — a standalone utility module for pixel-level
PNG comparison — and a `rdc assert-image` CLI command that wraps it. No daemon
involvement. Pure CLI-side file I/O using Pillow and numpy.

Prerequisite for `diff-framebuffer` (Phase 3B) and CI-side image regression
assertions (Phase 3C).

## Design References

- `命令总览.md` — `rdc assert-image` is Phase 3A (listed under 工具 section)
- `设计原则.md` — exit codes: 0 = match, 1 = differs, 2 = error (diff semantics)
- `规划/Roadmap.md` — image-compare is P1 in Phase 3A, prerequisite for diff-framebuffer

## Changes

### New files

| File | Description |
|------|-------------|
| `src/rdc/image_compare.py` | `CompareResult` dataclass + `compare_images()` |
| `src/rdc/commands/assert_image.py` | `assert_image_cmd` Click command |
| `tests/unit/test_image_compare.py` | Utility module unit tests |
| `tests/unit/test_assert_image_command.py` | CLI command unit tests |

### Modified files

| File | Change |
|------|--------|
| `pyproject.toml` | Move `Pillow>=10.0` and `numpy>=1.24` from optional to core deps |
| `src/rdc/cli.py` | Register `assert_image_cmd` as `"assert-image"` |

## Implementation Details

### CompareResult dataclass

```python
@dataclass(frozen=True)
class CompareResult:
    identical: bool        # True iff diff_ratio <= threshold
    diff_pixels: int       # count of pixels where any channel differs
    total_pixels: int      # width * height
    diff_ratio: float      # diff_pixels / total_pixels * 100.0 (percentage)
    diff_image: Path | None  # path to saved diff PNG, or None
```

### compare_images() function

```python
def compare_images(
    path_a: Path,
    path_b: Path,
    threshold: float = 0.0,
    diff_output: Path | None = None,
) -> CompareResult:
```

Steps:
1. Open both images with `PIL.Image.open()`, convert to RGBA.
2. If dimensions differ: raise `ValueError("size mismatch: {a} vs {b}")`.
3. `np.array(..., dtype=np.uint8)` for both, compute pixel mask.
4. `mask = np.any(arr_a != arr_b, axis=2)` → diff_pixels, diff_ratio.
5. `identical = diff_ratio <= threshold`.
6. If `diff_output` and `diff_pixels > 0`: red-on-grayscale diff image.
7. Return `CompareResult(...)`.

### CLI command

```
rdc assert-image <expected> <actual> [--threshold N] [--diff-output PATH] [--json]
```

- Exit 0: match (within threshold)
- Exit 1: differs (beyond threshold)
- Exit 2: error (size mismatch, file not found, invalid image)

Default output: `match` or `diff: 1234/307200 pixels (0.40%)`
JSON output: all CompareResult fields + threshold.

### Threshold semantics

`--threshold N` is a float percentage (0.0–100.0). Default 0.0 = exact match.
Comparison is `diff_ratio <= threshold` (inclusive).

## Scope

| Component | Lines |
|-----------|-------|
| `src/rdc/image_compare.py` | ~60 |
| `src/rdc/commands/assert_image.py` | ~55 |
| `src/rdc/cli.py` (registration) | ~2 |
| `pyproject.toml` (deps) | ~4 |
| `tests/unit/test_image_compare.py` | ~120 |
| `tests/unit/test_assert_image_command.py` | ~80 |
| **Total** | **~320** |
