# Test Plan: Phase 2 — VFS Binary Export Infrastructure

## Scope

- **In scope**: Temp dir lifecycle, binary transport protocol (`leaf_bin` handler dispatch),
  TTY protection, `-o`/`--output` delivery, 7 new daemon handlers (`tex_info`, `tex_export`,
  `tex_raw`, `buf_info`, `buf_raw`, `rt_export`, `rt_depth`), VFS route table additions,
  tree cache expansion (texture/buffer/draw-target children), CLI convenience commands
  (`rdc texture`, `rdc rt`, `rdc buffer`), mock module extensions
- **Out of scope**: Slice/format selection, streaming binary over JSON-RPC, mesh decode,
  pixel readback, `/by-marker/` hierarchy, `rdc find`, shader binary export

## Test Matrix

| Layer | GPU? | What |
|-------|------|------|
| Unit | No | `resolve_path()` for all new `leaf_bin` and `dir` route patterns |
| Unit | No | Tree cache: `/textures/<id>/`, `/buffers/<id>/`, `/draws/<eid>/targets/` children |
| Unit | No | CLI `cat` binary branch: TTY guard, `-o` delivery, pipe delivery, temp cleanup |
| Unit | No | CLI convenience commands (`texture`, `rt`, `buffer`) path construction + delegation |
| Mock | No | Daemon handlers (`tex_info`, `tex_export`, `tex_raw`, `buf_info`, `buf_raw`, `rt_export`, `rt_depth`) via `_handle_request()` with mock adapter |
| Mock | No | Temp dir lifecycle (create on load, clean on shutdown) |
| Integration | Yes | `rdc open` -> `rdc texture <id> -o f.png` -> verify PNG file -> `rdc close` |

## Unit Tests: Path Router (`test_vfs_router.py` — additions)

### New happy-path routes

- `resolve_path("/textures/42")` -> kind=dir, handler=None, args={id: 42}
- `resolve_path("/textures/42/info")` -> kind=leaf, handler="tex_info", args={id: 42}
- `resolve_path("/textures/42/image.png")` -> kind=leaf_bin, handler="tex_export", args={id: 42}
- `resolve_path("/textures/42/mips")` -> kind=dir, handler=None, args={id: 42}
- `resolve_path("/textures/42/mips/0.png")` -> kind=leaf_bin, handler="tex_export", args={id: 42, mip: 0}
- `resolve_path("/textures/42/mips/3.png")` -> kind=leaf_bin, handler="tex_export", args={id: 42, mip: 3}
- `resolve_path("/textures/42/data")` -> kind=leaf_bin, handler="tex_raw", args={id: 42}
- `resolve_path("/buffers/7")` -> kind=dir, handler=None, args={id: 7}
- `resolve_path("/buffers/7/info")` -> kind=leaf, handler="buf_info", args={id: 7}
- `resolve_path("/buffers/7/data")` -> kind=leaf_bin, handler="buf_raw", args={id: 7}
- `resolve_path("/draws/142/targets")` -> kind=dir, handler=None, args={eid: 142}
- `resolve_path("/draws/142/targets/color0.png")` -> kind=leaf_bin, handler="rt_export", args={eid: 142, target: 0}
- `resolve_path("/draws/142/targets/color3.png")` -> kind=leaf_bin, handler="rt_export", args={eid: 142, target: 3}
- `resolve_path("/draws/142/targets/depth.png")` -> kind=leaf_bin, handler="rt_depth", args={eid: 142}

### Edge / error cases

- `resolve_path("/textures/abc")` -> None (non-numeric id)
- `resolve_path("/textures/42/nonexistent")` -> None
- `resolve_path("/buffers/abc")` -> None
- `resolve_path("/draws/142/targets/colorX.png")` -> None (non-numeric target)
- `resolve_path("/textures/42/mips/abc.png")` -> None (non-numeric mip)
- `resolve_path("/textures/42/mips/0")` -> None (missing .png)
- `resolve_path("/draws/142/targets/color0")` -> None (missing .png)
- `resolve_path("/draws/142/targets/depth")` -> None (missing .png)

## Unit Tests: Tree Cache (`test_vfs_tree_cache.py` — additions)

### Texture and buffer skeleton population

- Build skeleton with resources including 2 textures (id 5 type=Texture2D, id 10 type=Texture2D) and 1 buffer (id 20 type=Buffer)
- Assert `/textures` children = ["5", "10"]
- Assert `/textures/5` kind=dir, children=["info", "image.png", "mips", "data"]
- Assert `/textures/5/mips` kind=dir, children=["0.png", "1.png", ...] (from resource mip count)
- Assert `/textures/5/info` kind=leaf
- Assert `/textures/5/image.png` kind=leaf_bin
- Assert `/textures/5/data` kind=leaf_bin
- Assert `/buffers` children = ["20"]
- Assert `/buffers/20` kind=dir, children=["info", "data"]
- Assert `/buffers/20/info` kind=leaf
- Assert `/buffers/20/data` kind=leaf_bin

### No textures or buffers (empty case)

- Build skeleton with resources of type Unknown only
- Assert `/textures` children = []
- Assert `/buffers` children = []

### Draw targets subtree (dynamic populate)

- Build skeleton, populate draw subtree for eid 10 with pipe state that has 2 color targets and 1 depth target
- Assert `/draws/10` children include "targets"
- Assert `/draws/10/targets` kind=dir, children=["color0.png", "color1.png", "depth.png"]
- Assert `/draws/10/targets/color0.png` kind=leaf_bin
- Assert `/draws/10/targets/depth.png` kind=leaf_bin

### Draw targets: no targets at eid

- Populate draw subtree for eid with pipe state returning empty output targets and null depth
- Assert `/draws/<eid>/targets` kind=dir, children=[]

### Draw targets: color only, no depth

- Populate draw subtree with 1 color target and null depth
- Assert `/draws/<eid>/targets` children=["color0.png"] (no depth.png)

### LRU eviction cleans target nodes

- LRU capacity=1, populate eid 10 (with targets), then populate eid 20
- Assert eid 10 target nodes removed from static dict
- Assert `/draws/10/targets` children=[]

## Unit Tests: Daemon Binary Handlers (`test_binary_daemon.py`)

Test via `_handle_request()` with `DaemonState` + mock adapter, same pattern as `test_vfs_daemon.py`. DaemonState must have `temp_dir` set to a real `tmp_path` fixture directory.

### `tex_info` handler

- Happy: request `tex_info` with valid id -> result contains {id, name, format, width, height, depth, mips, array_size}
- Error: request `tex_info` with nonexistent id -> error -32001 "resource <id> not found"
- Error: no adapter -> error -32002

### `tex_export` handler

- Happy: request `tex_export` with valid id, mip=0 -> result has {"path": str, "size": int}, path file exists and size > 0
- Happy: request `tex_export` with valid id, mip=2 -> exports mip level 2
- Error: request `tex_export` with nonexistent id -> error -32001 "resource <id> not found"
- Error: request `tex_export` with mip out of range -> error -32001 "mip <n> out of range"
- Error: SaveTexture fails -> error -32002 "SaveTexture failed"
- Error: temp_dir is None -> error -32002 "temp directory not available"

### `tex_raw` handler

- Happy: request `tex_raw` with valid id -> result has {"path": str, "size": int}, file exists
- Error: nonexistent id -> error -32001

### `buf_info` handler

- Happy: request `buf_info` with valid id -> result contains {id, name, size, usage}
- Error: nonexistent id -> error -32001

### `buf_raw` handler

- Happy: request `buf_raw` with valid id -> result has {"path": str, "size": int}, file exists
- Error: nonexistent id -> error -32001
- Error: temp_dir is None -> error -32002

### `rt_export` handler

- Happy: request `rt_export` with valid eid and target=0 -> result has {"path": str, "size": int}
- Error: no color targets at eid -> error -32001 "no color targets at eid <eid>"
- Error: target index out of range (target=5, only 2 targets) -> error -32001 "target index <n> out of range"
- Error: eid out of range -> error -32002

### `rt_depth` handler

- Happy: request `rt_depth` with valid eid -> result has {"path": str, "size": int}
- Error: no depth target at eid (null resource) -> error -32001 "no depth target at eid <eid>"
- Error: eid out of range -> error -32002

### Temp dir lifecycle

- After `_load_replay()`, `state.temp_dir` is a `Path`, directory exists
- `state.temp_dir` name starts with `rdc-` followed by 8 hex chars
- After `shutdown` handler, temp directory is deleted
- Shutdown with no temp_dir (None) does not crash

## Unit Tests: CLI Binary Cat (`test_vfs_binary.py`)

Monkeypatch `_daemon_call`, `resolve_path`, and `sys.stdout.isatty` in vfs command module.

### TTY protection

- `cat /textures/42/image.png` on TTY (isatty=True, no --raw) -> exit 1, stderr contains "binary data, use redirect or -o"
- `cat /textures/42/image.png --raw` on TTY -> exit 0 (force raw output)

### `-o` / `--output` delivery

- `cat /textures/42/image.png -o /tmp/out.png` -> exit 0, file moved from temp path to /tmp/out.png, temp file deleted
- `cat /buffers/7/data -o /tmp/out.bin` -> exit 0, file exists at target path

### Pipe delivery (stdout not TTY)

- `cat /textures/42/image.png` when isatty=False -> exit 0, binary data written to stdout buffer, temp file deleted

### Error: handler returns error

- Handler returns error (resource not found) -> exit 1, stderr contains error message

### Error: temp file missing

- Handler returns path that does not exist -> exit 1, appropriate error

## Unit Tests: Export Convenience Commands (`test_export_commands.py`)

Monkeypatch the underlying cat logic or `_daemon_call` to verify path construction.

### `rdc texture`

- `texture 42 -o f.png` -> delegates to cat with path `/textures/42/image.png` and output=f.png
- `texture 42 --mip 2 -o f.png` -> delegates to cat with path `/textures/42/mips/2.png`
- `texture 42` on TTY -> exit 1 (TTY protection from cat)
- `texture 42` piped -> exit 0 (binary output to stdout)

### `rdc rt`

- `rt 100 -o f.png` -> delegates to cat with path `/draws/100/targets/color0.png` and output=f.png
- `rt 100 --target 2 -o f.png` -> path = `/draws/100/targets/color2.png`
- `rt 100` with no current eid and no eid arg -> exit 1

### `rdc buffer`

- `buffer 7 -o f.bin` -> delegates to cat with path `/buffers/7/data` and output=f.bin
- `buffer 7` piped -> exit 0

### Error paths (all convenience commands)

- No session -> exit 1, "no active session"
- Invalid resource id (daemon returns not found) -> exit 1

## Mock Module Extensions (`tests/mocks/mock_renderdoc.py`)

The following must be added to the mock module before implementing tests:

- `MockReplayController.SaveTexture(texsave, path)` -> write dummy PNG bytes to path
- `MockReplayController.GetTextureData(resource_id, sub)` -> return bytes object (dummy data)
- `MockReplayController.GetBufferData(resource_id, offset, length)` -> return bytes object
- `MockReplayController.GetOutputTargets()` -> delegate to `MockPipeState.GetOutputTargets()` (already exists)
- `MockReplayController.GetDepthTarget()` -> delegate to `MockPipeState.GetDepthTarget()` (already exists)
- `TextureSave` dataclass for SaveTexture configuration
- `ResourceDescription.type` field must be properly typed (already exists as `ResourceType`)

## Integration Tests (`test_daemon_handlers_real.py` — additions)

### With real capture file (GPU required)

- `tex_info` on first texture resource -> returns valid metadata with width > 0 and height > 0
- `tex_export` on first texture -> returns path to valid PNG file, verify file is a valid PNG (magic bytes `\x89PNG`)
- `buf_raw` on first buffer -> returns path, file size matches reported size
- `rt_export` on first draw call -> returns path to valid PNG
- `rt_depth` on first draw call (if depth target exists) -> returns path to valid PNG
- `vfs_ls /textures` -> returns non-empty children list
- `vfs_ls /buffers` -> returns non-empty children list
- `vfs_ls /draws/<first_draw>/targets` -> returns at least 1 child (color0.png)

## Assertions

- **Exit codes**: 0 on success, 1 on all errors
- **stdout**: `cat` of `leaf_bin` outputs raw bytes to stdout (pipe mode) or writes file (`-o` mode)
- **stderr**: all error messages go to stderr, including TTY protection hint
- **Binary protocol**: daemon handler response is always `{"path": <str>, "size": <int>}` for `leaf_bin` nodes
- **Temp file cleanup**: temp files are deleted after CLI reads them (pipe mode) or moves them (`-o` mode)
- **TTY protection**: `cat` on `leaf_bin` to TTY always exits 1 with redirect hint (unless `--raw`)
- **File integrity**: exported PNG files start with `\x89PNG` magic bytes (integration tests)
- **JSON**: `--json` on cat of `leaf` nodes (tex_info, buf_info) produces valid JSON

## Risks & Rollback

- **Temp dir security**: `/tmp/rdc-<token[:8]>/` must not be world-writable beyond default umask;
  tests should verify directory permissions (0o700)
- **Race condition on temp cleanup**: if CLI crashes between handler call and cleanup, temp files
  leak -> mitigated by whole-directory cleanup on `rdc close` / daemon shutdown
- **Existing test regressions**: tree cache skeleton tests assert `/textures` and `/buffers` have
  empty children -> must update those tests to account for new population logic (the existing
  `test_placeholder_dirs` test will need modification)
- **Mock adequacy**: `SaveTexture` mock must write actual bytes so file-existence assertions work;
  use `tmp_path` fixtures throughout
- **Large texture memory**: `GetTextureData` on large textures could OOM in daemon -> out of scope
  for Phase 2 (no streaming), but integration tests should use small captures
- **Rollback**: revert the branch; no schema changes, no persistent state changes outside `/tmp/`
