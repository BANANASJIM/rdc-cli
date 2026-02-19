# Tasks: phase1-count-shadermap

## Test-first tasks
- [ ] Add unit tests for count logic (each target type, with and without
      pass filter).
- [ ] Add unit tests for shader-map collection (multiple draws, mixed stages,
      compute-only dispatch).
- [ ] Add unit tests for `rdc count` CLI output format (single integer,
      no trailing whitespace).
- [ ] Add unit tests for `rdc shader-map` TSV output (header, no-header,
      `-` for unbound stages).
- [ ] Add mock daemon tests for `count` and `shader_map` JSON-RPC methods.
- [ ] Add error path tests (no session, invalid count target).

## Implementation tasks
- [ ] Create `src/rdc/commands/unix_helpers.py` with `count` and `shader-map`
      commands.
- [ ] Add count logic to `src/rdc/services/query_service.py` (or reuse
      existing aggregation from draws-events).
- [ ] Add shader_map collection to query_service (iterate draws, collect
      shader IDs per stage via GetShader).
- [ ] Add daemon JSON-RPC method handlers: count, shader_map.
- [ ] Wire new commands into `cli.py`.
- [ ] Ensure `make check` passes (ruff + mypy strict + pytest ≥ 80%).
