# Add `--gpu` override to `rdc open`

## Problem

When a capture is replayed, the daemon picks the replay GPU automatically via
`_match_capture_gpu()`: it matches the capture's recorded device name (Vulkan)
or adapter description / DeviceId (D3D12), and **falls back to vendor priority
(nVidia > AMD > Intel)** when nothing matches.

On a multi-GPU host that fallback is `filtered[0]` after a stable sort, i.e. the
first-enumerated device of the highest-priority vendor — frequently the
integrated GPU. There is no way for the user to override it:

- `rdc open` exposes no GPU selection flag.
- The fallback cannot be steered toward a discrete GPU, a specific device, or a
  GPU whose name does not match the capture's recorded name (common when
  replaying a capture taken on different hardware).

This complements the recent multi-GPU auto-matching work (#225) by giving the
analyst an explicit escape hatch when auto-selection picks the wrong device.

Note: an explicit GPU choice does not make a capture portable across
incompatible hardware (RADV descriptor layouts differ per GPU generation); it
only controls *which* available GPU replay is attempted on.

## Solution

Add an optional `--gpu INDEX|NAME|DEVICEID` flag to `rdc open` that forces the
replay GPU, overriding auto-selection.

Resolution order against `cap.GetAvailableGPUs()`:

1. **0-based index** — `--gpu 1` selects the second enumerated GPU.
2. **device ID** — decimal or `0x` hex (`--gpu 0x747e`), matched against
   `GPUDevice.deviceID`.
3. **name substring** — case-insensitive (`--gpu "7800 XT"`).

If the preference matches no available GPU, a warning is logged listing the
available GPUs and replay falls back to the existing auto-selection (non-fatal).

### Plumbing

The flag threads CLI → daemon, reusing the existing daemon-arg channel:

- `commands/session.py`: `--gpu` option on `open_cmd`; ignored (with a warning)
  for `--connect` (an external daemon is already running). Passed to
  `open_session` / `listen_open_session`.
- `services/session_service.py`: `start_daemon(..., gpu=...)` appends
  `--gpu <value>` to the daemon argv; `open_session` / `listen_open_session`
  forward it.
- `daemon_server.py`: `--gpu` arg → `DaemonState.gpu_pref`; `_match_capture_gpu`
  gains a `pref` parameter that short-circuits to the resolved GPU before
  auto-matching. Applied at both the local and remote replay call sites.

Out of scope: changing the default auto-selection (vendor priority is unchanged).

## Spec Delta

The existing scenario "Multi-GPU capture replay" under **Requirement: Replay
lifecycle** in `openspec/specs/daemon/spec.md` (added by #226, amended by #230)
is amended so the user `--gpu` preference takes precedence over auto-selection:

```diff
 #### Scenario: Multi-GPU capture replay
 - **WHEN** the capture was taken on a multi-GPU system
 - **AND** multiple GPUs are available for replay
-- **THEN** the daemon walks structured-data chunks whose name contains any of
+- **THEN** if the user passed `--gpu` (a 0-based index, a PCI device ID in
+  decimal or `0x` hex, or a case-insensitive name substring) that resolves to an
+  available GPU, that GPU is selected and structured-data inspection is skipped
+- **AND** otherwise the daemon walks structured-data chunks whose name contains any of
   "Driver Initialisation Parameters", "DriverInit", "EnumAdapters", or
   "CreateDXGIFactory"
 ...
 - **AND** if no structured-data match exists, Software/WARP adapters are excluded
   and the highest-ranked discrete GPU is preferred (nVidia > AMD > Intel)
+- **AND** an unresolved `--gpu` preference logs a warning and falls back to the
+  auto-selection above
 - **AND** a single available GPU is always returned directly without inspection
```

This delta has been applied to `openspec/specs/daemon/spec.md` as part of this
change.
