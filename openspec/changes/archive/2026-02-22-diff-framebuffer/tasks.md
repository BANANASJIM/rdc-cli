# Tasks: diff-framebuffer

## Phase A — Unit tests: library

- [ ] Create `tests/unit/test_diff_framebuffer.py`
- [ ] Test identical renders → `FramebufferDiffResult(identical=True, diff_pixels=0)`
- [ ] Test different renders → `identical=False, diff_pixels > 0`
- [ ] Test `eid=None` → `rt_export` called WITHOUT `eid` param (daemon defaults to last event)
- [ ] Test explicit `eid=50` → `rt_export` called with `eid=50` on both
- [ ] Test `target=1` forwarded in `rt_export` params
- [ ] Test `threshold=0.5` forwarded to `compare_images`
- [ ] Test `diff_output` path forwarded; `result.diff_image` populated
- [ ] Test `diff_image=None` when no differing pixels
- [ ] Test daemon A `rt_export` failure → `(None, error string)`
- [ ] Test daemon B `rt_export` failure → `(None, error string)`
- [ ] Test `compare_images` raises `ValueError` → `(None, "size mismatch: ...")`
- [ ] Test `compare_images` raises `FileNotFoundError` → `(None, "export file not found: ...")`
- [ ] Test `compare_images` raises `PIL.UnidentifiedImageError` → `(None, "invalid image: ...")`
- [ ] Test all `FramebufferDiffResult` fields populated correctly (eid_a, eid_b, target, total_pixels, diff_ratio)

## Phase B — Unit tests: CLI

- [ ] Test `--framebuffer` identical → stdout `"identical\n"`, exit 0
- [ ] Test `--framebuffer` different → stdout contains `"diff: N/M pixels (R%)"`, exit 1
- [ ] Test EID info in text output: `"eid_a=..."` and `"eid_b=..."`
- [ ] Test `--diff-output` path appears in output when `diff_image` is set
- [ ] Test no `"diff image:"` line when `diff_image=None`
- [ ] Test `--json` identical → valid JSON with `"identical": true`, exit 0
- [ ] Test `--json` different → JSON contains all required fields, exit 1
- [ ] Test `--json` `diff_image` null when no diff file
- [ ] Test error → stderr message, exit 2
- [ ] Test `"framebuffer"` no longer triggers stub message `"not yet implemented"`
- [ ] Test `--target 2` forwarded to `compare_framebuffers`
- [ ] Test `--threshold 1.5` forwarded
- [ ] Test `--eid 100` forwarded
- [ ] Test `--diff-output /tmp/d.png` forwarded
- [ ] Test no `--eid` → `eid=None` forwarded

## Phase C — Implementation: `src/rdc/diff/framebuffer.py`

- [ ] Create `src/rdc/diff/framebuffer.py`
- [ ] Define `FramebufferDiffResult` frozen dataclass (fields: `identical`, `diff_pixels`, `total_pixels`, `diff_ratio`, `diff_image`, `eid_a`, `eid_b`, `target`)
- [ ] Implement `compare_framebuffers(ctx, *, target, threshold, eid, diff_output, timeout_s)`:
  - Build `rt_export` params: `{"target": target}`, add `"eid": eid` only if not None
  - Query `rt_export` via `query_both` concurrently
  - Validate both responses present; return error string on failure
  - Delegate to `compare_images(Path(path_a), Path(path_b), threshold, diff_output)`
  - Catch `ValueError`, `FileNotFoundError`, `PIL.UnidentifiedImageError`; return `(None, message)`
  - Return `(FramebufferDiffResult(...), "")` on success
- [ ] Verify Phase A tests pass: `pixi run test -k test_diff_framebuffer`

## Phase D — Implementation: CLI wiring

- [ ] In `src/rdc/commands/diff.py`:
  - Remove `"framebuffer"` from `_MODE_STUBS`
  - Add `--target`, `--threshold`, `--eid`, `--diff-output` options to `diff_cmd`
  - Import `compare_framebuffers` from `rdc.diff.framebuffer`
  - Add `if mode == "framebuffer":` branch: call `compare_framebuffers`, render, exit
  - Implement `_render_framebuffer(result, output_json, threshold)`: text and JSON output
- [ ] Verify Phase B tests pass: `pixi run test -k test_diff_framebuffer`

## Phase E — Final verification

- [ ] `pixi run lint` — zero ruff errors
- [ ] `pixi run test` — all unit tests green, coverage >= 80%

## Phase F — GPU integration test

- [ ] In `tests/integration/test_daemon_handlers_real.py`:
  - Add `test_diff_framebuffer_self_identical_real`: self-diff `hello_triangle.rdc`; assert `identical=True`, `diff_pixels=0`
  - Add `test_diff_framebuffer_default_eid`: verify `rt_export` succeeds without explicit EID
- [ ] Run: `RENDERDOC_PYTHON_PATH=... pixi run test-gpu -k test_diff_framebuffer`

## Phase G — Completion

- [ ] Multi-agent code review — zero P0/P1 blockers
- [ ] Archive openspec, update vault, PR
