# Proposal: Phase 2 — VFS Binary Export Infrastructure

## Summary

Add binary data export to the VFS layer: textures, buffers, and render targets are
exposed as `leaf_bin` nodes. The daemon writes temp files and returns paths via
JSON-RPC; the CLI handles stdout/`-o` delivery and temp cleanup. Three new
convenience commands (`rdc texture`, `rdc rt`, `rdc buffer`) delegate to the VFS
`cat` machinery.

## Motivation

- Phase 1 VFS can only serve text leaves. GPU data (textures, buffers, render
  targets) is inherently binary and is the most common export need.
- RenderDoc's `SaveTexture` / `GetTextureData` / `GetBufferData` already write to
  file paths, so a temp-file protocol avoids base64 bloat and extra memory copies.
- Convenience commands let users do `rdc texture 42 -o albedo.png` without
  memorizing VFS paths, while power users can still `rdc cat /textures/42/image.png > out.png`.

## Scope

### In scope

- Session temp directory: `/tmp/rdc-<first 8 chars of token>/`, created at daemon
  start, cleaned on `shutdown` / `rdc close`
- Binary transport protocol: daemon writes temp file, returns `{"path": "...", "size": N}`
- CLI binary delivery: `-o` flag moves temp to target; stdout mode reads+writes+deletes; TTY protection
- VFS route table: new `leaf_bin` routes for textures, buffers, draw targets
- VFS tree cache: `/textures/` and `/buffers/` populated with actual resource lists; `/draws/<eid>/targets/` subtree
- Daemon handlers: `tex_info`, `tex_export`, `tex_raw`, `buf_info`, `buf_raw`, `rt_export`, `rt_depth`
- CLI convenience commands: `rdc texture`, `rdc rt`, `rdc buffer`

### Out of scope (later phases)

- `rdc mesh` (vertex/index buffer decode + ASCII preview)
- `rdc pixel` (single-pixel readback)
- Slice/format selection on texture export (hardcoded slice0, PNG)
- Streaming binary over JSON-RPC (always temp file)
- `/by-marker/` hierarchy population

## Architecture

### Temp directory lifecycle

```
daemon start (_load_replay)
  └─ mkdir /tmp/rdc-<token[:8]>/
      ├─ tex_export writes here: tex_<id>.png
      ├─ tex_raw writes here: tex_<id>.raw
      ├─ buf_raw writes here: buf_<id>.bin
      ├─ rt_export writes here: rt_<eid>_color<n>.png
      └─ rt_depth writes here: rt_<eid>_depth.png

shutdown / rdc close
  └─ shutil.rmtree(temp_dir, ignore_errors=True)
```

`DaemonState` gains a `temp_dir: Path | None` field set during `_load_replay()`.

### Binary transport protocol

All `leaf_bin` handlers return:

```json
{"path": "/tmp/rdc-a1b2c3d4/tex_42.png", "size": 1048576}
```

The CLI `cat` flow for `leaf_bin` nodes:

1. If `sys.stdout.isatty()` and not `--raw`: print error with redirect hint, exit 1 (no handler call)
2. Call handler RPC, receive `{"path", "size"}`
3. If `-o <file>`: `shutil.move(path, file)` (zero-copy rename on same fs)
4. Else (piped stdout): read temp file, write to `sys.stdout.buffer`, delete temp

### New VFS paths

| VFS path | kind | handler | Description |
|----------|------|---------|-------------|
| `/textures/<id>/info` | leaf | `tex_info` | Format, size, mips, array size |
| `/textures/<id>/image.png` | leaf_bin | `tex_export` | SaveTexture mip0 slice0 PNG |
| `/textures/<id>/mips/<n>.png` | leaf_bin | `tex_export` | SaveTexture mip=n slice0 PNG |
| `/textures/<id>/data` | leaf_bin | `tex_raw` | GetTextureData raw bytes |
| `/buffers/<id>/info` | leaf | `buf_info` | Size, usage flags |
| `/buffers/<id>/data` | leaf_bin | `buf_raw` | GetBufferData raw bytes |
| `/draws/<eid>/targets/` | dir | - | List: color0.png, color1.png, ..., depth.png |
| `/draws/<eid>/targets/color0.png` | leaf_bin | `rt_export` | GetOutputTargets[0] -> SaveTexture |
| `/draws/<eid>/targets/depth.png` | leaf_bin | `rt_depth` | GetDepthTarget -> SaveTexture |

### Route table additions (`router.py`)

```python
# textures
_r(r"/textures/(?P<id>\d+)", "dir", None, [("id", int)])
_r(r"/textures/(?P<id>\d+)/info", "leaf", "tex_info", [("id", int)])
_r(r"/textures/(?P<id>\d+)/image\.png", "leaf_bin", "tex_export", [("id", int)])
_r(r"/textures/(?P<id>\d+)/mips", "dir", None, [("id", int)])
_r(r"/textures/(?P<id>\d+)/mips/(?P<mip>\d+)\.png", "leaf_bin", "tex_export", [("id", int), ("mip", int)])
_r(r"/textures/(?P<id>\d+)/data", "leaf_bin", "tex_raw", [("id", int)])

# buffers
_r(r"/buffers/(?P<id>\d+)", "dir", None, [("id", int)])
_r(r"/buffers/(?P<id>\d+)/info", "leaf", "buf_info", [("id", int)])
_r(r"/buffers/(?P<id>\d+)/data", "leaf_bin", "buf_raw", [("id", int)])

# draw targets
_r(r"/draws/(?P<eid>\d+)/targets", "dir", None, [("eid", int)])
_r(r"/draws/(?P<eid>\d+)/targets/color(?P<target>\d+)\.png", "leaf_bin", "rt_export",
   [("eid", int), ("target", int)])
_r(r"/draws/(?P<eid>\d+)/targets/depth\.png", "leaf_bin", "rt_depth", [("eid", int)])
```

### Tree cache expansion (`tree_cache.py`)

**Static skeleton changes:**

- `/textures/` children populated from resources filtered by type (textures have
  `TextureResource` type or dimensionality > 0)
- `/buffers/` children populated from resources filtered by type (buffers have
  `BufferResource` type or byte size > 0 with no dimensionality)
- Each `/textures/<id>/` gets children `["info", "image.png", "mips", "data"]`
- Each `/textures/<id>/mips/` children populated from resource mip count: `["0.png", "1.png", ...]`
- Each `/buffers/<id>/` gets children `["info", "data"]`

**Dynamic draw subtree expansion (`populate_draw_subtree`):**

- Add `targets` to `_DRAW_CHILDREN`
- Populate `/draws/<eid>/targets/` children dynamically:
  - `SetFrameEvent(eid)` -> `GetOutputTargets()` -> one `colorN.png` per non-null target
  - `GetDepthTarget()` -> `depth.png` if non-null

### New daemon handlers (`daemon_server.py`)

**`tex_info(id)`**
- Lookup resource by ID via `adapter.get_resources()`
- Return `{id, name, format, width, height, depth, mips, array_size}`

**`tex_export(id, mip=0)`**
- `controller.SaveTexture(texsave, path)` where `texsave` configures mip=mip, slice=0, PNG
- `image.png` route passes mip=0 (default); `/mips/<n>.png` passes mip=n
- Return `{"path": temp_path, "size": file_size}`

**`tex_raw(id)`**
- `controller.GetTextureData(resource_id, sub)` -> write bytes to temp file
- Return `{"path": temp_path, "size": file_size}`

**`buf_info(id)`**
- Lookup buffer resource by ID
- Return `{id, name, size, usage}`

**`buf_raw(id)`**
- `controller.GetBufferData(resource_id, offset=0, length=0)` -> write to temp file
- Return `{"path": temp_path, "size": file_size}`

**`rt_export(eid, target)`**
- `SetFrameEvent(eid)` -> `pipe.GetOutputTargets()[target]` -> `SaveTexture` to temp
- Return `{"path": temp_path, "size": file_size}`

**`rt_depth(eid)`**
- `SetFrameEvent(eid)` -> `pipe.GetDepthTarget()` -> `SaveTexture` to temp
- Return `{"path": temp_path, "size": file_size}`

### CLI changes

**`cat_cmd` (`src/rdc/commands/vfs.py`)**

- After resolving path and getting kind, if `kind == "leaf_bin"`:
  - If `sys.stdout.isatty()` and not `--raw`: error with redirect hint
  - Call handler RPC -> receive `{"path", "size"}`
  - If `-o <file>`: `shutil.move(path, file)`
  - Else: read temp file -> `sys.stdout.buffer.write()` -> delete temp

Add `-o` / `--output` option to `cat_cmd`.

**New file: `src/rdc/commands/export.py`**

Three convenience commands that construct VFS paths and delegate to cat logic:

```python
@click.command("texture")
@click.argument("id", type=int)
@click.option("-o", "--output", type=click.Path())
@click.option("--mip", default=0, type=int, help="Mip level (default 0)")
def texture_cmd(id, output, mip): ...
    # mip=0 -> cat /textures/<id>/image.png [-o output]
    # mip>0 -> cat /textures/<id>/mips/<mip>.png [-o output]

@click.command("rt")
@click.argument("eid", type=int, required=False)
@click.option("-o", "--output", type=click.Path())
@click.option("--target", default=0, type=int)
def rt_cmd(eid, output, target): ...
    # -> cat /draws/<eid>/targets/color<target>.png [-o output]

@click.command("buffer")
@click.argument("id", type=int)
@click.option("-o", "--output", type=click.Path())
def buffer_cmd(id, output): ...
    # -> cat /buffers/<id>/data [-o output]
```

### Error handling

| Condition | Exit code | Message |
|-----------|-----------|---------|
| `cat` leaf_bin on TTY | 1 | `error: <path>: binary data, use redirect (>) or -o` |
| Mip index out of range | 1 | `error: mip <n> out of range (max: <max>)` |
| Resource ID not found | 1 | `error: resource <id> not found` |
| No output targets at eid | 1 | `error: no color targets at eid <eid>` |
| No depth target at eid | 1 | `error: no depth target at eid <eid>` |
| Target index out of range | 1 | `error: target index <n> out of range` |
| SaveTexture fails | 1 | `error: SaveTexture failed` |
| Temp dir missing | 1 | `error: temp directory not available` |

## Files changed

### New files
- `src/rdc/commands/export.py`
- `tests/unit/test_vfs_binary.py`
- `tests/unit/test_export_commands.py`
- `tests/unit/test_binary_daemon.py`

### Modified files
- `src/rdc/vfs/router.py` — new `leaf_bin` route entries
- `src/rdc/vfs/tree_cache.py` — texture/buffer children, draw targets subtree
- `src/rdc/commands/vfs.py` — `cat_cmd` binary handling, `-o` flag
- `src/rdc/daemon_server.py` — temp dir lifecycle, 7 new handlers, `DaemonState.temp_dir`
- `src/rdc/adapter.py` — `save_texture()`, `get_texture_data()`, `get_buffer_data()` wrappers (optional)
- `src/rdc/cli.py` — register `texture`, `rt`, `buffer` commands
- `tests/mocks/mock_renderdoc.py` — mock `SaveTexture`, `GetTextureData`, `GetBufferData`, `GetOutputTargets`, `GetDepthTarget`
