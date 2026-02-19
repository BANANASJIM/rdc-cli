# Tasks: phase1-draws-events

## Test-first tasks
- [ ] Extend mock renderdoc module with realistic action tree (nested markers,
      multiple passes, draw/dispatch/clear/copy actions, structured data chunks).
- [ ] Add unit tests for action tree traversal (walk, flatten, filter by type,
      filter by pass, filter by name pattern, count by category).
- [ ] Add unit tests for stats aggregation (per-pass breakdown, top draws,
      largest resources).
- [ ] Add unit tests for TSV output of `events` (columns, filter, range, limit).
- [ ] Add unit tests for TSV output of `draws` (columns, pass filter, sort,
      limit, quiet mode, footer to stderr).
- [ ] Add unit tests for `info` key:value output format.
- [ ] Add unit tests for `event <eid>` detail output (structured data lookup).
- [ ] Add unit tests for `draw [eid]` detail output (pipeline state, bindings,
      render targets, shaders).
- [ ] Add mock daemon tests for each new JSON-RPC method (info, stats, events,
      draws, event, draw).
- [ ] Add error path tests (no session, invalid eid, empty capture).

## Implementation tasks
- [ ] Create `src/rdc/services/query_service.py` with action tree helpers:
      walk_actions, flatten_actions, filter_by_type, filter_by_pass,
      aggregate_stats, find_action_by_eid.
- [ ] Create `src/rdc/commands/info.py` with `rdc info` and `rdc stats` commands.
- [ ] Create `src/rdc/commands/events.py` with `rdc events`, `rdc draws`,
      `rdc event <eid>`, `rdc draw [eid]` commands.
- [ ] Add daemon JSON-RPC method handlers: info, stats, events, draws, event,
      draw.
- [ ] Wire new commands into `cli.py`.
- [ ] Update README with new command examples.
- [ ] Ensure `make check` passes (ruff + mypy strict + pytest ≥ 80%).
