# Test Plan: phase2.7-bug-filters

## Scope

### In scope
- Fix 1: `shaders` daemon handler applies `stage` filter post-`shader_inventory`
- Fix 2: `filter_by_pass` EID-range path when `actions` arg is provided; daemon call-site passes `actions` + `sf`
- Fix 3: `draws` daemon handler summary computed from post-filter `flat` list
- Fix 4: `_friendly_pass_name` helper produces readable names; applied in `_build_pass_list_recursive` for marker-free passes
- Fix 5: `pipeline_row` topology field serializes SWIG enum name via `getattr(..., "name", str(...))`
- Mock coverage for all 5 fixes (no GPU required for unit tests)
- GPU regression on `hello_triangle.rdc` for all 5 fixes

### Out of scope
- New CLI options, commands, or JSON-RPC methods
- VFS router or tree cache changes
- Performance benchmarking of `filter_by_pass` on large captures

## Test Matrix

| Layer | Scope | File |
|-------|-------|------|
| Unit | Fix 1: shaders stage filter in daemon handler | `tests/unit/test_pipeline_daemon.py` |
| Unit | Fix 2: `filter_by_pass` with `actions` arg (EID-range path) | `tests/unit/test_query_service.py` |
| Unit | Fix 2: daemon `_handle_draws` passes `actions`+`sf` to `filter_by_pass` | `tests/unit/test_draws_daemon.py` |
| Unit | Fix 3: summary reflects filtered `flat`, not `all_flat` | `tests/unit/test_draws_daemon.py` |
| Unit | Fix 4: `_friendly_pass_name` output for various API name patterns | `tests/unit/test_query_service.py` |
| Unit | Fix 4: `_build_pass_list` uses friendly names when no marker groups | `tests/unit/test_query_service.py` |
| Unit | Fix 5: `pipeline_row` topology is enum name string, not integer | `tests/unit/test_query_service.py` |
| GPU | Fix 1: `shaders --stage vs` returns only VS rows on real capture | `tests/integration/test_daemon_handlers_real.py` |
| GPU | Fix 2: `draws --pass <name>` matches semantic name from `rdc passes` | `tests/integration/test_daemon_handlers_real.py` |
| GPU | Fix 3: filtered summary count matches `len(draws)` in response | `tests/integration/test_daemon_handlers_real.py` |
| GPU | Fix 4: `passes` list on markerless capture has readable names | `tests/integration/test_daemon_handlers_real.py` |
| GPU | Fix 5: topology field is non-numeric string on real pipeline state | `tests/integration/test_daemon_handlers_real.py` |

## Cases

### Fix 1: shaders stage filter

1. **Happy path — stage filter applied**: call `shaders` handler with `params={"stage": "vs"}`;
   mock `shader_inventory` returns rows with `stages` values of `"vs"`, `"ps"`, and `"vs,ps"`;
   assert response `rows` contains only the `"vs"` and `"vs,ps"` entries.
2. **Stage filter case-insensitive**: `params={"stage": "VS"}` matches rows with `stages="vs"`.
3. **Stage filter with no matches**: `params={"stage": "cs"}` against a graphics-only capture;
   response `rows` is empty list, not an error.
4. **No stage filter**: `params={}` returns all rows unfiltered (existing behavior preserved).
5. **Invalid stage value**: `params={"stage": "zz"}` yields empty `rows` (post-filter, no match),
   not a daemon error.

### Fix 2: `filter_by_pass` EID-range path

6. **EID-range match via semantic name**: pass a mock action tree with a BeginPass node named
   `"vkCmdBeginRenderPass(C=Load)"` containing draws at EIDs 5, 7, 9; call
   `filter_by_pass(flat, "Colour Pass #1", actions=actions, sf=None)`;
   assert all three FlatActions are returned.
7. **Semantic marker name match**: mock tree has a marker group named `"Opaque objects"` under
   a BeginPass; `filter_by_pass(flat, "Opaque objects", actions=actions)` returns only draws
   within that marker's EID range.
8. **Name not found in pass list — fallback**: no pass in `_build_pass_list` matches the given
   name; function falls back to `a.pass_name` string comparison; returns matching items if any,
   empty list if none.
9. **`actions=None` — legacy path**: `filter_by_pass(flat, "vkCmdBeginRenderPass(C=Load)")` with
   no `actions` arg uses original string match; behavior unchanged from pre-fix.
10. **Daemon call-site forwards `actions`+`sf`**: monkeypatch `filter_by_pass` to assert it
    receives non-None `actions` and `sf` when `pass_name` param is set in `_handle_draws`.

### Fix 3: Summary from filtered stats

11. **Pass filter reduces summary count**: mock `all_flat` has 10 draws total; after
    `filter_by_pass` yields 3 draws; summary string starts with `"3 draw calls"`, not `"10"`.
12. **Type filter reduces summary count**: `filter_by_type(all_flat, "draw")` yields 4 draws
    from 10 mixed events; summary starts with `"4 draw calls"`.
13. **No filter — summary equals total**: no `pass` or `type` params; summary count equals
    `len(all_flat)` draw actions.
14. **Combined filter**: `--pass` + `--sort` applied; summary reflects the post-pass-filter
    list (sort does not change count).

### Fix 4: `_friendly_pass_name` helper

15. **Single color target, no depth**: `_friendly_pass_name("vkCmdBeginRenderPass(C=Load)", 0)`
    → `"Colour Pass #1 (1 Target)"`.
16. **Multiple color targets with depth**: `_friendly_pass_name("vkCmdBeginRenderPass(C=Load, C=Clear, D=Clear)", 2)`
    → `"Colour Pass #3 (2 Targets + Depth)"`.
17. **Depth only, no color**: `_friendly_pass_name("vkCmdBeginRenderPass(D=Clear)", 0)`
    → `"Colour Pass #1 (Depth)"`.
18. **Unrecognized API name**: `_friendly_pass_name("UnknownPassType()", 0)` → `"Colour Pass #1"`
    (no suffix, no crash).
19. **`_build_pass_list` uses friendly name for markerless pass**: mock action tree with BeginPass
    API name `"vkCmdBeginRenderPass(C=Load, D=Clear)"` and no marker children; result from
    `_build_pass_list` has `name == "Colour Pass #1 (1 Target + Depth)"`, not the raw API string.
20. **`_build_pass_list` preserves marker group names**: when marker groups are present, the
    marker group's own name is used, not the friendly pass name.

### Fix 5: Topology enum name

21. **SWIG enum with `.name`**: mock `GetPrimitiveTopology()` returns an object with
    `.name = "TriangleList"`; `pipeline_row` `"topology"` field is `"TriangleList"`.
22. **Fallback for plain int**: mock returns `3` (no `.name` attribute); `pipeline_row`
    `"topology"` field is `"3"` (not crash).
23. **Mock enum via IntEnum**: `MockPrimitiveTopology(IntEnum)` with `TriangleList = 3`;
    `getattr(v, "name", str(v))` → `"TriangleList"`.
24. **GPU real API**: `pipeline_row` on a real Vulkan capture returns `"TriangleList"` string,
    not `"3"` or `"Topology.TriangleList"`.

### Regression

25. **`shaders` without `--stage` returns same result as before**: existing test assertions
    for unfiltered shaders list remain green.
26. **`draws` without `--pass` returns same result as before**: existing draws tests pass.
27. **`filter_by_pass` with no `actions` arg is backward-compatible**: all existing call sites
    that do not pass `actions` continue to work identically.

## Assertions

### Exit codes
- 0: success for all filtered queries, including zero-result cases
- 1: runtime error (no session, no adapter loaded)
- 2: CLI argument error (invalid stage name rejected by Click choices, if applicable)

### `shaders` response contract
- `rows` is always a list (may be empty)
- When `stage` filter is active, every row's `"stages"` field contains the requested stage
  as a comma-separated element (case-insensitive)
- No error is returned for a valid filter that matches zero rows

### `draws` response contract
- `draws` list length and `summary` count are consistent: summary must reflect
  `len(draws)` draw-type actions (not the unfiltered frame total)
- `summary` format: `"<N> draw calls (<I> indexed, <D> dispatches, <C> clears)"`

### `filter_by_pass` contract
- With `actions` provided: match is EID-range based, case-insensitive on name
- Without `actions`: match is exact `a.pass_name` string comparison (unchanged)
- Return type is always `list[FlatAction]`

### `_friendly_pass_name` contract
- Return value is always a non-empty string
- Format: `"Colour Pass #<N>"` with optional ` (<attachments>)` suffix
- `N` is 1-based (`index + 1`)
- Color count is the number of `"C="` occurrences in the API name
- Depth is present if `"D="` appears in the API name
- No exception for any string input

### `pipeline_row` topology contract
- `"topology"` field is always a non-empty string
- Must not be a plain decimal integer string for any SWIG-wrapped enum value
- Must match the enum's `.name` attribute when available

### Error response (JSON-RPC)
- `-32002` when `state.adapter is None` for any handler
- `"message"` field is non-empty string
- Error output on stderr, nothing on stdout

## Risks & Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| `stages` field format changes in `shader_inventory` output | Fix 1 filter breaks silently | Assert field format in unit test; use `in row["stages"].lower().split(",")` not substring match |
| `state.structured_file` is None for mock-only states | Fix 2 `_build_pass_list` receives `sf=None` | `_build_pass_list` already handles `sf=None`; `GetName(None)` falls back to `_name` attr in mocks |
| `_build_pass_list` returns empty for a capture style not yet tested | Fix 2 fallback never triggers | Unit test the fallback path explicitly; GPU test on markerless capture (hello_triangle) |
| `_friendly_pass_name` index counter diverges from actual pass list index | Pass #N label is wrong | Maintain explicit counter in `_build_pass_list_recursive`; unit-test multi-pass sequences |
| `getattr(v, "name", str(v))` called twice (once for check, once for value) | Minor performance | Use a single `v = pipe_state.GetPrimitiveTopology(); getattr(v, "name", str(v))` |
| Rollback | — | Revert branch; no master changes until PR squash-merge |
