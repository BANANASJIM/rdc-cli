# Tasks: phase2-usage

## Phase A — Mock infrastructure

- [ ] Add `ResourceUsage` `IntEnum` to `mock_renderdoc.py` (46 values: `VertexBuffer`, `IndexBuffer`, `VS_Constants`, `PS_Constants`, `ColorTarget`, `DepthStencilTarget`, `CopySrc`, `CopyDst`, `Clear`, etc.)
- [ ] Add `EventUsage` dataclass to `mock_renderdoc.py`: `eventId: int`, `usage: ResourceUsage`
- [ ] Add `_usage_map: dict[int, list[EventUsage]]` field to `MockReplayController.__init__`
- [ ] Add `GetUsage(resource_id: Any) -> list[EventUsage]` method to `MockReplayController`

## Phase B — Tests: daemon handlers

- [ ] Create `tests/unit/test_usage_daemon.py`
- [ ] Test `usage` handler: happy path — returns `{id, name, entries: [{eid, usage}]}`
- [ ] Test `usage` handler: empty entries — returns header only, no error
- [ ] Test `usage` handler: unknown resource ID — returns error code `-32001`
- [ ] Test `usage` handler: no replay loaded (`adapter=None`) — returns error code `-32002`
- [ ] Test `usage_all` handler: no filters — returns all resource×event rows with `total`
- [ ] Test `usage_all` handler: `type` filter — rows match resource type only
- [ ] Test `usage_all` handler: `usage` filter — rows match usage type string only
- [ ] Test `usage_all` handler: both filters combined — intersection

## Phase C — Daemon handler implementation

- [ ] Add `usage` branch to `_handle_request` in `daemon_server.py`: call `GetUsage(ResourceId(id))`, resolve name from `state.res_names`, return `{id, name, entries}`
- [ ] Add `usage_all` branch: iterate all resources, call `GetUsage` for each, flatten to rows, apply `type`/`usage` filters, return `{rows, total}`
- [ ] Return `-32001` when resource ID not in `state.res_names`
- [ ] Return `-32002` when `state.adapter is None`
- [ ] Verify Phase B tests pass: `pixi run test -k test_usage_daemon`

## Phase D — Tests: VFS route + tree cache

- [ ] Add route test to `tests/unit/test_vfs_router.py`: `/resources/97/usage` → `PathMatch(kind="leaf", handler="usage", args={"id": 97})`
- [ ] Add tree cache test to `tests/unit/test_vfs_tree_cache.py`: `build_vfs_skeleton` produces `"usage"` child under each `/resources/<id>/` node

## Phase E — VFS route + tree cache implementation

- [ ] Add route entry to `router.py`: `_r(r"/resources/(?P<id>\d+)/usage", "leaf", "usage", [("id", int)])`
- [ ] Add `"usage"` to resource children list in `tree_cache.py` (alongside existing `"info"`)
- [ ] Verify Phase D tests pass: `pixi run test -k "test_vfs_router or test_vfs_tree_cache"`

## Phase F — Tests: CLI command

- [ ] Create `tests/unit/test_usage_commands.py`
- [ ] Test `rdc usage <id>` TSV: header `EID\tUSAGE`, one row per entry
- [ ] Test `rdc usage <id> --json`: output is valid JSON with `id`, `name`, `entries`
- [ ] Test `rdc usage --all` TSV: header `ID\tNAME\tEID\tUSAGE`, rows from `usage_all`
- [ ] Test `rdc usage --all --type Texture`: passes `type` param to daemon
- [ ] Test `rdc usage --all --usage ColorTarget`: passes `usage` param to daemon
- [ ] Test `rdc usage <id>` error: daemon returns `-32001` → exit code 1, message to stderr
- [ ] Test `rdc usage` (no args, no `--all`): exits with usage error / non-zero

## Phase G — CLI command implementation + VFS extractor

- [ ] Create `src/rdc/commands/usage.py` with `usage_cmd` Click command
- [ ] `usage_cmd`: `@click.argument("resource_id", required=False, type=int)` + `--all` flag + `--type` + `--usage` + `--json`
- [ ] Single-resource path: call daemon `usage`, print TSV `EID\tUSAGE` or JSON
- [ ] `--all` path: call daemon `usage_all` with optional filters, print TSV `ID\tNAME\tEID\tUSAGE` or JSON
- [ ] Error when neither `resource_id` nor `--all` is provided
- [ ] Register `usage_cmd` in `src/rdc/cli.py`
- [ ] Add `"usage"` extractor to `_EXTRACTORS` in `commands/vfs.py`: format as TSV `EID\tUSAGE`
- [ ] Verify Phase F tests pass: `pixi run test -k test_usage_commands`

## Phase H — GPU integration tests

- [ ] Add `test_usage_single_real` to `tests/integration/test_daemon_handlers_real.py`: call `usage` with a known resource ID from `hello_triangle.rdc`, assert `entries` is a list and each entry has `eid` (int) and `usage` (str)
- [ ] Add `test_usage_all_real`: call `usage_all`, assert `total > 0` and row schema matches
- [ ] Add `test_usage_all_filter_real`: call `usage_all` with `usage="ColorTarget"`, assert all returned rows have `usage == "ColorTarget"`
- [ ] Run GPU tests: `RENDERDOC_PYTHON_PATH=... pixi run test-gpu -k test_usage`

## Phase I — Final verification

- [ ] `pixi run lint` passes (zero ruff errors)
- [ ] `pixi run test` passes (≥80% coverage, all unit tests green)
- [ ] GPU tests pass on `hello_triangle.rdc`
- [ ] Archive: move `openspec/changes/2026-02-20-phase2-usage/` → `openspec/changes/archive/`
- [ ] Merge delta into `openspec/specs/`
- [ ] Update `进度跟踪.md` in Obsidian vault
