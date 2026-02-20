# Tasks: Phase 2 — VFS Binary Export Infrastructure

## Dependencies

Tasks are ordered by dependency. Tests are written before or alongside implementation (No Test Design, No Implementation).

---

## Phase A: Binary Infrastructure (no handler changes yet)

### A1. Temp directory lifecycle
- [ ] Add `temp_dir: Path | None = None` field to `DaemonState` in `src/rdc/daemon_server.py`
- [ ] In `_load_replay()`, after building VFS skeleton: `state.temp_dir = Path(tempfile.mkdtemp(prefix=f"rdc-{state.token[:8]}-"))`
- [ ] In `shutdown` handler: `shutil.rmtree(state.temp_dir, ignore_errors=True)` before adapter/cap shutdown
- [ ] Write temp dir lifecycle tests in `tests/unit/test_binary_daemon.py`:
  - Temp dir created after `_load_replay()` completes
  - Temp dir path starts with `rdc-<token[:8]>-`
  - Temp dir removed after shutdown handler runs
- [ ] Verify: `pixi run test -k test_binary_daemon`

### A2. Binary delivery in cat_cmd
- [ ] Add `-o` / `--output` option to `cat_cmd` in `src/rdc/commands/vfs.py`
- [ ] Add `leaf_bin` branch after resolving path and kind:
  - If `sys.stdout.isatty()` and not `--raw`: print error `"error: <path>: binary data, use redirect or -o"`, exit 1
  - Call handler RPC, receive `{"path", "size"}`
  - If `-o <file>`: `shutil.move(path, file)`
  - Else (piped stdout): read temp file -> `sys.stdout.buffer.write()` -> delete temp
- [ ] Write CLI binary delivery tests in `tests/unit/test_vfs_binary.py`:
  - TTY protection: `isatty=True`, no `--raw` -> exit 1 with hint message
  - TTY bypass: `isatty=True` with `--raw` -> delivers binary
  - `-o` delivery: temp file moved to output path
  - Pipe delivery: `isatty=False` -> binary written to stdout, temp deleted
  - Temp cleanup: temp file deleted after pipe delivery
  - Error: handler returns error -> propagated correctly
  - Monkeypatch `_daemon_call`, `resolve_path`, `sys.stdout.isatty`
- [ ] Verify: `pixi run test -k test_vfs_binary`

---

## Phase B: VFS Routes + Tree Cache

### B1. Route table expansion
- [ ] Add `leaf_bin` routes to `src/rdc/vfs/router.py`:
  ```
  /textures/<id>           dir       None
  /textures/<id>/info      leaf      tex_info
  /textures/<id>/image.png leaf_bin  tex_export
  /textures/<id>/mips      dir       None
  /textures/<id>/mips/<n>.png leaf_bin tex_export (with mip arg)
  /textures/<id>/data      leaf_bin  tex_raw
  /buffers/<id>            dir       None
  /buffers/<id>/info       leaf      buf_info
  /buffers/<id>/data       leaf_bin  buf_raw
  /draws/<eid>/targets     dir       None
  /draws/<eid>/targets/color<n>.png  leaf_bin  rt_export
  /draws/<eid>/targets/depth.png     leaf_bin  rt_depth
  ```
- [ ] Add route tests to `tests/unit/test_vfs_router.py`:
  - Each new route resolves correctly with expected kind, handler, and coerced args
  - `/textures/42/image.png` -> kind=leaf_bin, handler=tex_export, args={id: 42}
  - `/textures/42/mips` -> kind=dir
  - `/textures/42/mips/3.png` -> kind=leaf_bin, handler=tex_export, args={id: 42, mip: 3}
  - `/buffers/7/data` -> kind=leaf_bin, handler=buf_raw, args={id: 7}
  - `/draws/100/targets/color0.png` -> kind=leaf_bin, handler=rt_export, args={eid: 100, target: 0}
  - `/draws/100/targets/depth.png` -> kind=leaf_bin, handler=rt_depth, args={eid: 100}
  - `/textures/42` -> kind=dir
  - `/buffers/7` -> kind=dir
  - `/draws/100/targets` -> kind=dir
  - Non-matching paths still return None
- [ ] Verify: `pixi run test -k test_vfs_router`

### B2. Tree cache expansion
- [ ] Modify `build_vfs_skeleton()` in `src/rdc/vfs/tree_cache.py`:
  - Classify resources: textures (type in {Texture1D, Texture2D, Texture3D}) vs buffers (type == Buffer)
  - Populate `/textures/` with classified texture resource IDs as children
  - Each `/textures/<id>/` gets children `["info", "image.png", "mips", "data"]` with correct kinds
  - Each `/textures/<id>/mips/` children populated from resource mip count: `["0.png", "1.png", ...]`
  - Populate `/buffers/` with classified buffer resource IDs as children
  - Each `/buffers/<id>/` gets children `["info", "data"]` with correct kinds
- [ ] Add `"targets"` to `_DRAW_CHILDREN`
- [ ] Expand `populate_draw_subtree()` to populate `/draws/<eid>/targets/`:
  - Call `GetOutputTargets()` on pipe state -> one `color<n>.png` per non-null target
  - Call `GetDepthTarget()` on pipe state -> `depth.png` if non-null
  - Register children as `leaf_bin` nodes in `tree.static`
- [ ] Add tree cache tests to `tests/unit/test_vfs_tree_cache.py`:
  - Skeleton: `/textures/` children match texture resource IDs
  - Skeleton: `/buffers/` children match buffer resource IDs
  - Skeleton: `/textures/<id>/` has children `["info", "image.png", "mips", "data"]`
  - Skeleton: `/textures/<id>/mips/` has children matching resource mip count
  - Skeleton: `/buffers/<id>/` has children `["info", "data"]`
  - Skeleton: draw nodes include `"targets"` in children
  - Dynamic: `populate_draw_subtree()` populates targets with correct color/depth children
  - Dynamic: no depth target -> no `depth.png` child
  - Dynamic: multiple color targets -> `color0.png`, `color1.png`, etc.
- [ ] Verify: `pixi run test -k test_vfs_tree_cache`

---

## Phase C: Daemon Handlers

### C1. tex_info + tex_export + tex_raw handlers
- [ ] Add `SaveTexture(texsave, path)` and `GetTextureData(resource_id, sub)` to `MockReplayController` in `tests/mocks/mock_renderdoc.py`
- [ ] Add `TextureSave` dataclass to mock module (mip, slice, destType fields)
- [ ] Add `tex_info` handler to `_handle_request()` in `daemon_server.py`:
  - Lookup texture by resource ID from `adapter.get_resources()`
  - Return `{id, name, format, width, height, depth, mips, array_size}`
  - Error if resource not found
- [ ] Add `tex_export` handler (accepts optional `mip` arg, default 0):
  - Build `TextureSave` config (mip=mip, slice=0, PNG)
  - Validate mip < resource.mips, error if out of range
  - `controller.SaveTexture(texsave, temp_path)` where temp_path is in `state.temp_dir`
  - Return `{"path": temp_path, "size": file_size}`
  - Error if `state.temp_dir` is None
- [ ] Add `tex_raw` handler:
  - `controller.GetTextureData(resource_id, sub)` -> write bytes to temp file
  - Return `{"path": temp_path, "size": file_size}`
- [ ] Register `tex_info`, `tex_export`, `tex_raw` in `_handle_request()` dispatch
- [ ] Write handler tests in `tests/unit/test_binary_daemon.py`:
  - `tex_info`: happy path returns correct fields
  - `tex_info`: resource not found -> error -32001
  - `tex_export`: happy path with mip=0 writes file, returns path + size
  - `tex_export`: happy path with mip=2 writes correct mip level
  - `tex_export`: mip out of range -> error
  - `tex_export`: temp dir missing -> error
  - `tex_raw`: happy path writes raw bytes, returns path + size
- [ ] Verify: `pixi run test -k test_binary_daemon`

### C2. buf_info + buf_raw handlers
- [ ] Add `GetBufferData(resource_id, offset, length)` to `MockReplayController`
- [ ] Add `buf_info` handler to `_handle_request()`:
  - Lookup buffer by resource ID from `adapter.get_resources()`
  - Return `{id, name, size, usage}`
  - Error if resource not found
- [ ] Add `buf_raw` handler:
  - `controller.GetBufferData(resource_id, 0, 0)` -> write bytes to temp file
  - Return `{"path": temp_path, "size": file_size}`
- [ ] Register `buf_info`, `buf_raw` in dispatch
- [ ] Write handler tests in `tests/unit/test_binary_daemon.py`:
  - `buf_info`: happy path returns correct fields
  - `buf_info`: resource not found -> error -32001
  - `buf_raw`: happy path writes file, returns path + size
- [ ] Verify: `pixi run test -k test_binary_daemon`

### C3. rt_export + rt_depth handlers
- [ ] Add `rt_export` handler to `_handle_request()`:
  - `SetFrameEvent(eid)` -> `GetPipelineState()` -> `GetOutputTargets()[target]`
  - `SaveTexture` to temp path `rt_<eid>_color<target>.png`
  - Return `{"path": temp_path, "size": file_size}`
  - Error if no color targets, target index OOB
- [ ] Add `rt_depth` handler:
  - `SetFrameEvent(eid)` -> `GetPipelineState()` -> `GetDepthTarget()`
  - `SaveTexture` to temp path `rt_<eid>_depth.png`
  - Return `{"path": temp_path, "size": file_size}`
  - Error if no depth target (resource ID == 0)
- [ ] Register `rt_export`, `rt_depth` in dispatch
- [ ] Write handler tests in `tests/unit/test_binary_daemon.py`:
  - `rt_export`: happy path returns correct path + size
  - `rt_export`: no color targets -> error
  - `rt_export`: target index OOB -> error
  - `rt_depth`: happy path returns correct path + size
  - `rt_depth`: no depth target -> error
  - `rt_export`/`rt_depth`: eid out of range -> error
- [ ] Verify: `pixi run test -k test_binary_daemon`

---

## Phase D: CLI Convenience Commands

### D1. Export commands
- [ ] Create `src/rdc/commands/export.py` with shared binary delivery helper:
  - `_binary_deliver(vfs_path, output)` — construct path, call `_daemon_call`, handle `-o` / pipe / TTY
- [ ] Add `texture_cmd`:
  - `rdc texture <id> [-o output] [--mip N]` -> delegates to `/textures/<id>/image.png` (mip=0) or `/textures/<id>/mips/<N>.png` (mip>0)
- [ ] Add `rt_cmd`:
  - `rdc rt <eid> [-o output] [--target N]` -> delegates to `/draws/<eid>/targets/color<N>.png`
  - If eid omitted, use current eid from `status` call
- [ ] Add `buffer_cmd`:
  - `rdc buffer <id> [-o output]` -> delegates to `/buffers/<id>/data`
- [ ] Register `texture_cmd`, `rt_cmd`, `buffer_cmd` in `src/rdc/cli.py`
- [ ] Write CLI tests in `tests/unit/test_export_commands.py`:
  - `rdc texture 42 -o out.png` -> calls correct VFS path, writes output
  - `rdc texture 42 --mip 2 -o out.png` -> path = `/textures/42/mips/2.png`
  - `rdc texture 42` piped -> binary to stdout
  - `rdc texture 42` on TTY -> error with hint
  - `rdc rt 100 -o rt.png` -> correct VFS path with default target=0
  - `rdc rt 100 --target 1 -o rt.png` -> correct VFS path with target=1
  - `rdc buffer 7 -o buf.bin` -> correct VFS path
  - Error propagation from daemon
  - Monkeypatch `_daemon_call` and `sys.stdout.isatty`
- [ ] Verify: `pixi run test -k test_export_commands`

---

## Phase E: Integration + Verification

### E1. Mock renderdoc consolidation
- [ ] Review `tests/mocks/mock_renderdoc.py` for completeness:
  - `SaveTexture`, `GetTextureData`, `GetBufferData` on `MockReplayController`
  - `TextureSave` dataclass
  - Mock resources have proper `type` field (Texture2D, Buffer) for classification
- [ ] Ensure existing tests still pass after mock changes
- [ ] Verify: `pixi run test`

### E2. GPU integration tests
- [ ] Add to `tests/integration/`:
  - `test_tex_export_real` — export texture from `hello_triangle.rdc`, verify PNG header
  - `test_buf_raw_real` — export buffer, verify non-empty bytes
  - `test_rt_export_real` — export render target at a draw eid, verify PNG header
  - `test_temp_dir_lifecycle` — open, export, close; verify temp dir cleaned
- [ ] Mark with `@pytest.mark.gpu`
- [ ] Verify: `pixi run test-gpu`

### E3. Final verification
- [ ] `pixi run lint && pixi run test` — all pass
- [ ] `pixi run test-gpu` — integration pass
- [ ] Manual smoke: `rdc open tests/fixtures/hello_triangle.rdc && rdc cat /textures/... > out.png`
- [ ] Manual smoke: `rdc texture <id> -o tex.png && file tex.png`
- [ ] Manual smoke: `rdc rt <eid> -o rt.png && file rt.png`

---

## Estimated test count

| Test file | Estimated cases |
|-----------|----------------|
| test_vfs_binary.py | ~8 (TTY protection, -o delivery, pipe delivery, cleanup, errors) |
| test_vfs_router.py (additions) | ~15 (all new leaf_bin/dir routes including mips) |
| test_vfs_tree_cache.py (additions) | ~10 (texture/buffer/mips skeleton, draw targets subtree) |
| test_binary_daemon.py | ~21 (temp dir lifecycle + 7 handlers x happy/error + mip tests) |
| test_export_commands.py | ~10 (3 commands x happy/error/options + --mip) |
| integration (GPU) | ~4 |
| **Total** | **~68** |
