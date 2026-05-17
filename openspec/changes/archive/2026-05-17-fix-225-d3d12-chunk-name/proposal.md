# Fix #225 (fix-forward): D3D12 Chunk Name, Depth, and Exact-ID Matching

## Summary

PR #226 (squash 3735f2b) shipped the D3D12 adapter-matching logic but the
structured-data guard never fires on real hardware. Hardware verification by
issue reporter @YunHsiao (renderdoc 1.42, Windows multi-GPU D3D12 box) confirmed
that the user-facing crash is resolved by the vendor-priority fallback introduced
in #226, but the structured-data path — the primary, deterministic signal — is
silently skipped on every real capture. Three distinct defects prevent it from
working. This change is a fix-forward on the merged commit; issue #225 remains
open until hardware re-verification passes.

## Problem

### Canonical dump (ground truth)

Reporter provided the structured-data tree from renderdoc 1.42's bundled Python
module on a real D3D12 capture. The ONLY chunk carrying adapter identity is
`chunk[0]`, whose name is literally:

```
Internal::Driver Initialisation Parameters
```

Its subtree:

```
Internal::Driver Initialisation Parameters [Chunk] children=1
  InitParams [D3D12InitParams] children=7
    MinimumFeatureLevel [D3D_FEATURE_LEVEL]
    AdapterDesc [DXGI_ADAPTER_DESC] children=9
      Description           [string]  = 'NVIDIA RTX 4500 Ada Generation'
      VendorId              [uint32_t]
      DeviceId              [uint32_t]
      SubSysId              [uint32_t]
      Revision              [uint32_t]
      DedicatedVideoMemory  [uint64_t]
      DedicatedSystemMemory [uint64_t]
      SharedSystemMemory    [uint64_t]
      AdapterLuid           [LUID]
    usedDXIL, VendorExtensions, VendorUAV, VendorUAVSpace, SDKVersion
```

All remaining chunks are `ID3D12Device::*` / `ID3D12Resource::SetName` API calls
and 4834× `Internal::Initial Contents`. There is no `EnumAdapters`, no
`CreateDXGIFactory`, no `DriverInit` chunk anywhere in the capture.

Available GPUs on reporter's machine:
- `AMD Radeon(TM) Graphics` vendor=2 deviceID=5056
- `NVIDIA RTX 4500 Ada Generation` vendor=6 deviceID=10161
- `WARP Rasterizer` vendor=9 deviceID=0

### Defect 1 — outer chunk guard never matches

`d3d_markers = ("DriverInit", "EnumAdapters", "CreateDXGIFactory")`

None of the three substrings occur in `"Internal::Driver Initialisation Parameters"`.
The space between "Driver" and "Initialisation" defeats `"DriverInit"`. The guard
falls through on every chunk and `_find_adapter_description` is never called.

### Defect 2 — `_find_adapter_description` only walks 2 levels

The real `Description` field is at depth 3 relative to the chunk root:

```
chunk (depth 0)
  InitParams (depth 1)
    AdapterDesc (depth 2)
      Description (depth 3)  ← required
```

The current walker checks direct children (depth 1) for `Description`/`DeviceName`
and direct children of `AdapterDesc`/`pAdapter`/`adapter` (depth 2 for the
container, depth 3 only if the container is at depth 1). Because `AdapterDesc` is
at depth 2 (a grandchild), the current inner loop is never reached.

### Defect 3 — name-substring match is fragile for same-vendor multi-GPU

The name-substring comparison `desc_l in name_l or name_l in desc_l` is the
only disambiguation signal once a Description is found. On a system with two
NVIDIA cards whose names differ only by suffix, substring matching can produce a
false-positive match. The `AdapterDesc` already exposes `DeviceId` (PCI Device
ID, uint32) and `VendorId` (PCI Vendor ID, uint32). The reporter explicitly
recommended hardening to exact numeric match.

`GPUDevice.deviceID` in the renderdoc Python API carries the PCI Device ID, which
is what `DXGI_ADAPTER_DESC.DeviceId` encodes. An exact `DeviceId` match is
unambiguous and free of string-normalization risk.

## Design

### Part 1 — extend chunk name markers

Add `"Driver Initialisation Parameters"` to `d3d_markers`. Retain the three
existing substrings (`"DriverInit"`, `"EnumAdapters"`, `"CreateDXGIFactory"`) for
compatibility with other renderdoc versions or API paths that may use them.

```python
d3d_markers = (
    "Driver Initialisation Parameters",  # renderdoc 1.42 D3D12
    "DriverInit",
    "EnumAdapters",
    "CreateDXGIFactory",
)
```

### Part 2 — bounded recursive descent in `_find_adapter_description`

Replace the 2-level manual walk with a depth-bounded recursive descent (cap at
depth 4 or 5). At each node:

1. If the node name is `Description` or `DeviceName`, return its string value and
   a paired `DeviceId` if available at the same level.
2. If the node name is `AdapterDesc`, `pAdapter`, or `adapter`, recurse into it
   with depth decremented — this finds `Description` at depth 3 regardless of
   intermediate wrapper levels.
3. Otherwise recurse into all children with depth decremented.

Return type changes to a small named tuple carrying
`(description, device_id)` so the caller can use the numeric `DeviceId` for the
primary match. `VendorId` is deliberately NOT parsed (see Risks — it cannot be
compared against the renderdoc `GPUVendor` enum, so carrying it would be dead).

`DeviceId` is a `uint32_t` structured-data scalar. The renderdoc `SDObject`
interface used everywhere else in this code reads strings via `AsString()`; the
integer-valued counterpart is `AsInt()` (there is no `AsUInt()` on `SDObject`).
The implementation MUST read `DeviceId` via `child.AsInt()`, consistent with the
existing `AsString()` usage on the same interface. There is no top-level integer
`.data` attribute to read directly.

### Part 3 — exact numeric DeviceId match as primary signal

In `_match_capture_gpu`, after obtaining the result from
`_find_adapter_description`, apply a three-tier selection:

1. **Primary**: exact `DeviceId` match — `match.device_id == g.deviceID` for
   each GPU `g`. The first matching GPU wins. A `DeviceId` of `0` is treated as
   a software/WARP sentinel (software, WARP and virtualized adapters report
   `DXGI_ADAPTER_DESC.DeviceId == 0`): the tier-1 gate is truthiness, not
   `is not None`, so a present-but-zero id falls through to tier 2; and any
   candidate GPU whose `deviceID == 0` is skipped inside the exact-match loop so
   a real non-zero parsed id can never coincidentally bind the WARP adapter.
2. **Secondary**: name-substring match (existing logic) — used when no GPU's
   `deviceID` matches the parsed value, when `DeviceId` is absent, or when the
   parsed `DeviceId` is the `0` sentinel.
3. **Tertiary**: vendor-priority fallback (existing logic, unchanged).

### Known limitations / risks

**Why VendorId is not parsed.** `DXGI_ADAPTER_DESC.VendorId` is the raw PCI
vendor ID (e.g., NVIDIA = 0x10DE = 4318). The renderdoc `GPUVendor` enum uses
ordinals (nVidia = 6). These values are in unrelated spaces, so `VendorId`
cannot be compared against `g.vendor` and there is no other consumer for it.
The field is therefore deliberately NOT read from the chunk (carrying it would
be dead state). `DeviceId` → `g.deviceID` is the only exact key used.

**(RISK-A) `deviceID` vs PCI `DeviceId` same-space assumption.** Tier-1 assumes
the renderdoc `GPUDevice.deviceID` is the same integer as the PCI
`DXGI_ADAPTER_DESC.DeviceId`. This holds on the D3D12 path per the reporter
dump but is unverifiable on Linux/Vulkan from this repo. A mismatch silently
demotes tier-1 to name-substring (correctness preserved, determinism lost).
*Reporter verification question:* "On the #225 capture, print
`GetAvailableGPUs()[i].deviceID` for the NVIDIA RTX 4500 entry AND
`AdapterDesc.DeviceId` parsed from the same capture; confirm they are
bitwise-equal (expected 10161)."

**(RISK-B) Chunk-name version pinning.** The substring
`"Driver Initialisation Parameters"` is renderdoc-1.42-specific (British
spelling). A future renderdoc renaming it makes the guard miss every chunk and
silently reverts to vendor-priority — exactly the #225 failure class. Mitigated
by the new FIX-3 diagnostic `_log.warning` ("no recognized adapter chunk … —
renderdoc version may have changed chunk naming") which fires only on the
multi-GPU + structured-data + no-marker-chunk path, making the regression
loud and diagnosable instead of silent. *Reporter verification question:* "After
a renderdoc upgrade, if multi-GPU replay picks the wrong card, grep the daemon
log for `renderdoc version may have changed chunk naming`; its presence confirms
the chunk was renamed and the new name must be added to `d3d_markers`."

**Bounded-recursion depth.** A depth cap of 4 is sufficient for the observed tree
(Description at depth 3). Setting the cap to 5 provides one level of headroom.
Setting it higher risks traversing large subtrees (4834× `Initial Contents` chunks
are siblings at the top level, not descendants, so they are not a concern; the
guard in Part 1 prevents entering them).

**Chunk-name variance across renderdoc versions.** The real chunk name contains
"Initialisation" (British spelling). Future renderdoc versions may rename it.
Adding the new marker as an additional entry (not replacing the old ones) hedges
against this. If the chunk name is ever confirmed to differ, the new entry should
be updated in a follow-up.

**`GPUDevice` field names.** The field names `g.deviceID` and `g.name` are
inferred from the existing code and the reported dump. The implementer must
confirm these names against the bundled `renderdoc.pyi` or equivalent before
finalising the implementation.

## Spec Delta

The existing scenario "Multi-GPU capture replay" under **Requirement: Replay
lifecycle** in `openspec/specs/daemon/spec.md` (added by #226) requires the
following amendment:

The target scenario in `openspec/specs/daemon/spec.md` (HEAD lines 38–45) uses
bold `**WHEN**` / `**AND**` / `**THEN**` markers. The delta below reproduces
those bytes verbatim so it applies cleanly:

```diff
 #### Scenario: Multi-GPU capture replay
 - **WHEN** the capture was taken on a multi-GPU system
 - **AND** multiple GPUs are available for replay
-- **THEN** the daemon selects the GPU whose name matches structured-data adapter
-  metadata extracted from the capture
+- **THEN** the daemon walks structured-data chunks whose name contains any of
+  "Driver Initialisation Parameters", "DriverInit", "EnumAdapters", or
+  "CreateDXGIFactory"
+- **AND** within each such chunk descends recursively (depth ≤ 5) to locate an
+  AdapterDesc/pAdapter/adapter subtree
+- **AND** selects the GPU whose PCI DeviceId exactly matches
+  DXGI_ADAPTER_DESC.DeviceId when that field is present
+- **AND** falls back to case-insensitive name-substring match when no exact
+  DeviceId match is found
 - **AND** if no structured-data match exists, Software/WARP adapters are excluded
   and the highest-ranked discrete GPU is preferred (nVidia > AMD > Intel)
 - **AND** a single available GPU is always returned directly without inspection
```

This delta has been applied verbatim to `openspec/specs/daemon/spec.md` as
part of this change.

## Files Changed

- `src/rdc/daemon_server.py` — `d3d_markers` tuple; `_find_adapter_description`
  return type and walk algorithm; `_match_capture_gpu` selection logic
- `openspec/specs/daemon/spec.md` — scenario amendment (see Spec Delta above)
- `tests/unit/test_daemon_server_unit.py` — new unit tests (see `test-plan.md`)
