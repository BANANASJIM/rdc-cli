# Test Plan: Phase 1.5 — VFS Path Addressing

## Scope

- **In scope**: Path router, tree cache, daemon VFS handlers, CLI ls/cat/tree/_complete
- **Out of scope**: `rdc find`, binary export (SaveTexture), `ls -l` domain columns

## Test Matrix

| Layer | GPU? | What |
|-------|------|------|
| Unit | No | `resolve_path()` for all route patterns; tree cache skeleton build + dynamic populate + LRU |
| Unit | No | CLI commands (ls/cat/tree/_complete) with monkeypatched VFS calls |
| Mock | No | Daemon `vfs_ls`/`vfs_tree` via `_handle_request()` with mock adapter |
| Integration | Yes | `rdc open` → `rdc ls /` → `rdc cat /info` → `rdc tree / --depth 1` end-to-end |

## Unit Tests: Path Router (`test_vfs_router.py`)

### Happy path
- `resolve_path("/")` → kind=dir, handler=None
- `resolve_path("/info")` → kind=leaf, handler="info"
- `resolve_path("/stats")` → kind=leaf, handler="stats"
- `resolve_path("/log")` → kind=leaf, handler="log"
- `resolve_path("/capabilities")` → kind=leaf, handler="capabilities"
- `resolve_path("/events")` → kind=dir, handler=None
- `resolve_path("/events/42")` → kind=leaf, handler="event", args={eid: 42}
- `resolve_path("/draws")` → kind=dir, handler=None
- `resolve_path("/draws/142")` → kind=dir, handler=None
- `resolve_path("/draws/142/pipeline")` → kind=dir, handler=None
- `resolve_path("/draws/142/pipeline/ia")` → kind=leaf, handler="pipeline", args={eid: 142, section: "ia"}
- `resolve_path("/draws/142/pipeline/summary")` → kind=leaf, handler="pipeline", args={eid: 142, section: None}
- `resolve_path("/draws/142/shader")` → kind=dir, handler=None
- `resolve_path("/draws/142/shader/ps")` → kind=dir, handler=None
- `resolve_path("/draws/142/shader/ps/disasm")` → kind=leaf, handler="shader_disasm", args={eid: 142, stage: "ps"}
- `resolve_path("/draws/142/shader/ps/reflect")` → kind=leaf, handler="shader_reflect", args={eid: 142, stage: "ps"}
- `resolve_path("/draws/142/shader/ps/constants")` → kind=leaf, handler="shader_constants", args={eid: 142, stage: "ps"}
- `resolve_path("/draws/142/shader/ps/source")` → kind=leaf, handler="shader_source", args={eid: 142, stage: "ps"}
- `resolve_path("/draws/142/shader/ps/binary")` → kind=leaf_bin, handler="shader_binary", args={eid: 142, stage: "ps"}
- `resolve_path("/draws/142/bindings")` → kind=dir, handler=None
- `resolve_path("/passes")` → kind=dir, handler=None
- `resolve_path("/passes/GBuffer")` → kind=dir, handler=None
- `resolve_path("/passes/GBuffer/info")` → kind=leaf, handler="pass", args={name: "GBuffer"}
- `resolve_path("/passes/GBuffer/draws")` → kind=dir, handler=None
- `resolve_path("/passes/GBuffer/attachments")` → kind=dir, handler=None
- `resolve_path("/resources")` → kind=dir, handler=None
- `resolve_path("/resources/88")` → kind=dir, handler=None
- `resolve_path("/resources/88/info")` → kind=leaf, handler="resource", args={id: 88}
- `resolve_path("/shaders")` → kind=dir, handler=None
- `resolve_path("/current")` → kind=alias, handler=None

### Error / edge cases
- `resolve_path("/nonexistent")` → None
- `resolve_path("/draws/abc")` → None (non-numeric eid)
- `resolve_path("/draws/142/shader/ps/nonexistent")` → None
- `resolve_path("")` → resolves as "/"
- `resolve_path("/draws/142/")` → same as without trailing slash
- `resolve_path("/../etc/passwd")` → None (path traversal blocked)

## Unit Tests: Tree Cache (`test_vfs_tree_cache.py`)

### Static skeleton
- Build skeleton with 3 draws (eid 10, 20, 30), 2 passes ("Shadow", "GBuffer"), 2 resources (id 5, 10)
- Assert root has all expected children
- Assert `/draws` children = ["10", "20", "30"]
- Assert `/draws/10` children = ["pipeline", "shader", "bindings"]
- Assert `/events` children include all event eids
- Assert `/passes` children = ["Shadow", "GBuffer"]
- Assert `/passes/Shadow` children = ["info", "draws", "attachments"]
- Assert `/resources/5` children = ["info"]
- Assert `/current` kind = "alias"

### Dynamic subtree population
- Build skeleton, then call `populate_draw_subtree(tree, 10, mock_pipe_state)`
- Mock pipe state with VS + PS active
- Assert `/draws/10/shader` children = ["vs", "ps"]
- Assert `/draws/10/shader/ps` children = ["disasm", "source", "reflect", "constants", "binary"]
- Assert `/draws/10/shader/ps/disasm` kind = "leaf"
- Assert `/draws/10/shader/ps/binary` kind = "leaf_bin"

### LRU eviction
- Set LRU capacity to 2
- Populate subtrees for eid 10, 20, 30
- Assert eid 10's subtree was evicted (get_draw_subtree(10) returns None)
- Assert eid 20 and 30 still cached

## Unit Tests: Daemon VFS Handlers (`test_vfs_daemon.py`)

Test via `_handle_request()` with `DaemonState` + mock adapter (same pattern as `test_draws_events_daemon.py`).

### Happy path
- `vfs_ls` path="/" → returns root children with correct kinds
- `vfs_ls` path="/draws" → returns list of draw eids
- `vfs_ls` path="/draws/<eid>/shader" → triggers dynamic populate, returns stage children
- `vfs_tree` path="/" depth=1 → returns root tree with children
- `vfs_tree` path="/draws/<eid>" depth=2 → returns nested structure

### Error cases
- `vfs_ls` with no adapter → error -32002
- `vfs_ls` path="/nonexistent" → error -32001
- `vfs_ls` path="/current" with current_eid=0 → error -32002 "no event selected"
- `vfs_tree` depth=0 → error -32602
- `vfs_tree` depth=9 → error -32602

## Unit Tests: CLI Commands (`test_vfs_commands.py`)

Monkeypatch `_call` or `_daemon_call` in vfs command module (no network).

### `rdc ls`
- `ls /` → exit 0, output contains "info", "draws", "passes"
- `ls -F /` → exit 0, output contains "draws/", "current@", "info" (no suffix for text leaf)
- `ls /draws/142` → exit 0, output "pipeline\nshader\nbindings"
- `ls --json /` → exit 0, valid JSON array
- `ls /info` (leaf, not dir) → exit 1, "Not a directory"

### `rdc cat`
- `cat /info` → exit 0, calls "info" RPC, renders key-value output
- `cat /draws/142/shader/ps/disasm` → exit 0, calls "shader_disasm" RPC, outputs disasm text
- `cat /draws/142/shader` (dir) → exit 1, "Is a directory"
- `cat /nonexistent` → exit 1, "not found"
- `cat --json /info` → exit 0, JSON output
- `cat` binary node on TTY → exit 1, "binary data, use redirect"

### `rdc tree`
- `tree / --depth 1` → exit 0, ASCII tree with root children
- `tree /draws/142 --depth 2` → exit 0, nested ASCII tree
- `tree --json /` → exit 0, valid JSON
- `tree / --depth 0` → exit error (click validation, depth must be 1-8)

### `rdc _complete`
- `_complete /draws/14` → outputs paths starting with "14" under /draws/
- `_complete /draws/142/sh` → outputs "/draws/142/shader/"
- `_complete /` → outputs all root children with / suffix for dirs

### Error paths (all commands)
- No session → exit 1, "no active session"
- Daemon unreachable → exit 1, "daemon unreachable"

## Integration Tests (`test_daemon_handlers_real.py`)

### With real capture file
- `vfs_ls` path="/" → returns non-empty children, "draws" in children
- `vfs_ls` path="/draws" → returns at least 1 draw eid
- `vfs_ls` path="/draws/<first_eid>/shader" → returns at least 1 stage (e.g., "vs")
- `vfs_tree` path="/" depth=1 → root tree has expected structure
- `cat /info` equivalent: call `vfs_ls /info` → kind=leaf, then call "info" → valid result

## Assertions

- **Exit codes**: 0 on success, 1 on all errors
- **stdout**: ls outputs one name per line; cat outputs text content; tree outputs ASCII art
- **stderr**: all error messages go to stderr
- **JSON**: `--json` on all 3 commands produces valid JSON
- **TSV**: ls does NOT use TSV (bare names); cat content format depends on handler
- **Type markers**: `-F` appends exactly `/` `*` `@` or nothing

## Risks & Rollback

- **Potential regressions**: `_load_replay()` modification could slow down `rdc open` if skeleton build is expensive → mitigate by profiling with large captures
- **Existing command breakage**: None — ls/cat/tree are new commands, no existing commands modified
- **Mock adequacy**: Tree cache tests need mock actions with proper flags; existing MockReplayController + ActionDescription should suffice
- **Rollback**: revert the branch; no schema changes, no persistent state changes
