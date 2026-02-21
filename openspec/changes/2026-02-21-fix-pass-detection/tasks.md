# Tasks: Fix Pass Detection

## Phase A: Tests first

- [ ] Add unit test: container node (BeginPass|EndPass) is skipped
- [ ] Add unit test: complex scene — named groups within render pass detected as passes
- [ ] Add unit test: simple scene — render pass itself is the pass when no groups exist
- [ ] Fix `test_query_service_pass_hierarchy` — use hierarchical action tree (draws as children of begin_pass)
- [ ] Fix `test_daemon_passes_handler` — same hierarchical fix
- [ ] Verify `test_count_passes` in test_count_shadermap still passes

## Phase B: Implementation

- [ ] Add `_subtree_has_draws(action)` helper in query_service.py
- [ ] Add `_subtree_stats(action, sf)` helper — collects name, begin_eid, end_eid, draws, dispatches, triangles
- [ ] Rewrite `_build_pass_list_recursive` with new algorithm
- [ ] Update `_count_passes` to use `_build_pass_list`

## Phase C: Integration

- [ ] Add GPU test: `rdc passes` on real capture returns correct pass names (no container nodes)
- [ ] `pixi run check` passes (664+ tests, zero lint/type errors, 80%+ coverage)

## Phase D: Verify

- [ ] Manual test: `rdc open tests/fixtures/vulkan_samples/render_passes.rdc && rdc passes` shows semantic groups
- [ ] Manual test: `rdc open tests/fixtures/hello_triangle.rdc && rdc passes` shows render pass
