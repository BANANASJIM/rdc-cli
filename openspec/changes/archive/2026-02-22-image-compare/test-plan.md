# Test Plan: image-compare

## Unit Tests

All tests use synthetic images via `PIL.Image.new()` + `tmp_path`. No fixtures.

### compare_images() — happy paths

| # | Test | Validates |
|---|------|-----------|
| 1 | Identical images | `identical=True`, `diff_pixels=0`, `diff_ratio=0.0` |
| 2 | One pixel differs | `diff_pixels=1`, `identical=False` (threshold 0.0) |
| 3 | All pixels differ | `diff_pixels=total_pixels`, `diff_ratio=100.0` |
| 4 | Threshold below diff | ratio 6.25%, threshold 10.0 → `identical=True` |
| 5 | Threshold at boundary | ratio 6.25%, threshold 6.25 → `identical=True` (inclusive) |
| 6 | Threshold above diff | ratio 6.25%, threshold 5.0 → `identical=False` |
| 7 | Diff image written | `diff_output` provided → PNG exists, correct dims, red at changed pixels |
| 8 | Diff image not requested | `diff_output=None` → `diff_image is None` |
| 9 | Mode normalization | RGB vs RGBA identical content → `diff_pixels=0` |

### compare_images() — error paths

| # | Test | Validates |
|---|------|-----------|
| 10 | Size mismatch (width) | raises `ValueError` with "size mismatch" |
| 11 | Size mismatch (height) | raises `ValueError` |
| 12 | File not found | raises `FileNotFoundError` |
| 13 | Invalid image file | raises `PIL.UnidentifiedImageError` |

### CLI — exit codes and output

| # | Test | Validates |
|---|------|-----------|
| 14 | Identical → exit 0 | stdout contains "match" |
| 15 | Differs → exit 1 | stdout contains "diff:", pixel count, percentage |
| 16 | Size mismatch → exit 2 | stderr contains "error: size mismatch" |
| 17 | --threshold below → exit 0 | threshold allows diff |
| 18 | --threshold above → exit 1 | threshold rejects diff |
| 19 | --diff-output, differs | file written, exit 1 |
| 20 | --json identical | valid JSON, `identical=true`, exit 0 |
| 21 | --json differs | valid JSON, `identical=false`, exit 1 |
| 22 | --json error | exit 2, stderr has error, stdout empty |
| 23 | --help exits 0 | command registered |

## Regression

```bash
pixi run lint && pixi run test
```
