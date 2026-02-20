# Tasks: phase2-counters

## Phase A — Mock infrastructure

- [ ] Add `GPUCounter` `IntEnum` to `mock_renderdoc.py` (EventGPUDuration=1 through CSInvocations=13, Count=16)
- [ ] Add `CounterUnit` `IntEnum` to `mock_renderdoc.py` (Absolute=0, Seconds=1, Hertz=2, Cycles=3, Percentage=4, Ratio=5, Bytes=6, Pixels=7, Celsius=8)
- [ ] Add `CompType` members if not already present (Float=1, UInt=4 needed)
- [ ] Add `CounterDescription` dataclass to `mock_renderdoc.py`: `name: str`, `category: str`, `description: str`, `counter: GPUCounter`, `resultByteWidth: int`, `resultType: CompType`, `unit: CounterUnit`, `uuid: str`
- [ ] Add `CounterValue` dataclass to `mock_renderdoc.py`: `.d: float`, `.u64: int`, `.u32: int`, `.f: float`
- [ ] Add `CounterResult` dataclass to `mock_renderdoc.py`: `eventId: int`, `counter: GPUCounter`, `value: CounterValue`
- [ ] Add `_counter_descs: dict[GPUCounter, CounterDescription]` field to `MockReplayController.__init__`
- [ ] Add `_counter_results: dict[GPUCounter, list[CounterResult]]` field to `MockReplayController.__init__`
- [ ] Add `EnumerateCounters() -> list[GPUCounter]` method to `MockReplayController`
- [ ] Add `DescribeCounter(counterId: GPUCounter) -> CounterDescription` method to `MockReplayController`
- [ ] Add `FetchCounters(counterIds: list[GPUCounter]) -> list[CounterResult]` method to `MockReplayController`

## Phase B — Tests: daemon handlers

- [ ] Create `tests/unit/test_counters_daemon.py`
- [ ] Test `counter_list` handler: happy path — returns `{counters: [{id, name, category, unit}]}`
- [ ] Test `counter_list` handler: empty counter list — returns `{counters: []}`
- [ ] Test `counter_list` handler: no replay loaded (`adapter=None`) — returns error code `-32002`
- [ ] Test `counter_fetch` handler: happy path — returns `{results: [{eid, counter_id, value}]}`
- [ ] Test `counter_fetch` handler: specific `counter_ids` filter — only requested counters returned
- [ ] Test `counter_fetch` handler: `eid` filter — only results for that event returned
- [ ] Test `counter_fetch` handler: unknown counter ID — returns error code `-32001`
- [ ] Test `counter_fetch` handler: no replay loaded (`adapter=None`) — returns error code `-32002`

## Phase C — Daemon handler implementation

- [ ] Add `counter_list` branch to `_handle_request` in `daemon_server.py`: call `EnumerateCounters()`, call `DescribeCounter` for each, return `{counters: [{id, name, category, unit}]}`
- [ ] Add `counter_fetch` branch: accept optional `counter_ids` and `eid` params, call `FetchCounters(counter_ids)`, filter by `eid` if provided, return `{results: [{eid, counter_id, value}]}`
- [ ] Return `-32001` when a requested counter ID is not found
- [ ] Return `-32002` when `state.adapter is None`
- [ ] Verify Phase B tests pass: `pixi run test -k test_counters_daemon`

## Phase D — Tests: VFS route + tree cache

- [ ] Add route test to `tests/unit/test_vfs_router.py`: `/counters/list` → `PathMatch(kind="leaf", handler="counter_list", args={})`
- [ ] Add route test: `/counters/` → `PathMatch(kind="dir", handler="counters_dir", args={})`
- [ ] Add tree cache test to `tests/unit/test_vfs_tree_cache.py`: `build_vfs_skeleton` produces `"counters"` top-level dir with `"list"` child

## Phase E — VFS route + tree cache implementation

- [ ] Add route entry to `router.py`: `/counters/` dir node
- [ ] Add route entry to `router.py`: `/counters/list` leaf → `counter_list` handler
- [ ] Add `"counters"` top-level dir with `"list"` leaf to `tree_cache.py`
- [ ] Verify Phase D tests pass: `pixi run test -k "test_vfs_router or test_vfs_tree_cache"`

## Phase F — Tests: CLI command

- [ ] Create `tests/unit/test_counters_commands.py`
- [ ] Test `rdc counters list` TSV: header `ID\tNAME\tCATEGORY\tUNIT`, one row per counter
- [ ] Test `rdc counters list --json`: output is valid JSON with `counters` array
- [ ] Test `rdc counters fetch` TSV: header `EID\tCOUNTER_ID\tVALUE`, one row per result
- [ ] Test `rdc counters fetch --counter-ids <id>`: passes `counter_ids` param to daemon
- [ ] Test `rdc counters fetch --eid <eid>`: passes `eid` filter to daemon
- [ ] Test `rdc counters fetch --json`: output is valid JSON with `results` array
- [ ] Test `rdc counters fetch` error: daemon returns `-32001` → exit code 1, message to stderr
- [ ] Test `rdc counters list` error: daemon returns `-32002` → exit code 1, message to stderr

## Phase G — CLI command implementation + VFS extractor

- [ ] Create `src/rdc/commands/counters.py` with `counters` Click group
- [ ] Add `list` subcommand: call daemon `counter_list`, print TSV `ID\tNAME\tCATEGORY\tUNIT` or `--json`
- [ ] Add `fetch` subcommand: accept `--counter-ids` (multiple) and `--eid` options, call daemon `counter_fetch`, print TSV `EID\tCOUNTER_ID\tVALUE` or `--json`
- [ ] Register `counters` group in `src/rdc/cli.py`
- [ ] Add `"counter_list"` extractor to `_EXTRACTORS` in `commands/vfs.py`: format as TSV `ID\tNAME\tCATEGORY\tUNIT`
- [ ] Verify Phase F tests pass: `pixi run test -k test_counters_commands`

## Phase H — Mock API sync

- [ ] Add `GPUCounter` and `CounterUnit` to `ENUM_PAIRS` in `test_mock_api_sync.py`
- [ ] Add `CounterDescription` and `CounterResult` to `STRUCT_PAIRS` in `test_mock_api_sync.py`
- [ ] Verify sync tests pass: `pixi run test -k test_mock_api_sync`

## Phase I — GPU integration tests

- [ ] Add `test_counter_list` to `tests/integration/test_daemon_handlers_real.py`: call `counter_list`, assert `counters` is a list and each entry has `id`, `name`, `category`, `unit`
- [ ] Add `test_counter_fetch`: call `counter_fetch` with IDs from `counter_list`, assert `results` is a list and each entry has `eid` (int), `counter_id` (int), `value` (number)
- [ ] Add `test_counter_fetch_eid_filter`: call `counter_fetch` with `eid` filter, assert all returned results have matching `eid`
- [ ] Add `test_vfs_counters_list`: fetch `/counters/list` via VFS cat, assert TSV header and at least one row
- [ ] Run GPU tests: `RENDERDOC_PYTHON_PATH=... pixi run test-gpu -k test_counter`

## Phase J — Final verification

- [ ] `pixi run check` passes (lint + typecheck + test, ≥80% coverage)
- [ ] GPU tests pass on `hello_triangle.rdc`
- [ ] All task checkboxes checked
- [ ] Archive: move `openspec/changes/2026-02-20-phase2-counters/` → `openspec/changes/archive/`
- [ ] Merge delta into `openspec/specs/`
- [ ] Update `进度跟踪.md` in Obsidian vault
