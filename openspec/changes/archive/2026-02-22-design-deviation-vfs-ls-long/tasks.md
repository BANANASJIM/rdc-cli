# Tasks: VFS ls Long Format (-l flag)

## Agent Assignment

Single worktree. All files are in one logical change with no conflicting parallel paths.

| Commit | Files | Notes |
|--------|-------|-------|
| 1 — feat(vfs): extend vfs_ls RPC with long mode | `handlers/vfs.py`, `handlers/_helpers.py` | Daemon-only change |
| 2 — feat(vfs): add -l flag to rdc ls and render_ls_long formatter | `commands/vfs.py`, `vfs/formatter.py` | CLI + formatter |
| 3 — test: cover vfs_ls long mode (unit + integration) | test files | Tests only |

---

## Commit 1: `feat(vfs): extend vfs_ls RPC with long mode`

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/handlers/vfs.py` | Read `long = bool(params.get("long", False))` in `_handle_vfs_ls`; when true, call new `_ls_long_children(path, node, state)` helper; include `long=True` and `columns` in result |
| `src/rdc/handlers/_helpers.py` | In `_build_shader_cache`, store `inputs` (len of `readOnlyResources`) and `outputs` (len of `readWriteResources`) into each `state.shader_meta[sid]` entry |

### New internal helper in `handlers/vfs.py`

`_ls_long_children(path: str, node: VfsNode, state: DaemonState) -> tuple[list[str], list[dict]]`

Dispatches on top-level path segment:
- `/passes` — iterate `state.vfs_tree.pass_list`; match child names; return draws/dispatches/triangles from pass stats
- `/draws` — call `walk_actions` on root actions; build eid→FlatAction map; for each child EID look up name, flags, num_indices, num_instances; compute triangles and type string via `_action_type_str`
- `/events` — same walk; return eid, name, type for all events
- `/resources` — for each child name (resource ID): look up `state.res_names`, `state.res_types`, `state.res_rid_map`; extract size via `getattr(rid_obj, "byteSize", "-")`
- `/textures` — for each child ID: look up `state.tex_map`; return width, height, format name (via `fmt.Name()` if available)
- `/buffers` — for each child ID: look up `state.buf_map`; return length
- `/shaders` — ensure `_build_shader_cache` called; for each child ID look up `state.shader_meta`; return stages (comma-joined), entry, inputs, outputs
- default — return `["NAME", "TYPE"]` with only name and kind per child

---

## Commit 2: `feat(vfs): add -l flag to rdc ls and render_ls_long formatter`

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/commands/vfs.py` | Add `@click.option("-l", "--long", "use_long", is_flag=True, help="Long format (TSV)")` to `ls_cmd`; guard `-l` and `-F` mutual exclusion with a check + `raise SystemExit(1)`; when `use_long`, pass `"long": True` in RPC params; if `use_json`, pass enriched result to `write_json`; else call `render_ls_long(children, columns)` |
| `src/rdc/vfs/formatter.py` | Add `render_ls_long(children: list[dict], columns: list[str]) -> str`; header = `"\t".join(columns)`; rows = one tab-joined line per child where each value is `str(child.get(col.lower(), "-") or "-")`; return `"\n".join([header, *rows])` |

### Key details

- Column key mapping: column header (uppercase) → child dict key (lowercase). E.g. `"DRAWS"` → `child["draws"]`.
- `-F` and `-l` check: `if classify and use_long: click.echo("error: -F and -l are mutually exclusive", err=True); raise SystemExit(1)`
- When `use_long` but response does not contain `"long": true` (e.g. path has no long schema), fall back to bare name rendering with a warning on stderr.

---

## Commit 3: `test: cover vfs_ls long mode`

### New Test File

| File | Content |
|------|---------|
| `tests/unit/test_vfs_formatter.py` | Unit tests for `render_ls_long` and regression tests for `render_ls` |

### Updated Test Files

| File | Tests Added |
|------|-------------|
| `tests/unit/test_vfs_handlers.py` | 14 new tests for `_handle_vfs_ls` with `long=True` across all path contexts (see test-plan.md) |
| `tests/unit/test_vfs_commands.py` | 8 new tests for `-l` CLI flag behavior (see test-plan.md) |
| `tests/integration/test_daemon_handlers_real.py` | 7 new GPU integration tests in `TestVfsLsLong` class (see test-plan.md) |

---

## File Conflict Analysis

| File | Worktree |
|------|----------|
| `src/rdc/handlers/vfs.py` | Single agent |
| `src/rdc/handlers/_helpers.py` | Single agent |
| `src/rdc/commands/vfs.py` | Single agent |
| `src/rdc/vfs/formatter.py` | Single agent |
| `tests/unit/test_vfs_formatter.py` | Single agent (new file) |
| `tests/unit/test_vfs_handlers.py` | Single agent |
| `tests/unit/test_vfs_commands.py` | Single agent |
| `tests/integration/test_daemon_handlers_real.py` | Single agent |

No parallel split needed; all files belong to one feature boundary.

---

## Acceptance Criteria

- [ ] `rdc ls -l /passes` outputs a TSV with header `NAME\tDRAWS\tDISPATCHES\tTRIANGLES`
- [ ] `rdc ls -l /draws` outputs a TSV with header `EID\tNAME\tTYPE\tTRIANGLES\tINSTANCES`
- [ ] `rdc ls -l /resources` outputs a TSV with header `ID\tNAME\tTYPE\tSIZE`
- [ ] `rdc ls -l /shaders` outputs a TSV with header `ID\tSTAGES\tENTRY\tINPUTS\tOUTPUTS`
- [ ] `rdc ls -l /textures` outputs a TSV with header `ID\tNAME\tWIDTH\tHEIGHT\tFORMAT`
- [ ] `rdc ls -l /buffers` outputs a TSV with header `ID\tNAME\tLENGTH`
- [ ] `rdc ls -l --json /passes` emits valid JSON with `columns` and enriched children
- [ ] `rdc ls -l -F` exits with code 1 and a clear mutual-exclusion error
- [ ] `rdc ls /passes` without `-l` still outputs bare names (no regression)
- [ ] `vfs_ls` without `long` param returns existing format (no regression)
- [ ] `pixi run lint && pixi run test` passes with zero failures
- [ ] Coverage remains >= 95%
