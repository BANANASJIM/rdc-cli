# Tasks: P2 Bugfix Batch

## Agent A: B75 — SDObject value extraction

- [ ] A1: Update `tests/mocks/mock_renderdoc.py` — Add `SDType` class with `basetype` field, update `SDBasic` to have `u`, `i`, `d`, `b`, `id` fields alongside `value`, add `type` attribute to `SDObject`
- [ ] A2: Add `_extract_sd_value(child: Any) -> str` helper to `src/rdc/handlers/query.py` — maps basetype enum to correct data field
- [ ] A3: Update `_handle_event()` in `src/rdc/handlers/query.py` — replace `child.AsString()` with `_extract_sd_value(child)` call
- [ ] A4: Update `tests/unit/test_draws_events_daemon.py` — add `TestB75SDValueExtraction` class with 8 test cases
- [ ] A5: Update `tests/unit/test_daemon_crash_regression.py` — update SD mock construction if needed to work with new `SDBasic` fields

## Agent B: Remote Export — `is_remote` guard

- [ ] B1: Add `is_remote` guard to `_handle_tex_export()` in `src/rdc/handlers/texture.py`
- [ ] B2: Add `is_remote` guard to `_handle_rt_export()` in `src/rdc/handlers/texture.py`
- [ ] B3: Add `is_remote` guard to `_handle_rt_depth()` in `src/rdc/handlers/texture.py`
- [ ] B4: Add `is_remote` guard to `_handle_pick_pixel()` in `src/rdc/handlers/pixel.py`
- [ ] B5: Add `test_pick_pixel_remote_rejected()` to `tests/unit/test_pick_pixel_daemon.py`
- [ ] B6: Add remote mode tests for `tex_export`, `rt_export`, `rt_depth` in existing texture test file or new file alongside existing tests

## Agent C: Daemon Survival — Windows creation flags

- [ ] C1: Update `popen_flags()` in `src/rdc/_platform.py` — add `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` flags
- [ ] C2: Add `TestPopenFlagsWindows` to `tests/unit/test_platform.py` — verify all three flag bits present

## Verification (main agent)

- [ ] V1: `pixi run lint` passes
- [ ] V2: `pixi run test` passes with zero failures
- [ ] V3: Windows VM: pull branch, run `rdc event 11` to verify B75 parameter values
