# Tasks: 2026-06-09-rt-depth-flag

## T1: Implementation — `rt_cmd` CLI plumbing

- [ ] In `src/rdc/commands/export.py`, change `--target` default from `0` to `None`;
  update help text to read `"Color target index (default 0)"` (no user-visible change).
- [ ] Add `--depth` boolean flag (`is_flag=True`) to the `@click.command("rt")` decorator.
- [ ] In `rt_cmd` body (after the `--overlay` early-return, before `_export_vfs_path`):
  - Raise `click.UsageError("--depth and --target are mutually exclusive")` if
    `depth` is `True` and `target is not None`.
  - If `depth` is `True`: call
    `_export_vfs_path(f"/draws/{eid}/targets/depth.png", output, raw)`.
  - Otherwise: use `target if target is not None else 0` as the color index.

## T2: Unit tests

- [ ] Extend `TestRtCmd` in `tests/unit/test_export_commands.py` with four cases from
  test-plan.md: `test_rt_depth_routes_to_depth_png`,
  `test_rt_depth_with_explicit_target_raises_usage_error`,
  `test_rt_depth_target_none_defaults_to_color0`,
  `test_rt_depth_remote_pid0_writes_output`,
  `test_rt_depth_with_overlay_ignores_depth`.
- [ ] Run `pixi run test` — all pass.

## T3: Docs + completion regen

- [ ] Run `pixi run gen-commands` to regenerate `docs-astro/src/data/commands.json`.
- [ ] Run `pixi run gen-skill-ref` to regenerate
  `src/rdc/_skills/references/commands-quick-ref.md`.
- [ ] Verify `pixi run check-commands` and `pixi run check-skill-ref` pass (CI gate).
- [ ] Commit regenerated artifacts alongside the implementation.

## T4: Manual real-GPU verify

- [ ] Run the four manual steps from test-plan.md against a vkcube capture:
  local depth export, remote-proxy depth export, mutual-exclusion error, overlay
  depth regression.
- [ ] Confirm output PNG is non-empty and visually plausible depth greyscale.
