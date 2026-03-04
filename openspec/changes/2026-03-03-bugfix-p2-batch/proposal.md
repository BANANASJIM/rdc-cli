# OpenSpec Proposal: P2 Bug Fix Batch (B75 + Remote Export + Daemon Survival)

## Motivation

Three P2 bugs affect correctness and reliability of core workflows:

1. **B75 — `rdc event` parameter values missing**: The event detail command returns empty strings for all numeric and boolean parameter values, making it useless for debugging draw calls. Root cause is that `SDObject.AsString()` in RenderDoc's SWIG binding only works for `String`/`Enum` basetypes; all other basetypes (UnsignedInteger, SignedInteger, Float, Boolean, Resource) return an empty string. The raw POD fields on `SDObjectPODData` must be read directly based on `basetype`.

2. **Remote Export silent failure**: `rdc tex export`, `rdc rt export`, `rdc rt depth`, and `rdc pick pixel` silently succeed (returning empty or zero data) when the daemon is running in remote/proxy mode, even though `SaveTexture()` and `PickPixel()` require a GPU-side replay controller that is not available in that mode. Users get no error, just garbage output.

3. **Daemon Survival on Windows SSH**: When a user connects via SSH on Windows and launches the daemon in background, the daemon process is killed when the SSH session disconnects. The `CREATE_NO_WINDOW` flag alone is not sufficient; the process must also be detached from the controlling terminal via `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS`.

## Design

### B75: `_extract_sd_value()` helper in `query.py`

Replace the `child.AsString()` call inside `_handle_event()` with a new private helper `_extract_sd_value(child)` that switches on `child.type.basetype`:

| basetype value | SDObject field | Python expression |
|---|---|---|
| 7 (UnsignedInteger) | `data.basic.u` | `str(child.data.basic.u)` |
| 8 (SignedInteger) | `data.basic.i` | `str(child.data.basic.i)` |
| 9 (Float) | `data.basic.d` | `str(child.data.basic.d)` |
| 10 (Boolean) | `data.basic.b` | `str(bool(child.data.basic.b))` |
| 12 (Resource) | `data.basic.id` | `str(int(child.data.basic.id))` |
| 5, 6 (String, Enum) | `AsString()` or `data.str` | `child.AsString()` |
| default | — | `child.AsString()` (last-resort fallback) |

The helper remains private (`_extract_sd_value`) and is only called from `_handle_event()`.

`SDBasicData` on the mock (`tests/mocks/mock_renderdoc.py`) must gain the fields `u`, `i`, `d`, `b`, `id` so unit tests can exercise all branches. `SDObject` in the mock must expose a `type` attribute with a `basetype` field matching the integer constants above.

### Remote Export: `is_remote` guard

Four handlers in `texture.py` and `pixel.py` that call GPU-only API must return an error before touching the replay controller when `state.is_remote` is true. The error message mirrors the existing pattern from `_handle_rt_overlay`:

```
"not supported in remote mode"
```

Affected handlers — guard goes as first statement in function body (before `rd is None` check), matching `_handle_rt_overlay` pattern:
- `_handle_tex_export` (texture.py ~line 65)
- `_handle_rt_export` (texture.py ~line 117)
- `_handle_rt_depth` (texture.py ~line 147)
- `_handle_pick_pixel` (pixel.py ~line 131)

No logic changes beyond the early return; existing `_handle_rt_overlay` guard is the canonical reference.

### Daemon Survival: Windows creation flags

In `src/rdc/_platform.py`, the `popen_flags()` function's Windows branch currently returns:

```python
{"creationflags": 0x08000000}  # CREATE_NO_WINDOW
```

Change to:

```python
{"creationflags": 0x00000200 | 0x00000008}
# CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
```

**Note**: `DETACHED_PROCESS` (0x8) and `CREATE_NO_WINDOW` (0x08000000) are mutually exclusive per Win32 docs — they cannot be ORed together. `DETACHED_PROCESS` is the stronger option: it completely detaches from the parent's console, ensuring the daemon survives SSH session teardown. `CREATE_NEW_PROCESS_GROUP` (0x200) provides signal isolation. The previous `CREATE_NO_WINDOW` is **replaced**, not added to. Unix behavior is unchanged.

## Risk Assessment

| Bug | Risk | Mitigation |
|---|---|---|
| B75 | Medium | `basetype` integer constants are part of RenderDoc's stable public API and have not changed across v1.x. The `AsString()` fallback ensures no regression for unknown future basetypes. Mock update keeps unit tests accurate. |
| Remote Export | Low | Pure early-return guards, no existing logic is altered. The pattern is already proven by `_handle_rt_overlay`. |
| Daemon Survival | Low | Only changes Windows `creationflags` bit mask. Existing Unix path is untouched. The three flags are stable Win32 constants that have existed since Windows XP. |
