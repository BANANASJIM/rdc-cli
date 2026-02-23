# Proposal: VFS ls Long Format (-l flag)

**Date:** 2026-02-22
**Phase:** Design-deviation fix
**Status:** Draft

---

## Problem

`rdc ls` is missing the `-l` / `--long` flag specified in `设计/路径寻址设计.md`.

Current behavior:
- `rdc ls [path]` — bare names, one per line
- `-F/--classify` appends `/`, `*`, `@` suffixes
- `--json` emits the raw children array
- No `-l` flag exists at all

Design requires:
```
rdc ls -l /passes       # TSV: NAME  DRAWS  DISPATCHES  TRIANGLES
rdc ls -l /draws        # TSV: EID  NAME  TYPE  TRIANGLES  INSTANCES
rdc ls -l /resources    # TSV: ID  NAME  TYPE  SIZE
rdc ls -l /shaders      # TSV: ID  STAGES  ENTRY  INPUTS  OUTPUTS
```

---

## Solution

**Option 1 (chosen):** Add `long: bool` to `vfs_ls` RPC. When `true`, the daemon enriches each child entry with context-specific metadata columns. The CLI passes `long=True` when `-l` is given and renders tab-separated output.

**Option 2 (rejected):** CLI makes per-child sub-RPCs to fetch metadata (N+1 calls). Rejected: unacceptable latency for large directories.

---

## Design

### RPC protocol change

`vfs_ls` gains an optional boolean parameter:

```json
{ "method": "vfs_ls", "params": { "path": "/passes", "long": true } }
```

Response when `long=false` (existing, backward-compatible):
```json
{ "path": "/passes", "kind": "dir", "children": [{"name": "...", "kind": "dir"}] }
```

Response when `long=true`:
```json
{
  "path": "/passes",
  "kind": "dir",
  "long": true,
  "columns": ["NAME", "DRAWS", "DISPATCHES", "TRIANGLES"],
  "children": [
    {"name": "Pass#1", "kind": "dir", "draws": 42, "dispatches": 0, "triangles": 180000}
  ]
}
```

The `columns` array declares which metadata keys are present. The CLI uses it to build the header row.

### Metadata by path context

Path resolution is done by stripping the top-level segment from `path`:

| Path prefix | Header columns | Daemon data source |
|-------------|---------------|-------------------|
| `/passes` | `NAME DRAWS DISPATCHES TRIANGLES` | `vfs_tree.pass_list` (already in `DaemonState`) |
| `/draws` | `EID NAME TYPE TRIANGLES INSTANCES` | `walk_actions` flat action list |
| `/events` | `EID NAME TYPE` | `walk_actions` flat action list |
| `/resources` | `ID NAME TYPE SIZE` | `state.res_names`, `state.res_types`, `state.res_rid_map` |
| `/textures` | `ID NAME WIDTH HEIGHT FORMAT` | `state.tex_map`, `state.res_names` |
| `/buffers` | `ID NAME LENGTH` | `state.buf_map`, `state.res_names` |
| `/shaders` | `ID STAGES ENTRY INPUTS OUTPUTS` | `state.shader_meta` (built lazily on first `/shaders` access) |
| Other dirs | `NAME TYPE` | minimal: just child name + kind |

For `/resources`, SIZE comes from `state.res_rid_map` attributes (`byteSize` or equivalent).

For `/draws`, the flat list is obtained with `walk_actions(state.adapter.get_root_actions(), state.structured_file)` and filtered to draws-only (already in VFS tree). TRIANGLES = `(num_indices // 3) * num_instances`. TYPE uses the existing `_action_type_str(flags)` helper.

For `/shaders`, the long format is only available after the shader cache is built. The handler calls `_build_shader_cache(state)` if needed before collecting metadata.

INPUTS = count of `readOnlyResources`, OUTPUTS = count of `readWriteResources` from shader reflection stored in `state.shader_meta`. Extend `shader_meta` entries to store `inputs` and `outputs` counts alongside existing `stages`, `uses`, `first_eid`, `entry`.

### CLI change

`ls_cmd` gains a new option:

```python
@click.option("-l", "--long", "use_long", is_flag=True, help="Long format (TSV with metadata)")
```

When `-l` is set:
1. Call `vfs_ls` with `{"path": path, "long": True}`
2. If response has `long: true`, render with `render_ls_long(children, columns)` from `vfs/formatter.py`
3. `--json` with `-l` emits the full enriched response as-is (children array with all metadata fields)

`-F/--classify` and `-l` are mutually exclusive (print error and exit 1 if both given).

### Formatter change

Add `render_ls_long(children, columns)` to `src/rdc/vfs/formatter.py`:
- Prints a TSV header line from `columns`
- Prints one TSV row per child, substituting `-` for missing/None values

### Backward compatibility

- `long` parameter defaults to `false`; existing callers (including shell completion) are unaffected
- Existing `children` entries always contain `name` and `kind`; new fields are additive

---

## Files Changed

| File | Change |
|------|--------|
| `src/rdc/handlers/vfs.py` | Accept `long` param; dispatch to `_ls_long_children()` helper |
| `src/rdc/handlers/_helpers.py` | `_build_shader_cache` stores `inputs`/`outputs` counts in `shader_meta` |
| `src/rdc/commands/vfs.py` | Add `-l`/`--long` flag to `ls_cmd`; enforce `-F`/`-l` mutex; pass `long=True` to RPC |
| `src/rdc/vfs/formatter.py` | Add `render_ls_long(children, columns)` |
| `tests/unit/test_vfs_commands.py` | Tests for `-l` CLI flag (mock-based) |
| `tests/unit/test_vfs_handlers.py` | Tests for `vfs_ls` with `long=True` daemon handler |
| `tests/integration/test_daemon_handlers_real.py` | GPU integration tests for `-l` on real capture |
