# Tasks: GPU Test Coverage Expansion (Track B)

## Branch
`test/gpu-coverage-expansion`

## Task List

- [ ] Read `tests/integration/test_daemon_handlers_real.py` header to understand `_call` helper and fixture patterns

- [ ] Add `TestBufferDecodeReal` class with `_setup` autouse fixture + 2 tests:
  - `test_cbuffer_decode_returns_data` — `_call(self.state, "cbuffer_decode", {"eid": eid, "stage": "vs", "set": 0, "binding": 0})`; assert `"variables" in result or "set" in result`
  - `test_vbuffer_decode_returns_vertex_data` — `_call(self.state, "vbuffer_decode", {"eid": eid})`; assert `"columns" in result and "vertices" in result`

- [ ] Add `TestShaderMapAndAllReal` class with `_setup` autouse fixture + 2 tests:
  - `test_shader_map_returns_rows` — `_call(self.state, "shader_map")`; assert `"rows" in result and len(result["rows"]) >= 2`
  - `test_shader_all_returns_stages` — `_call(self.state, "shader_all")`; assert `"stages" in result and len(result["stages"]) >= 2`

- [ ] Run `pixi run test-gpu -k "TestBufferDecodeReal or TestShaderMapAndAllReal"` to verify new tests
  - If a test reveals unexpected API shape, update assertions to match real behavior
  - Do NOT adjust assertions to hide real failures — report them instead

- [ ] Run full `pixi run test-gpu` — zero new failures

## Definition of Done
- 2 new GPU test classes (4 total new test methods)
- `pixi run test-gpu` green with no regressions
- No changes to handler code (test-only)

## Notes
- If `cbuffer_decode` or `vbuffer_decode` returns an error dict for vkcube
  (e.g., "no cbuffer at slot 0"), that is also a valid result — assert it's a well-formed dict
- `debug_thread` is deferred to a future phase (requires compute shader capture)
