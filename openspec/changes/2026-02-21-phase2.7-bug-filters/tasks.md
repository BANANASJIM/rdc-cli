# Tasks: phase2.7-bug-filters

## Phase A: Tests first

### Fix 1: shaders stage filter
- [ ] In `tests/unit/test_pipeline_daemon.py`, add `test_shaders_stage_filter_applied`: mock `shader_inventory` returning rows with `stages="vs"`, `"ps"`, `"vs,ps"`; call handler with `params={"stage": "vs"}`; assert response `rows` contains only the `vs` and `vs,ps` entries
- [ ] Add `test_shaders_stage_filter_case_insensitive`: `params={"stage": "VS"}` matches `stages="vs"` rows
- [ ] Add `test_shaders_stage_filter_no_match`: `params={"stage": "cs"}` returns `{"rows": []}`, no error
- [ ] Add `test_shaders_no_stage_filter`: `params={}` returns all rows unmodified (regression guard)

### Fix 2: filter_by_pass EID-range
- [ ] In `tests/unit/test_query_service.py`, add `test_filter_by_pass_eid_range_semantic_name`: build a mock action tree with BeginPass at EID 3 (API name `"vkCmdBeginRenderPass(C=Load)"`), draws at EIDs 5, 7, 9, EndPass at EID 10; call `filter_by_pass(flat, "Colour Pass #1", actions=actions)`; assert all three draw FlatActions returned
- [ ] Add `test_filter_by_pass_eid_range_marker_name`: mock tree with marker group `"Opaque objects"` under a BeginPass; `filter_by_pass(flat, "Opaque objects", actions=actions)` returns only draws within that marker's EID range
- [ ] Add `test_filter_by_pass_name_not_found_fallback`: no matching pass in `_build_pass_list`; function falls back to `a.pass_name` string comparison; empty result when no action has matching `pass_name`
- [ ] Add `test_filter_by_pass_no_actions_legacy`: call without `actions` arg; uses original string match; asserts backward-compatible behavior
- [ ] In `tests/unit/test_draws_daemon.py`, add `test_draws_pass_filter_forwards_actions`: monkeypatch `filter_by_pass` in `daemon_server`; call `_handle_draws` with `params={"pass": "Opaque objects"}`; assert monkeypatched `filter_by_pass` was called with non-None `actions` and `sf`

### Fix 3: summary from filtered stats
- [ ] In `tests/unit/test_draws_daemon.py`, add `test_draws_summary_reflects_filtered_count`: mock 10 draws total, pass filter yields 3; assert `summary` starts with `"3 draw calls"`, not `"10"`
- [ ] Add `test_draws_summary_no_filter_equals_total`: no pass filter; summary count equals total draw count in `all_flat`
- [ ] Add `test_draws_summary_type_filter`: all_flat has mixed types; after `filter_by_type("draw")` yields 4 draws; summary starts with `"4 draw calls"`

### Fix 4: friendly pass names
- [ ] In `tests/unit/test_query_service.py`, add `test_friendly_pass_name_single_color`: `_friendly_pass_name("vkCmdBeginRenderPass(C=Load)", 0)` == `"Colour Pass #1 (1 Target)"`
- [ ] Add `test_friendly_pass_name_multi_color_with_depth`: `_friendly_pass_name("vkCmdBeginRenderPass(C=Load, C=Clear, D=Clear)", 2)` == `"Colour Pass #3 (2 Targets + Depth)"`
- [ ] Add `test_friendly_pass_name_depth_only`: `_friendly_pass_name("vkCmdBeginRenderPass(D=Clear)", 0)` == `"Colour Pass #1 (Depth)"`
- [ ] Add `test_friendly_pass_name_unknown_api`: `_friendly_pass_name("UnknownPassType()", 0)` == `"Colour Pass #1"` (no crash, no suffix)
- [ ] Add `test_build_pass_list_friendly_name_no_markers`: mock action tree with BeginPass named `"vkCmdBeginRenderPass(C=Load, D=Clear)"` and no marker children; `_build_pass_list` result has `name == "Colour Pass #1 (1 Target + Depth)"`
- [ ] Add `test_build_pass_list_preserves_marker_name`: marker group `"Opaque objects"` present; `_build_pass_list` result uses `"Opaque objects"`, not a friendly pass name

### Fix 5: topology enum name
- [ ] In `tests/unit/test_query_service.py`, add `test_pipeline_row_topology_enum_name`: mock `GetPrimitiveTopology()` returns object with `.name = "TriangleList"`; `pipeline_row` returns `{"topology": "TriangleList", ...}`
- [ ] Add `test_pipeline_row_topology_int_fallback`: mock returns plain `int` `3`; `pipeline_row` returns `{"topology": "3"}`, no exception
- [ ] Add `test_pipeline_row_topology_intenum`: mock returns `IntEnum` value `TriangleList=3`; `pipeline_row` returns `{"topology": "TriangleList"}`

## Phase B: Implementation

### Fix 1: daemon_server.py — shaders stage filter
- [ ] In `src/rdc/daemon_server.py`, after `rows = shader_inventory(pipe_states)` (line 365), add:
  ```python
  stage_filter = params.get("stage")
  if stage_filter:
      stage_filter = stage_filter.lower()
      rows = [r for r in rows if stage_filter in r["stages"].lower().split(",")]
  ```
- [ ] Verify `test_shaders_stage_filter_applied` and all Fix 1 tests pass: `pixi run test -k test_shaders`

### Fix 2a: query_service.py — extend filter_by_pass signature
- [ ] In `src/rdc/services/query_service.py`, update `filter_by_pass` (lines 142-145) to:
  ```python
  def filter_by_pass(
      flat: list[FlatAction],
      pass_name: str,
      actions: list[Any] | None = None,
      sf: Any = None,
  ) -> list[FlatAction]:
      if actions is not None:
          passes = _build_pass_list(actions, sf)
          target = next((p for p in passes if p["name"].lower() == pass_name.lower()), None)
          if target:
              return [a for a in flat if target["begin_eid"] <= a.eid <= target["end_eid"]]
      lower = pass_name.lower()
      return [a for a in flat if a.pass_name.lower() == lower]
  ```

### Fix 2b: daemon_server.py — pass actions+sf to filter_by_pass
- [ ] In `src/rdc/daemon_server.py`, replace lines 1858-1860:
  ```python
  if pass_name:
      flat = filter_by_pass(flat, pass_name)
  ```
  with:
  ```python
  if pass_name:
      _actions = state.adapter.get_root_actions()
      _sf = state.structured_file
      flat = filter_by_pass(flat, pass_name, actions=_actions, sf=_sf)
  ```
- [ ] Verify all Fix 2 tests pass: `pixi run test -k "filter_by_pass or test_draws_pass"`

### Fix 3: daemon_server.py — summary from filtered stats
- [ ] In `src/rdc/daemon_server.py`, restructure `_handle_draws` (lines 1855-1883):
  - Move pass filter BEFORE `filter_by_type("draw")`, apply to `all_flat`
  - Compute `stats = aggregate_stats(all_flat)` after pass filter but before type filter
  - Then `flat = filter_by_type(all_flat, "draw")` on the pass-filtered list
  - Summary uses `stats` (which includes dispatches/clears within the filtered pass)
  ```python
  all_flat = _get_flat_actions(state)
  pass_name = params.get("pass")
  if pass_name:
      actions = state.adapter.get_root_actions()
      sf = state.structured_file
      all_flat = filter_by_pass(all_flat, pass_name, actions=actions, sf=sf)
  stats = aggregate_stats(all_flat)
  flat = filter_by_type(all_flat, "draw")
  ```
- [ ] Verify all Fix 3 tests pass: `pixi run test -k test_draws_summary`

### Fix 4: query_service.py — friendly pass names
- [ ] In `src/rdc/services/query_service.py`, add `_friendly_pass_name(api_name: str, index: int) -> str` private function before `_build_pass_list_recursive`
- [ ] In `_build_pass_list_recursive` (line 533), introduce a local `_pass_index` counter scoped to the current level (start at 0, increment each time a pass entry is appended)
- [ ] In the children-of-BeginPass branch (line 558): when `not marker_groups` and has draws, use `_subtree_stats(a, sf)` but override `"name"` key with `_friendly_pass_name(name, _pass_index)` before appending
- [ ] In the flat-sibling branch (line 576): `_window_stats(a, window, sf)` result — override `"name"` with `_friendly_pass_name(name, _pass_index)` before appending
- [ ] When marker groups ARE present, do not apply `_friendly_pass_name` (preserve marker group name)
- [ ] Verify all Fix 4 tests pass: `pixi run test -k "friendly_pass or build_pass_list"`

### Fix 5: query_service.py — topology enum name
- [ ] In `src/rdc/services/query_service.py`, line 326, replace:
  ```python
  "topology": str(pipe_state.GetPrimitiveTopology()),
  ```
  with:
  ```python
  "topology": getattr(pipe_state.GetPrimitiveTopology(), "name", str(pipe_state.GetPrimitiveTopology())),
  ```
- [ ] Verify all Fix 5 tests pass: `pixi run test -k test_pipeline_row_topology`

## Phase C: Integration

- [ ] Run full unit test suite: `pixi run test` — all tests green, coverage ≥ 80%
- [ ] Run lint and type check: `pixi run lint` — zero ruff errors, zero mypy strict errors
- [ ] GPU test Fix 1: call `shaders` handler with `params={"stage": "vs"}` on `hello_triangle.rdc`; assert all returned rows have `"vs"` in their `stages` field; assert result is non-empty
- [ ] GPU test Fix 2: call `passes` on `hello_triangle.rdc` to get actual pass names; call `draws` with `params={"pass": <first_pass_name>}`; assert returned draws list is non-empty and all draws have EIDs within the pass range
- [ ] GPU test Fix 3: call `draws` with a pass filter on `hello_triangle.rdc`; assert `summary` count matches `len(draws)` in response
- [ ] GPU test Fix 4: call `passes` on a markerless capture (`hello_triangle.rdc`); assert no pass name matches `"vkCmd"` prefix pattern; assert all names match `"Colour Pass #\d+"` pattern
- [ ] GPU test Fix 5: call `pipeline` on any draw EID in `hello_triangle.rdc`; assert `topology` field is not purely numeric (i.e. `not response["topology"].isdigit()`)
- [ ] Run GPU tests: `RENDERDOC_PYTHON_PATH=/path/to/renderdoc/build/lib pixi run test-gpu -k bug_filters`

## Phase D: Verify

- [ ] `pixi run check` passes (= lint + typecheck + test, all green)
- [ ] Manual: `rdc shaders --stage vs` on a real capture returns only vertex shader rows
- [ ] Manual: `rdc draws --pass "<name from rdc passes>"` returns non-empty draw list
- [ ] Manual: `rdc draws --pass "<name>"` summary count matches number of rows printed
- [ ] Manual: `rdc passes` on `hello_triangle.rdc` shows `"Colour Pass #1"` style names
- [ ] Manual: `rdc pipeline <eid>` shows `TOPOLOGY: TriangleList`, not `TOPOLOGY: 3`
- [ ] Archive: move `openspec/changes/2026-02-21-phase2.7-bug-filters/` → `openspec/changes/archive/`
- [ ] Update `进度跟踪.md` in Obsidian vault
