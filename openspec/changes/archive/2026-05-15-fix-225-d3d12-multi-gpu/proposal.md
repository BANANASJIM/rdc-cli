# Fix #225: D3D12 Multi-GPU Capture Replay

## Summary

Fix `_match_capture_gpu()` incorrectly returning the integrated GPU on multi-GPU
systems when replaying D3D12 captures, causing an `E_INVALIDARG` heap failure on
devices with insufficient VRAM.

## Motivation

`_match_capture_gpu()` only matches GPUs via the Vulkan `vkEnumeratePhysicalDevices`
structured-data chunk. For D3D12 captures that chunk is absent, so the function
falls through to `return gpus[0]`. On reporter's machine the GPU enumeration order
was: AMD Radeon Graphics iGPU 2 GB, NVIDIA RTX 4500 Ada 24 GB, WARP. The iGPU was
selected, D3D12 heap creation required more VRAM than available, and renderdoc
returned `E_INVALIDARG`.

The same fall-through also affects the remote-replay call site at line 368, which
additionally never passes `sd` to the helper, so even the Vulkan path was silently
bypassed on every remote replay.

## Design

### 1. D3D12 structured-data matching

Walk the capture's structured data looking for chunks whose name contains
`DriverInit`, `EnumAdapters`, or `CreateDXGIFactory`. Inside each matching chunk
descend into child objects to find a child named `AdapterDesc` and within it a
string field named `Description` or `DeviceName`. Perform a case-insensitive
substring match of that string against `gpu.name`. Return the first GPU that
matches.

### 2. Vendor-preference fallback

When no structured-data chunk produces a match, filter out Software/WARP adapters
(`renderdoc.GPUVendor.Software`), then rank remaining GPUs by vendor:
nVidia > AMD > Intel. Return the highest-ranked GPU, or the first non-Software GPU
if no ranked match exists.

### 3. Single-GPU short-circuit

If `len(gpus) == 1` return that GPU immediately without inspecting structured data.

### 4. Signature and call-site corrections

Pass `rd` (the renderdoc module) into `_match_capture_gpu()` so that
`GPUVendor` enum values are accessible without a module-level import assumption.
Update the remote-replay call site (line 368) to pass `sd` in addition to `rd`,
matching the local-replay call site.

## Spec Delta

A new scenario "Multi-GPU capture replay" should be appended under the existing
**Requirement: Replay lifecycle** section in `openspec/specs/daemon/spec.md`:

```
#### Scenario: Multi-GPU capture replay
- WHEN the capture was taken on a multi-GPU system
- AND multiple GPUs are available for replay
- THEN the daemon selects the GPU whose name matches structured-data adapter
  metadata extracted from the capture
- AND if no structured-data match exists, Software/WARP adapters are excluded
  and the highest-ranked discrete GPU is preferred (nVidia > AMD > Intel)
- AND a single available GPU is always returned directly without inspection
```

This proposal targets that scenario. The spec file itself is not modified here;
the delta is applied in the implementing task (see `tasks.md`).

## Files Changed

- `src/rdc/daemon_server.py` — `_match_capture_gpu` body; call sites at lines 223
  and 368
- `tests/unit/test_daemon_server_unit.py` — new unit tests (see `test-plan.md`)

## Risks

- The exact D3D12 chunk name (`DriverInit` / `EnumAdapters` / `CreateDXGIFactory`)
  has not been confirmed against a real renderdoc 1.42 D3D12 capture. The matching
  uses substring search rather than exact equality as a defensive measure; a real
  capture should be obtained from the issue reporter for verification before merge.
- `renderdoc.GPUVendor.nVidia` uses a lower-case `n`. Attribute access should use
  `getattr(rd.GPUVendor, "nVidia", 4)` with an integer fallback to avoid
  `AttributeError` on builds where the spelling differs.
- The Vulkan low-VRAM edge case (structured-data match returns a GPU that has less
  VRAM than required) is not addressed here; the fix only corrects selection
  behaviour and does not validate VRAM sufficiency.
- Integration testing on Linux is not possible without Windows D3D12 multi-GPU
  hardware. The unit tests use mocks. Full verification must be performed by the
  issue reporter on their machine.
