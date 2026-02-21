# Fix: Pass Detection Logic

## Summary

`rdc passes` incorrectly identifies render passes. Container nodes (e.g.,
`vkBeginCommandBuffer`) are falsely detected as passes due to aggregated
ActionFlags, and the actual semantic draw groups within render passes are
not recognized.

## Problem

In RenderDoc's action tree, parent nodes aggregate flags from all descendants.
A `vkQueueSubmit/vkBeginCommandBuffer` node contains both `BeginPass` and
`EndPass` in its flags (from `vkCmdBeginRenderPass` + `vkCmdEndRenderPass`
children). The current code checks `flags & _BEGIN_PASS` without filtering
containers, so it reports the command buffer as a pass.

Additionally, the semantic draw groups within a render pass (e.g., "Opaque
objects", "GUI") are the true "passes" from a graphics programmer's
perspective, but the current code only detects the Vulkan API-level
`vkCmdBeginRenderPass`.

### Current (wrong) output

```
NAME                                                              DRAWS
=> vkQueueSubmit(1)[0]: vkBeginCommandBuffer(ResourceId::785)    0
vkCmdBeginRenderPass(C=Load, D=Clear)                            29
```

### Expected output

```
NAME              DRAWS
Opaque objects    26
GUI               3
```

## Root Cause

`_build_pass_list_recursive` in `query_service.py` uses `flags & _BEGIN_PASS`
which matches:

1. Container nodes with aggregated `BeginPass|EndPass` flags
2. The actual `vkCmdBeginRenderPass` action

It should instead identify the **semantic sub-groups** within the render pass
that contain draw calls.

## Fix Design

### Algorithm

```
for each action:
  if has BeginPass AND NOT EndPass (actual render pass, not container):
    find child groups = children with their own children that contain draws
    if groups exist:
      each group is a "pass" (complex scene with named sections)
    else:
      the render pass itself is a "pass" (simple scene like hello_triangle)
  else if has children:
    recurse (skip containers, find nested render passes)
```

### Key distinction

| Node | Flags | Detection |
|------|-------|-----------|
| `vkQueueSubmit/vkBeginCommandBuffer` | `BeginPass\|EndPass` (aggregated) | Skip — container |
| `vkCmdBeginRenderPass` | `BeginPass` only | Enter — find sub-groups |
| "Opaque objects" | 0 (no special flags) | **Pass** — has draw children |
| "GUI" | 0 (no special flags) | **Pass** — has draw children |

### Handles both cases

- **Complex scene** (render_passes.rdc): render pass has named groups → groups are passes
- **Simple scene** (hello_triangle.rdc): render pass has direct draw calls → render pass itself is pass

## Scope

### In scope

- Fix `_build_pass_list_recursive` algorithm
- Add `_subtree_has_draws` and `_subtree_stats` helpers
- Update `_count_passes` to use `_build_pass_list`
- Fix unit tests to use correct hierarchical action trees

### Out of scope

- `walk_actions` / `filter_by_pass` (still uses BeginPass for pass tracking — acceptable for now)
- VFS route changes (pass VFS structure unchanged)
- CLI command changes (output format unchanged)
