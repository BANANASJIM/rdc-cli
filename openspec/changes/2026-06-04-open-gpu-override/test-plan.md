# Test Plan: `--gpu` override for `rdc open`

## Unit (mocked — no GPU required)

`tests/unit/test_daemon_server_unit.py` (`TestMatchCaptureGpu`):

1. **Index** — `pref="1"` returns the second GPU.
2. **Name substring** — `pref="7800 xt"` matches case-insensitively.
3. **Device ID** — `pref="29822"` (decimal) and `pref="0x747e"` (hex) both match
   `deviceID==29822`.
4. **Precedence** — with a Vulkan `deviceName` chunk that would auto-match GPU B,
   `pref="AMD"` still selects GPU A.
5. **No match** — `pref="Matrox"` logs a `--gpu` warning and falls back to the
   vendor-priority auto-selection.
6. **`_resolve_gpu_pref`** — index / name / hex resolve; unknown and empty → None.

`tests/unit/test_session_service.py`:

7. `start_daemon(gpu="1")` puts `--gpu 1` in the daemon argv; default omits `--gpu`.

`tests/unit/test_session_commands.py`:

8. `rdc open CAP --gpu 1` forwards `gpu="1"` to `start_daemon`.
9. `rdc open --connect host:port --token T --gpu 1` prints
   `warning: --gpu is ignored with --connect`.

Run: `pixi run test` (unit only; no GPU/e2e). Full gate: `pixi run check`.

## Manual (requires a multi-GPU host + renderdoc)

- `rdc open frame.rdc --gpu <discrete-name>` then `rdc status` / a replay query;
  daemon log shows `replay GPU (user --gpu=...)`.
- `rdc open frame.rdc --gpu nonsense` logs the no-match warning and still opens
  via auto-selection.

(Not run in CI: needs real hardware; out of scope for the unit suite.)
