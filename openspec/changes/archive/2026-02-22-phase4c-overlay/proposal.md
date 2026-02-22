# Phase 4C-2: Overlay Rendering

## Goal

Add debug overlay rendering to `rdc rt`: render a capture's color target with a
RenderDoc debug overlay (wireframe, depth, overdraw, etc.) and save it as PNG.

## Scope

### New Daemon Method: `rt_overlay`

**Handler**: `_handle_rt_overlay` in `src/rdc/handlers/texture.py`

**Params**: `{eid?, overlay, width?, height?}`
- `eid`: event id (default `state.current_eid`)
- `overlay`: string key from `_OVERLAY_MAP` (required)
- `width` / `height`: headless window dimensions (default 256)

**Logic**:
1. Validate `overlay` against `_OVERLAY_MAP`; return -32602 on unknown name
2. Resolve `eid`; call `_set_frame_event`
3. Get `pipe.GetOutputTargets()`; find first non-null `.resource`; return -32001 if none
4. If `state.replay_output` is `None`, create it:
   - `rd.CreateHeadlessWindowingData(width, height)` → `windowing`
   - `controller.CreateOutput(windowing, rd.ReplayOutputType.Texture)` → stored in `state.replay_output`
5. Build `rd.TextureDisplay()`: set `.resourceId = target_rid`, `.overlay = _OVERLAY_MAP[overlay]`
6. `output.SetTextureDisplay(display)` + `output.Display()`
7. `overlay_rid = output.GetDebugOverlayTexID()`; return -32002 if zero
8. Build `TextureSave` for `overlay_rid`; call `controller.SaveTexture(texsave, path)`
9. Return `{path, size, overlay, eid, width, height}`

**Overlay name map**:
```python
_OVERLAY_MAP: dict[str, Any] = {
    "wireframe":     rd.DebugOverlay.Wireframe,
    "depth":         rd.DebugOverlay.Depth,
    "stencil":       rd.DebugOverlay.Stencil,
    "backface":      rd.DebugOverlay.BackfaceCull,
    "viewport":      rd.DebugOverlay.ViewportScissor,
    "nan":           rd.DebugOverlay.NaN,
    "clipping":      rd.DebugOverlay.Clipping,
    "overdraw":      rd.DebugOverlay.QuadOverdrawDraw,
    "triangle-size": rd.DebugOverlay.TriangleSizeDraw,
}
```

**Error codes**:
| Code | Condition |
|------|-----------|
| -32002 | no adapter / rd module / temp_dir / overlay tex ID zero |
| -32001 | no color output targets at eid |
| -32602 | unknown overlay name |

### CLI: Extend `rdc rt` in `src/rdc/commands/export.py`

Add `--overlay`, `--width`, `--height` options. When `--overlay` is given the
command calls the `rt_overlay` daemon method and delivers the resulting PNG
(to `-o FILE` or stdout). The existing VFS code path is untouched.

```
rdc rt EID --overlay <name> [-o FILE] [--width W] [--height H]
rdc rt EID [-o FILE] [--target N] [--raw]        # existing, unchanged
```

Implementation sketch inside `rt_cmd`:
```python
if overlay:
    result = _daemon_call("rt_overlay", {"eid": eid, "overlay": overlay,
                                          "width": width, "height": height})
    _deliver_binary_from_path(result["path"], output)
    return
# existing VFS path below
```

`_deliver_binary_from_path` reads the temp file and writes to `-o` or streams
to stdout (reuse existing `_deliver_binary` helper pattern).

### DaemonState Addition

```python
replay_output: Any = None  # cached ReplayOutput; shut down on session exit
```

Shutdown: add to the core `shutdown` handler in `src/rdc/handlers/core.py`
(where `adapter.controller` is already closed):
```python
if state.replay_output is not None:
    state.replay_output.Shutdown()
    state.replay_output = None
```

### Registration

- `texture.py` `HANDLERS` dict: add `"rt_overlay": _handle_rt_overlay`
- `daemon_server.py` `DaemonState`: add `replay_output: Any = None`
- `core.py` shutdown handler: call `state.replay_output.Shutdown()` if set

### Files Changed

| File | Change |
|------|--------|
| `src/rdc/handlers/texture.py` | Add `_OVERLAY_MAP`, `_handle_rt_overlay`, register in `HANDLERS` |
| `src/rdc/commands/export.py` | Extend `rt_cmd` with `--overlay`, `--width`, `--height` |
| `src/rdc/daemon_server.py` | Add `replay_output: Any = None` to `DaemonState` |
| `src/rdc/handlers/core.py` | Shutdown cleanup for `replay_output` |
| `tests/mocks/mock_renderdoc.py` | Add `MockReplayOutput`, `MockTextureDisplay`, `MockHeadlessWindowingData` |
| `tests/unit/test_overlay_handler.py` | Handler unit tests (NEW) |
| `tests/unit/test_export_overlay.py` | CLI unit tests (NEW) |
| `tests/integration/test_daemon_handlers_real.py` | GPU integration tests |

## Method Count Impact

After 4C-2: **72 methods**, **51 commands** (`rt` extended, not a new command)
