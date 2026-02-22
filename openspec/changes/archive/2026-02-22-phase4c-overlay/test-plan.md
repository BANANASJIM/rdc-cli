# Phase 4C-2: Overlay — Test Plan

## Handler Tests (`tests/unit/test_overlay_handler.py`)

Fixture pattern: `SimpleNamespace` controller with `CreateOutput`, `SetFrameEvent`, `GetAPIProperties`.
`MockReplayOutput` is set on `state.replay_output` for caching tests.
All tests call `_handle_request(_req("rt_overlay", ...), state)`.

### Happy path

**1. wireframe overlay**
- Call `rt_overlay` with `overlay="wireframe"`.
- Assert `result["path"]` present, `result["size"] > 0`, `result["overlay"] == "wireframe"`.

**2. depth overlay**
- Same as above with `overlay="depth"`.
- Assert result has expected fields.

**3. overdraw overlay**
- Same with `overlay="overdraw"`.

**4. custom dimensions forwarded**
- Call with `width=512, height=512`.
- Assert mock `CreateOutput` was called with those dimensions (capture via side-effect on controller).

**5. default eid uses `state.current_eid`**
- Set `state.current_eid = 10`, omit `eid` param.
- Assert `result["eid"] == 10`.

**6. cached `replay_output` reused**
- Pre-set `state.replay_output` to an existing `MockReplayOutput`.
- Assert `CreateOutput` on the controller is **not** called (cached path taken).

### Error cases

**7. invalid overlay name → -32602**
- Call with `overlay="invalid"`.
- Assert `resp["error"]["code"] == -32602`.

**8. no adapter → -32002**
- Use a bare `DaemonState` with `adapter=None`.
- Assert `resp["error"]["code"] == -32002`.

**9. no output targets at eid → -32001**
- Configure controller so `GetOutputTargets()` returns an empty list for the given eid.
- Assert `resp["error"]["code"] == -32001`.

**10. state.rd = None → -32002**
- Use a `DaemonState` with `rd=None`.
- Assert `resp["error"]["code"] == -32002`.

**11. state.temp_dir = None → -32002**
- Use a `DaemonState` with `temp_dir=None`.
- Assert `resp["error"]["code"] == -32002`.

---

## CLI Tests (`tests/unit/test_export_overlay.py`)

Pattern: `monkeypatch("rdc.commands.export._daemon_call", mock)`, `CliRunner`, invoke `rt_cmd`.

**1. `rt --overlay wireframe` calls `rt_overlay` daemon method**
- Capture calls list in mock.
- Assert one call with `method == "rt_overlay"` and `params["overlay"] == "wireframe"`.
- Assert exit code 0, output contains the returned path.

**2. `rt --overlay wireframe -o out.png` saves file**
- Mock returns a temp PNG path; command copies to `-o` destination.
- Assert `out.png` exists and contains PNG magic bytes.
- Assert stderr/stdout summary line present (e.g., "overlay wireframe").

**3. `rt --overlay wireframe --width 512 --height 512` forwards dimensions**
- Assert captured params include `width=512, height=512`.

**4. `rt` without `--overlay` falls through to VFS path (no regression)**
- Mock returns `vfs_ls` leaf_bin response.
- Assert `rt_overlay` method is **not** called; VFS path used as before.
- Assert exit code 0.

**5. `rt --overlay help` shows overlay choices**
- `runner.invoke(rt_cmd, ["--help"])`.
- Assert `--overlay` and at least `wireframe` present in output.

**6. `rt --overlay invalid` rejected by Click**
- Assert exit code != 0, `"Invalid value"` or `"invalid choice"` in output.

---

## GPU Integration Tests (`tests/integration/test_daemon_handlers_real.py`)

Add `class TestOverlayReal` following the `TestMeshDataReal` pattern.
Fixture: `autouse` `_setup` using `_make_state(vkcube_replay, rd_module)` + `tmp_path` for `state.temp_dir`.
Helper `_first_draw_eid()` via `_call(self.state, "draws")["draws"][0]["eid"]`.

**1. wireframe overlay produces a valid PNG**
- Call `rt_overlay` with `eid=draw_eid, overlay="wireframe"`.
- Assert `result["path"]` exists on disk, `result["size"] > 0`.
- Assert file starts with PNG magic bytes `b"\x89PNG"`.

**2. depth overlay produces a valid PNG**
- Same as above with `overlay="depth"`.
- Assert same file-existence and magic-bytes invariants.

**3. overlay PNG differs from plain `rt_export`**
- Export plain `rt_export` and `rt_overlay wireframe` for the same eid.
- Read both files; assert byte content is not identical (overlays visually differ from base RT).

---

## Mock Requirements (`tests/mocks/mock_renderdoc.py`)

| Addition | Details |
|---|---|
| `DebugOverlay` IntEnum | `NoOverlay=0, Drawcall=1, Wireframe=2, Depth=3, Stencil=4, BackfaceCull=5, ViewportScissor=6, NaN=7, Clipping=8, ClearBeforePass=9, ClearBeforeDraw=10, QuadOverdrawPass=11, QuadOverdrawDraw=12, TriangleSizePass=13, TriangleSizeDraw=14` |
| `ReplayOutputType` IntEnum | `Texture=1, Mesh=2` |
| `TextureDisplay` dataclass | Fields: `resourceId`, `overlay` (int), `rangeMin` (float=0.0), `rangeMax` (float=1.0), `scale` (float=1.0), `red/green/blue/alpha` (bool=True), `flipY` (bool=False), `hdrMultiplier` (float=1.0), `subresource` (any=None) |
| `MockReplayOutput` class | Methods: `SetTextureDisplay(td)`, `Display() -> bool`, `GetDebugOverlayTexID() -> ResourceId`, `ReadbackOutputTexture() -> bytes`, `Shutdown()` |
| `CreateHeadlessWindowingData(w, h)` | Free function returning a mock windowing object |
| `MockReplayController.CreateOutput(win, type)` | Returns a `MockReplayOutput`; used to populate `state.replay_output` |

`MockReplayOutput.ReadbackOutputTexture()` should return minimal valid PNG bytes (`b"\x89PNG\r\n\x1a\n" + b"\x00" * 8`) so size assertions pass without real image I/O.

---

## Coverage Target

All new handler and CLI code in `src/rdc/handlers/texture.py` and `src/rdc/commands/export.py` at **90%+ coverage**.
GPU tests are excluded from the coverage denominator (marked `gpu`, skipped in CI).
