# OpenSpec: 2026-06-09-rt-depth-flag

## Summary

Add `--depth` flag to `rdc rt` so `rdc rt <EID> --depth -o depth.png` exports the raw
depth attachment via the existing `rt_depth` VFS route.

## Context and Motivation

Issue #236's verify section literally used `rdc rt --eid 500 --depth` as the canonical
test command. The backend was shipped in PR #237: VFS route
`/draws/<eid>/targets/depth.png` → handler `rt_depth` is registered in `vfs/router.py`
line 152 and works in both local and remote (pid==0) modes. The CLI plumbing was never
added, leaving users with no ergonomic path to the depth attachment.

## Design

### New flag: `--depth`

```
rdc rt <EID> [--depth] [-o output.png] [--raw]
```

When `--depth` is passed, `rt_cmd` routes to
`/draws/{eid}/targets/depth.png` instead of `/draws/{eid}/targets/color{target}.png`.

### `--target` sentinel change

`--target` currently defaults to `0`. Click cannot distinguish "user passed `--target 0`"
from "user did not pass `--target`" when the default is `0`. To detect mutual exclusion:

- Change `--target` default in the Click decorator to `None` (sentinel).
- In the help text, document the default as `0` explicitly.
- In `rt_cmd` logic: if `--depth` is set and `--target` is not `None`, raise
  `click.UsageError("--depth and --target are mutually exclusive")`.
- If `--depth` is not set and `--target is None`, use `0` as the effective target.

This is a breaking change to the `--target` parameter type annotation (from `int` to
`int | None`) but not to user-visible defaults.

### Interaction with `--overlay`

`--overlay` takes priority: if `--overlay` is provided, the existing overlay path runs
unchanged and `--depth` is silently ignored (no interaction needed; depth overlay is a
separate concept). Document in help text.

### Distinction: `--overlay depth` vs `--depth`

These are fundamentally different operations:

- `--overlay depth` calls `rt_overlay` with `overlay="depth"`, which asks RenderDoc to
  render the depth *overlay visualization* on top of the colour buffer. Output is a
  colour-mapped image rendered by RenderDoc's overlay engine.
- `--depth` exports the raw depth/stencil attachment texture at the draw's framebuffer
  bind point, via the `rt_depth` handler. Output is the raw depth buffer as PNG.

The `rdc rt` help text must call this distinction out explicitly.

### Shell completion: `_complete_rt_target`

`_complete_rt_target` filters `color\d+\.png` filenames and therefore already excludes
`depth.png`. No change needed; `--depth` is a boolean flag without a completeable value.

### Docs surface

`scripts/gen-commands.py` introspects Click command objects to produce
`docs-astro/src/data/commands.json`, which feeds the Astro-based command reference.
`scripts/gen-skill-ref.py` generates `src/rdc/_skills/references/commands-quick-ref.md`.
Both are regenerated via `pixi run gen-commands` and `pixi run gen-skill-ref`. The new
flag will appear automatically once regenerated; no manual doc edits required.

## Risks

- **CLI surface change**: `--target` default changes from `int(0)` to `None` internally.
  Any caller that inspects `rt_cmd`'s Click parameter objects programmatically (e.g.
  test introspection) may need updating.
- **Shell completion**: no impact; `_complete_rt_target` is not invoked for `--depth`.
- **Docs regen**: both `check-commands` and `check-skill-ref` CI checks will fail if
  regenerated artifacts are not committed alongside the implementation.
- **Remote mode**: `_export_vfs_path` already handles `pid==0` (remote daemon) via
  `_deliver_binary`; no special casing needed for `--depth`.
