# Proposal: GPU Test Coverage Expansion (Track B)

## Problem

16 handler methods have no GPU integration test coverage. Unit tests pass against mocks, but
real hardware behavior is not validated. The blackbox testing session (PR #77) found bugs that
unit tests missed precisely because GPU behavior wasn't exercised.

## Handlers Without GPU Coverage

| Method | Module | Risk | Deferral |
|--------|--------|------|---------|
| `cbuffer_decode` | buffer.py | High | No |
| `vbuffer_decode` | buffer.py | High | No |
| `shader_all` | shader.py | Medium | No |
| `shader_map` | query.py | Medium | No |
| `ping` | core.py | Low | Defer — trivial no-op |
| `goto` | core.py | Low | Defer — covered implicitly |
| `shader` | query.py | Low | Defer — similar to `shaders` |
| `resource` | query.py | Low | Defer — similar to `resources` |
| `event` | query.py | Low | Defer — similar to `events` |
| `draw` | query.py | Low | Defer — similar to `draws` |
| `shader_reflect` | shader.py | Low | Defer — covered by shader_list_info |
| `shader_disasm` | shader.py | Low | Defer — covered by shader_list_disasm |
| `postvs` | buffer.py | Medium | Defer — requires draw setup |
| `ibuffer_decode` | buffer.py | Medium | Defer — requires IBO validation |
| `debug_thread` | debug.py | High | Defer — requires compute shader capture |
| `shader_replace` | shader_edit.py | High | Defer — edit flow tested in TestShaderEditReal |

## Scope for This PR (non-deferred)

Two new GPU test classes targeting the 4 highest-risk non-deferred methods.

### TestBufferDecodeReal — `cbuffer_decode`, `vbuffer_decode`

Test that buffer decode handlers return structured data with expected fields.
- `cbuffer_decode` params: `{"eid": eid, "stage": "vs", "set": 0, "binding": 0}` — stage is a string name, binding (not slot) is the param key
- `cbuffer_decode` response: `{"eid": eid, "set": int, "binding": int, "variables": [...]}`
- `vbuffer_decode` params: `{"eid": eid}` — count/stream/offset are optional/internal
- `vbuffer_decode` response: `{"eid": eid, "columns": [...], "vertices": [...]}`
- Fixture: `vkcube_replay` + `rd_module` (both required for `_make_state`)

### TestShaderMapAndAllReal — `shader_all`, `shader_map`

Test that shader enumeration handlers return valid results.
- `shader_map` response: `{"rows": [...]}` — NOT a flat dict
- `shader_all` response: `{"eid": eid, "stages": [...]}` — NOT a bare list
- Fixture: `vkcube_replay` + `rd_module`

## Implementation Notes
- All test classes MUST follow the `_setup` autouse fixture pattern (creates `self.state` via `_make_state`)
- Use `_call(self.state, method, params)` — state is the FIRST argument
- Use `_call(self.state, "events")["events"][0]["eid"]` to find a real draw EID (existing pattern)

## Acceptance Criteria
- 2 new GPU test classes in `tests/integration/test_daemon_handlers_real.py`
- Each class: minimum 2 test methods
- `pixi run test-gpu` passes (with RENDERDOC_PYTHON_PATH set)
- No regressions in existing GPU tests
