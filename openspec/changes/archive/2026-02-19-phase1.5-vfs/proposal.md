# Proposal: Phase 1.5 — VFS Path Addressing

## Summary

Add virtual filesystem navigation layer: `rdc ls`, `rdc cat`, `rdc tree`, `rdc _complete`.
Exposes the entire capture as a path hierarchy (Unix VFS philosophy).

## Motivation

- AI agents and shell scripts need a uniform discovery interface — `ls` + `cat` is sufficient
- Eliminates the need for users to memorize 20+ command names; paths are self-documenting
- Foundation for Phase 2+: new features only need a route table entry, not a new CLI command
- `ls -F` type markers enable agent type-discovery without JSON parsing

## Scope

### In scope
- Path router: `resolve_path()` pure function mapping regex patterns to handlers
- VFS tree cache: static skeleton built at `rdc open`, dynamic subtrees on demand
- Daemon RPCs: `vfs_ls`, `vfs_tree` (two new methods)
- CLI commands: `ls`, `cat`, `tree`, `_complete` (four new commands)
- `ls -F` classification: `/` dir, `*` binary, `@` alias
- `/current` alias resolution with explicit "no event selected" error
- Binary TTY protection on `cat`

### Out of scope (Phase 2+)
- `rdc find` (advanced search)
- `/textures/<id>/image.png` binary export (requires SaveTexture)
- `/by-marker/` hierarchy population (requires marker tree walk)
- `ls -l` domain-aware columns (e.g., pass draws/triangles)
- `cat` formatter for binary buffer data

## Architecture

### New package: `src/rdc/vfs/`

```
src/rdc/vfs/
├── __init__.py
├── router.py       # ROUTE_TABLE, PathMatch, resolve_path()
├── tree_cache.py   # VfsNode, VfsTree, build_vfs_skeleton(), populate_draw_subtree()
└── formatter.py    # render_ls(), render_tree_root()
```

### Path router (`router.py`)

Pure regex-based route table. Each entry maps a path pattern to:
- `kind`: dir | leaf | leaf_bin | alias
- `handler`: existing daemon RPC method name (for `cat`)
- Named capture groups extracted as handler args

```python
@dataclass(frozen=True)
class PathMatch:
    kind: str                    # "dir", "leaf", "leaf_bin", "alias"
    handler: str | None          # RPC method name for cat, None for dirs
    args: dict[str, Any]         # extracted path params {eid: 142, stage: "ps"}
```

`resolve_path()` returns `PathMatch | None`. Unknown paths return `None`.

### Tree cache (`tree_cache.py`)

- **Static skeleton**: built once at `_load_replay()` from action tree + resource list
  - Root children: capabilities, info, stats, log, events/, draws/, by-marker/, passes/, resources/, textures/, buffers/, shaders/, current@
  - Per-draw: `/draws/<eid>/` with pipeline/, shader/, bindings/ stubs
  - Per-event: `/events/<eid>` as leaf
  - Per-pass: `/passes/<name>/` with info, draws/, attachments/
  - Per-resource: `/resources/<id>/` with info
- **Dynamic subtrees**: populated on first access (e.g., shader stages under `/draws/<eid>/shader/`)
  - Triggers `SetFrameEvent` + `GetPipelineState` to discover active stages
  - LRU cache (capacity 64 draw subtrees)

### `cat` does NOT have its own RPC

`cat` resolves the path via `resolve_path()`, then calls the existing RPC method named in `PathMatch.handler` with the extracted args. No logic duplication.

| VFS path | handler RPC | equivalent CLI |
|----------|-------------|---------------|
| `/info` | `info` | `rdc info` |
| `/stats` | `stats` | `rdc stats` |
| `/log` | `log` | `rdc log` |
| `/events/<eid>` | `event` | `rdc event <eid>` |
| `/draws/<eid>/shader/<stage>/disasm` | `shader_disasm` | `rdc shader <eid> <stage>` |
| `/draws/<eid>/shader/<stage>/reflect` | `shader_reflect` | `rdc shader <eid> <stage> --reflect` |
| `/draws/<eid>/shader/<stage>/constants` | `shader_constants` | `rdc shader <eid> <stage> --constants` |
| `/draws/<eid>/shader/<stage>/source` | `shader_source` | `rdc shader <eid> <stage> --source` |
| `/draws/<eid>/pipeline/<section>` | `pipeline` | `rdc pipeline <eid> <section>` |
| `/passes/<name>/info` | `pass` | `rdc pass <name>` |
| `/resources/<id>/info` | `resource` | `rdc resource <id>` |

### Daemon RPC methods

**`vfs_ls`**: params `{path}` → returns `{path, kind, children: [{name, kind}]}`
**`vfs_tree`**: params `{path, depth}` → returns `{path, tree: {name, kind, children: [...]}}` (recursive)

Both handle `/current` alias resolution server-side.
Both return `-32002` if no replay loaded, `-32001` if path not found.

### CLI commands (`src/rdc/commands/vfs.py`)

- `rdc ls [path]` — calls `vfs_ls`, renders one name per line. `-F` adds type suffix. `--json` outputs raw.
- `rdc cat <path>` — calls `vfs_ls` to check kind, then calls handler RPC. Dir → error. Binary on TTY → error.
- `rdc tree [path] [--depth N]` — calls `vfs_tree`, renders ASCII tree. Default depth 2, max 8.
- `rdc _complete <partial>` — hidden command for shell tab completion. Calls `vfs_ls` on parent dir, filters by prefix.

### Error handling

| Condition | Exit code | Message |
|-----------|-----------|---------|
| No session | 1 | `error: no active session (run 'rdc open' first)` |
| Path not found | 1 | `error: not found: <path>` |
| `cat` on directory | 1 | `error: <path>: Is a directory` |
| `cat` binary on TTY | 1 | `error: <path>: binary data, use redirect: rdc cat <path> > file` |
| `/current` with no eid | 1 | `error: /current: no event selected` |

## Files changed

### New files
- `src/rdc/vfs/__init__.py`
- `src/rdc/vfs/router.py`
- `src/rdc/vfs/tree_cache.py`
- `src/rdc/vfs/formatter.py`
- `src/rdc/commands/vfs.py`
- `tests/unit/test_vfs_router.py`
- `tests/unit/test_vfs_tree_cache.py`
- `tests/unit/test_vfs_commands.py`
- `tests/unit/test_vfs_daemon.py`

### Modified files
- `src/rdc/daemon_server.py` — DaemonState field + `_load_replay()` skeleton build + `vfs_ls`/`vfs_tree` handlers
- `src/rdc/cli.py` — register 4 new commands
- `tests/mocks/mock_renderdoc.py` — may need minor extensions for tree cache tests
