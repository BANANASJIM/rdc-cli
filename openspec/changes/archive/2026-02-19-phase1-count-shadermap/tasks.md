# Tasks: phase1-count-shadermap

## Test-first tasks
- [x] Add unit tests for count logic (each target type, with and without
      pass filter).
- [x] Add unit tests for shader-map collection (multiple draws, mixed stages,
      compute-only dispatch).
- [x] Add unit tests for `rdc count` CLI output format (single integer,
      no trailing whitespace).
- [x] Add unit tests for `rdc shader-map` TSV output (header, no-header,
      `-` for unbound stages).
- [x] Add mock daemon tests for `count` and `shader_map` JSON-RPC methods.
- [x] Add error path tests (no session, invalid count target).

## Implementation tasks
- [x] Create `src/rdc/commands/unix_helpers.py` with `count` and `shader-map`
      commands.
- [x] Add count logic to `src/rdc/services/query_service.py` (or reuse
      existing aggregation from draws-events).
- [x] Add shader_map collection to query_service (iterate draws, collect
      shader IDs per stage via GetShader).
- [x] Add daemon JSON-RPC method handlers: count, shader_map.
- [x] Wire new commands into `cli.py`.
- [x] Ensure `make check` passes (ruff + mypy strict + pytest ≥ 80%).
