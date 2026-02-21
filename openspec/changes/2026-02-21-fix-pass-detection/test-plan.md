# Test Plan: Fix Pass Detection

## Scope

### In scope

- Pass detection algorithm (`_build_pass_list_recursive`)
- Pass counting (`_count_passes`)
- Daemon handler for `passes` / `pass` methods
- GPU integration test with real capture

### Out of scope

- `walk_actions` pass tracking
- VFS tree_cache pass population (unchanged behavior)
- CLI output formatting

## Test Matrix

| Layer | What | Where |
|-------|------|-------|
| Unit | Pass detection algorithm | `test_query_service_pass_hierarchy` |
| Unit | Container node filtering | new test |
| Unit | Simple scene (no sub-groups) | new test |
| Unit | Complex scene (named groups) | new test |
| Unit | Pass count aggregation | `test_count_passes` |
| Unit | Daemon passes handler | `test_daemon_passes_handler` |
| GPU | Real capture pass detection | `test_daemon_handlers_real.py` |

## Cases

### Happy path

1. **Simple scene**: BeginPass action has direct draw children (no groups)
   → the render pass itself is a pass
   - Input: `[begin_pass(children=[draw1]), end_pass]`
   - Expected: 1 pass with name of begin_pass

2. **Complex scene**: BeginPass action has named child groups with draw descendants
   → each named group is a pass
   - Input: `[begin_pass(children=[group_a(children=[draw1,draw2]), group_b(children=[draw3])]), end_pass]`
   - Expected: 2 passes ["group_a", "group_b"]

3. **Multiple render passes**: Two render passes, each with sub-groups
   → all groups from all render passes
   - Input: `[rp1(children=[shadow, main]), rp1_end, rp2(children=[post]), rp2_end]`
   - Expected: 3 passes ["shadow", "main", "post"]

### Edge / error paths

4. **Container node filtering**: Action with both BeginPass|EndPass flags
   → skipped, recurse into children
   - Input: `[container(flags=BeginPass|EndPass, children=[rp(flags=BeginPass, children=[group])])]`
   - Expected: 1 pass (the group), not the container

5. **Empty render pass**: BeginPass with no children
   → no passes (nothing to show)

6. **Mixed children**: BeginPass with some leaf draws and some groups
   → only groups with draw descendants count as passes

### Regression

7. **Existing count tests**: `_build_action_tree()` in test_count_shadermap still returns 2 passes
8. **count_from_actions("passes")** still returns correct count
9. **Pass detail by index/name** still works

## Assertions

- `get_pass_hierarchy(actions)["passes"]` returns correct count and names
- Each pass has: name, draws (count of Drawcall-flagged descendants)
- `_count_passes(actions)` == `len(get_pass_hierarchy(actions)["passes"])`
- Container nodes (BeginPass|EndPass) never appear in pass list
- Simple scenes (no groups) → render pass name used
- Complex scenes (groups) → group names used

## Risks & Rollback

- **Risk**: `walk_actions` still uses old pass tracking for `filter_by_pass`.
  This means `count_from_actions(actions, "draws", pass_name="Shadow")` still
  works with BeginPass-named actions but not with group names.
  **Mitigation**: Acceptable for now; can update `walk_actions` in a follow-up.

- **Rollback**: Revert the single commit on `fix/pass-detection` branch.
