# Tasks: phase2.6-output-quality

## Implementation

- [x] Add `_UINT_MAX_SENTINEL`, `_enum_name`, `_sanitize_size` to `daemon_server.py`
- [x] `pipe_topology`: wrap topology with `_enum_name`
- [x] `pipe_blend`: wrap all blend factor/op fields with `_enum_name`
- [x] `pipe_stencil`: wrap all stencil op/function fields with `_enum_name`
- [x] `pipe_samplers`: wrap address mode and filter fields with `_enum_name`
- [x] `postvs`: wrap topology with `_enum_name`
- [x] `pipe_vbuffers`: wrap `byteSize` with `_sanitize_size`
- [x] `pipe_ibuffer`: wrap `byteSize` with `_sanitize_size`
- [x] `daemon_client.py`: raise default `timeout` from `2.0` to `30.0`

## Tests

- [x] Write `tests/unit/test_daemon_output_quality.py`
  - [x] `TestEnumName` — 5 cases
  - [x] `TestSanitizeSize` — 4 cases
  - [x] `TestClientTimeout` — 1 case
  - [x] `TestPipeTopologyEnumName` — 1 case
  - [x] `TestPipeBlendEnumNames` — 1 case
  - [x] `TestPipeStencilEnumNames` — 1 case
  - [x] `TestPipeSamplersEnumNames` — 1 case
  - [x] `TestPipeVbuffersUintMax` — 2 cases
  - [x] `TestPipeIbufferUintMax` — 2 cases

## CI

- [x] `pixi run check` passes (lint + typecheck + test)
