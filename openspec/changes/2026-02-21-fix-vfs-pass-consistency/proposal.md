# fix/vfs-pass-consistency — 3 Bug Fixes

## Summary

Fix three consistency issues discovered during Vulkan Sample capture testing
(dynamic_uniform_buffers, hdr) after Phase 2.7:

1. `rdc draws` PASS column shows raw API name (`vkCmdBeginRenderPass(...)`) while
   `rdc passes` shows friendly name (`Colour Pass #1 (...)`) — inconsistent.
2. VFS `/draws/<eid>/bindings/` and `/cbuffer/` intermediate directories are empty
   (tree shows dir but `ls` returns no children).
3. `_friendly_pass_name` cannot parse `(Clear)` format (no `C=`/`D=` markers)
   producing suffix-less output.

## Motivation

Users expect `rdc draws` PASS column to match `rdc passes` output. Empty
intermediate VFS directories break navigation. The `(Clear)` format is common
in real Vulkan captures and must produce meaningful friendly names.

## Design

### Fix 1: draws PASS column uses friendly name

- Add `pass_name_for_eid(eid, passes)` helper in `query_service.py`
- Cache pass list on `VfsTree` during `build_vfs_skeleton` (avoids re-walking
  the action tree on every `rdc draws` call)
- In `_handle_draws`, use cached `state.vfs_tree.pass_list` and
  `pass_name_for_eid` instead of `a.pass_name`

### Fix 2: VFS bindings/cbuffer intermediate directories

- Add two intermediate directory routes in `router.py`:
  - `/draws/<eid>/cbuffer/<set>` → dir
  - `/draws/<eid>/bindings/<set>` → dir
- Update `_SHADER_PATH_RE` in `_helpers.py` to also match `bindings|cbuffer`
  paths so `_ensure_shader_populated` triggers `populate_draw_subtree`
- In `tree_cache.py:populate_draw_subtree`, iterate shader reflections to
  discover set/binding numbers and populate children of bindings/ and cbuffer/

### Fix 3: _friendly_pass_name handles (Clear) format

- When `color_count == 0` and `has_depth == False` but `"(" in api_name`,
  extract the parenthesized content verbatim as the suffix (e.g. `(Clear)`)
  rather than fabricating a target count.
