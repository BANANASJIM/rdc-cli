# Phase 4C-2: Overlay — Tasks

## Parallel Agent Split

Two worktree agents can work in parallel since they touch non-overlapping files:

### Agent 1: Mock + Handler + Handler Tests + GPU Tests
Files:
- `tests/mocks/mock_renderdoc.py` (modify: add overlay mock classes)
- `src/rdc/handlers/texture.py` (modify: add _handle_rt_overlay + register)
- `src/rdc/handlers/core.py` (modify: add replay_output shutdown cleanup)
- `src/rdc/daemon_server.py` (modify: add replay_output field + shutdown cleanup)
- `tests/unit/test_overlay_handler.py` (new)
- `tests/integration/test_daemon_handlers_real.py` (modify: add TestOverlayReal)

### Agent 2: CLI Extension + CLI Tests
Files:
- `src/rdc/commands/export.py` (modify: extend rt_cmd with --overlay)
- `tests/unit/test_export_overlay.py` (new)

## Task Checklist

### Mock Updates
- [ ] Add `DebugOverlay` IntEnum (15 values)
- [ ] Add `ReplayOutputType` IntEnum (Texture=1, Mesh=2)
- [ ] Add `TextureDisplay` dataclass
- [ ] Add `MockReplayOutput` class (SetTextureDisplay, Display, GetDebugOverlayTexID, ReadbackOutputTexture, Shutdown)
- [ ] Add `CreateHeadlessWindowingData` function
- [ ] Update `MockReplayController` with `CreateOutput` method

### Daemon Handler
- [ ] Add `_OVERLAY_MAP` dict (9 overlay names → enum values)
- [ ] Add `_handle_rt_overlay` handler
- [ ] Register `"rt_overlay"` in HANDLERS dict
- [ ] Add `replay_output` field to `DaemonState`
- [ ] Add cleanup in shutdown handler

### CLI Extension
- [ ] Add `--overlay` option to `rt_cmd` (Click.Choice from overlay names)
- [ ] Add `--width`/`--height` options
- [ ] Route to `rt_overlay` daemon method when `--overlay` is present
- [ ] Fallthrough to existing VFS behavior when `--overlay` is absent

### Tests
- [ ] 11 handler unit tests
- [ ] 6 CLI unit tests
- [ ] 3 GPU integration tests

## Verification

```bash
pixi run lint && pixi run test
RENDERDOC_PYTHON_PATH=... pixi run test-gpu -k "overlay" -v
```
