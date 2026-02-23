# Tasks: Phase 5 — pick-pixel

## Mock

- [ ] Add `_pick_pixel_map: dict[tuple[int, int], PixelValue]` to `MockReplayController.__init__` in `tests/mocks/mock_renderdoc.py`
- [ ] Add `PickPixel(self, texture_id, x, y, sub, comp_type) -> PixelValue` method to `MockReplayController`

## Handler

- [ ] Add `_handle_pick_pixel(request_id, params, state)` to `src/rdc/handlers/pixel.py`
  - [ ] Guard: no adapter → error -32002
  - [ ] Guard: missing `x` or `y` → error -32602
  - [ ] Seek: call `_set_frame_event(state, eid)`
  - [ ] RT lookup: `GetOutputTargets()`, filter non-null, validate `target_idx`
  - [ ] MSAA guard: check `tex.msSamp > 1` → error -32001
  - [ ] Build `sub` and `comp_type` using `state.rd`
  - [ ] Call `controller.PickPixel(rt_rid, x, y, sub, comp_type)`
  - [ ] Return result dict with `{x, y, eid, target: {index, id}, color: {r, g, b, a}}`
- [ ] Register `"pick_pixel": _handle_pick_pixel` in `HANDLERS` dict

## Command

- [ ] Create `src/rdc/commands/pick_pixel.py` with `pick_pixel_cmd`
  - [ ] Arguments: `x: int`, `y: int`, `eid: int | None`
  - [ ] Options: `--target` (default 0), `--json` / `use_json`
  - [ ] Human output: `r={r:.4f}  g={g:.4f}  b={b:.4f}  a={a:.4f}`
  - [ ] JSON output: delegate to `write_json(result)`

## CLI Registration

- [ ] Import `pick_pixel_cmd` in `src/rdc/cli.py`
- [ ] `main.add_command(pick_pixel_cmd, name="pick-pixel")`

## Unit Tests

- [ ] Create `tests/unit/test_pick_pixel_commands.py` — cover PP-U-01 through PP-U-14
- [ ] Create `tests/unit/test_pick_pixel_daemon.py` — cover PP-D-01 through PP-D-17

## GPU Integration Tests

- [ ] Add `test_pick_pixel_valid_rgba` to `TestDaemonHandlersReal` (PP-G-01)
- [ ] Add `test_pick_pixel_schema` (PP-G-02)
- [ ] Add `test_pick_pixel_target_nonzero` (PP-G-03)
- [ ] Add `test_pick_pixel_different_coords_differ` (PP-G-04)
- [ ] Add `test_pick_pixel_eid_echoed` (PP-G-05)

## Verification

- [ ] `pixi run lint` passes (ruff + mypy)
- [ ] `pixi run test` passes with zero failures
- [ ] New handler and command lines are covered (no uncovered branches)
- [ ] `rdc pick-pixel --help` renders correctly
