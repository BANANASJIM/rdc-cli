# Fix #225 (fix-forward): Test Plan

## Test classification

Tests are split into two classes with different obligations:

- **Red-first defect proofs** — MUST fail when run against the current buggy
  `daemon_server.py` (pre-fix) and pass after the fix. Each states the exact
  failure mode against current code so the implementer can confirm redness
  before changing any source.
- **Regression guards** — green pre-fix; they pin behavior that already works
  so the new recursive walker / DeviceId selection does not regress it. They
  MUST NOT be presented as defect proofs.

All tests live in `tests/unit/test_daemon_server_unit.py`.

## Mock construction (real shape — verified against `tests/mocks/mock_renderdoc.py`)

Structured data is built from the real `mock_renderdoc` dataclasses, exactly as
existing tests do (see `_d3d12_sd` / `_vulkan_sd` helpers in the current file).
There is **no** `AsUInt()` and **no** top-level integer `.data`. Numeric scalars
flow through `SDBasic.value` and are read via `AsInt()`; strings via
`AsString()`. Both accessors live on the same `SDObject`.

String field:

```python
rd.SDObject(name="Description", data=rd.SDData(basic=rd.SDBasic(value="NVIDIA RTX 4500 Ada Generation")))
# .AsString() -> "NVIDIA RTX 4500 Ada Generation"
```

Numeric (uint32) field — `DeviceId` (the chunk also contains a `VendorId`
sibling, but it is deliberately NOT parsed by the implementation; see
`proposal.md` Risks — so tests do not build a `VendorId` child):

```python
rd.SDObject(name="DeviceId", data=rd.SDData(basic=rd.SDBasic(value=10161)))
# .AsInt() -> 10161
```

Canonical depth-3 tree from the reporter's dump (omitting the unused
`VendorId` node):

```python
desc   = rd.SDObject(name="Description", data=rd.SDData(basic=rd.SDBasic(value="NVIDIA RTX 4500 Ada Generation")))
devid  = rd.SDObject(name="DeviceId",    data=rd.SDData(basic=rd.SDBasic(value=10161)))
adapter = rd.SDObject(name="AdapterDesc", children=[desc, devid])
init    = rd.SDObject(name="InitParams",  children=[adapter])
chunk   = rd.SDChunk(name="Internal::Driver Initialisation Parameters", children=[init])
sd      = rd.StructuredFile(chunks=[chunk])
```

The implementation reads `DeviceId` via `child.AsInt()` (consistent with the
existing `AsString()` usage on the same `SDObject` interface). No accessor
hedging is needed — `AsInt()` is the confirmed real accessor.

GPU objects: the existing `_gpu(name, vendor)` helper hardcodes `deviceID=0`.
Tests that exercise DeviceId matching MUST construct GPUs with explicit,
distinct `deviceID` values (e.g. `SimpleNamespace(name=..., vendor=...,
deviceID=10161, driver="")`).

## Red-first defect proofs (MUST fail against current buggy code)

- [ ] `test_d3d12_chunk_guard_recognizes_real_chunk_name` — **isolates Defect 1
  independent of depth-3 resolution.** Build structured data with a single chunk
  named exactly `"Internal::Driver Initialisation Parameters"` whose
  `AdapterDesc.Description = "AMD Radeon RX 7900 XTX"` is a *direct child of the
  chunk* (depth-2 layout, no `InitParams` wrapper). Two GPUs, pinned exactly:
  1. `name="AMD Radeon RX 7900 XTX" vendor=2 deviceID=29772` — the GPU the
     chunk's Description identifies.
  2. `name="NVIDIA RTX 4500 Ada Generation" vendor=6 deviceID=10161`.

  Pass `rd=` as the mock module (it has **no** `GPUVendor` attribute, so the
  fallback uses the hardcoded defaults `nVidia=6, AMD=2, Intel=5, Software=9`
  and `priority = {6:0, 2:1, 5:2}`). Assert the AMD GPU (`deviceID=29772`) is
  returned. *Failure mode against current code:* `d3d_markers = ("DriverInit",
  "EnumAdapters", "CreateDXGIFactory")` — no substring occurs in `"Internal::
  Driver Initialisation Parameters"` (the space breaks `"DriverInit"`), so the
  guard never fires and `_find_adapter_description` is never called. The
  function falls to vendor-priority: `filtered` keeps both GPUs (neither is
  Software), `filtered.sort(key=priority.get(vendor, 99))` orders NVIDIA
  (vendor=6 → priority 0) before AMD (vendor=2 → priority 1), so current code
  returns **NVIDIA** — the WRONG GPU vs. the asserted AMD. The wrong-GPU
  pick (NVIDIA before AMD) is guaranteed by the priority map regardless of
  enumeration order, so this test is provably RED pre-fix and isolates the
  guard predicate: a marker-only fix makes the guard fire on the real chunk
  name, the depth-2 `AdapterDesc.Description` resolves under the existing inner
  loop, and AMD is returned. Provable separately from the depth-3 walker fix.

- [ ] `test_d3d12_chunk_guard_fires_on_real_name` — end-to-end on the real tree,
  redesigned so the vendor-priority fallback returns the WRONG GPU (only the
  guard + depth-3 walker + DeviceId fix yields the asserted one). Single chunk
  named `"Internal::Driver Initialisation Parameters"` with the full canonical
  depth-3 subtree `chunk → InitParams → AdapterDesc → {Description = "AMD Radeon
  RX 7900 XTX", DeviceId = 29772}`. Two GPUs, pinned exactly:
  1. `name="AMD Radeon RX 7900 XTX" vendor=2 deviceID=29772` — the card the
     capture's `AdapterDesc` identifies (by Description AND DeviceId).
  2. `name="NVIDIA RTX 4500 Ada Generation" vendor=6 deviceID=10161`.

  Pass `rd=` as the mock module (no `GPUVendor` attribute → defaults
  `nVidia=6, AMD=2, Intel=5, Software=9`, `priority = {6:0, 2:1, 5:2}`). Assert
  `_match_capture_gpu` returns the **AMD** GPU (`deviceID=29772`). *Failure mode
  against current code:* guard miss (Defect 1) — `"Internal::Driver
  Initialisation Parameters"` contains none of the markers — so
  `_find_adapter_description` is never called; even if the guard had matched,
  `_find_adapter_description` stops at depth 2 (Defect 2) and never reaches the
  depth-3 `AdapterDesc` under `InitParams`; and even if a name were extracted
  there is no DeviceId logic (Defect 3). The function falls to vendor-priority:
  both GPUs survive the Software filter, `filtered.sort` orders NVIDIA
  (vendor=6 → priority 0) before AMD (vendor=2 → priority 1), so current code
  returns **NVIDIA** — the WRONG card vs. the asserted AMD. The fallback's
  wrong pick is fixed by the priority map (NVIDIA strictly before AMD) and is
  independent of enumeration order, so the test is provably RED pre-fix. Only
  after all three fixes — marker added → guard fires on the real name; walker
  recurses to depth 3 → reaches `AdapterDesc`; exact `DeviceId=29772` matches
  GPU #1 — is the asserted AMD GPU returned.

- [ ] `test_find_adapter_description_depth3` — call `_find_adapter_description`
  directly with the canonical depth-3 object tree `chunk → InitParams →
  AdapterDesc → {Description, DeviceId=10161}`. Assert the returned value exposes
  `description == "NVIDIA RTX 4500 Ada Generation"` and `device_id == 10161`.
  *Failure mode against current code:* the current walker only inspects direct
  children of the chunk and direct children of an `AdapterDesc`/`pAdapter`/
  `adapter` *direct child*; here `AdapterDesc` is a grandchild (under
  `InitParams`), so the inner loop is never entered and the function returns
  `None` (and has no `device_id` field at all — current return type is `str |
  None`). Proves Defect 2.

- [ ] `test_exact_deviceid_wins_over_wrong_name` — chunk named exactly
  `"Internal::Driver Initialisation Parameters"` with the canonical depth-3
  subtree `chunk → InitParams → AdapterDesc → {Description = "NVIDIA RTX 4500",
  DeviceId = 10161}` (same chunk name and InitParams→AdapterDesc depth as the
  real reporter dump, so the implementer deterministically exercises the
  guard + depth-3 walker + DeviceId path). Two GPUs, same vendor, **wrong one
  placed first**: `name="NVIDIA RTX 4500 Ada Generation Laptop GPU" vendor=6
  deviceID=9999` then `name="NVIDIA RTX 4500 Ada Generation" vendor=6
  deviceID=10161`. Both names contain the substring `"NVIDIA RTX 4500"`. Pass
  `rd=` as the mock module. Assert the GPU with `deviceID=10161` is returned.
  *Failure mode against current code:* the guard misses the real chunk name
  (no marker substring), so `_find_adapter_description` and the substring loop
  never run; the function falls to vendor-priority. Both GPUs have vendor=6, so
  `priority.get(6)=0` for both and the stable `filtered.sort` preserves
  enumeration order, returning GPU #1 (`deviceID=9999`) — the WRONG card vs. the
  asserted `deviceID=10161`. (Independently, even with the guard fixed,
  pre-walker code would never reach the depth-3 `AdapterDesc`, and even with a
  name extracted there is no DeviceId logic and the substring loop `desc_l in
  name_l or name_l in desc_l` would still match the first GPU.) After the fix
  the guard fires, the walker reaches depth-3 `AdapterDesc`, and exact
  `DeviceId=10161` selects the second GPU. Proves Defect 3 (and is guarded
  against the guard/walker defects masking it). Note: both GPUs share vendor=6
  so the vendor-priority tertiary path cannot accidentally yield the asserted
  GPU — only the DeviceId fix can.

- [ ] `test_exact_deviceid_same_vendor_multi_gpu` — pinned for guaranteed
  redness. Chunk named exactly `"Internal::Driver Initialisation Parameters"`
  with the canonical depth-3 subtree `chunk → InitParams → AdapterDesc →
  {Description = "NVIDIA RTX A5000", DeviceId = 8888}` (same chunk name and
  InitParams→AdapterDesc depth as the real dump). Three GPUs, all vendor
  NVIDIA (vendor=6), in this order:
  1. `name="NVIDIA RTX A5000" deviceID=2204` — a *wrong* same-vendor GPU whose
     name is an exact substring match of the Description.
  2. `name="NVIDIA RTX A4000" deviceID=9999`.
  3. `name="NVIDIA RTX A6000" deviceID=8888` — the wanted GPU (DeviceId points
     here), placed last and whose name does NOT substring-match the Description.

  Pass `rd=` as the mock module. Assert the GPU with `deviceID=8888` (GPU #3,
  "RTX A6000") is returned. *Failure mode against current code:* the guard
  misses the real chunk name (no marker substring), so the substring loop never
  runs and the function falls to vendor-priority. All three GPUs have vendor=6,
  so `priority.get(6)=0` for all and the stable `filtered.sort` preserves
  enumeration order, returning GPU #1 (`deviceID=2204`) — the WRONG card vs. the
  asserted `deviceID=8888`. (Independently, even with guard + walker fixed but
  no DeviceId logic, the substring loop would hit GPU #1 — `"NVIDIA RTX A5000"`
  ⊆ Description — first and still return the wrong same-vendor card.) The wanted
  GPU is deliberately placed after a wrong same-vendor GPU whose name
  substring-matches the Description, so both pre-fix paths (fallback and, with
  partial fixes, substring) are guaranteed to return the wrong GPU, and only the
  fixed exact-DeviceId logic returns GPU #3. Same vendor across all three means
  vendor-priority can never accidentally yield the asserted GPU.

## Regression guards (green pre-fix; prevent regression)

- [ ] `test_d3d12_legacy_marker_path_unbroken` — **reworked legacy-marker
  guard; explicitly NOT a defect proof.** This is green pre-fix (it is the same
  path as the existing passing `test_d3d12_match_via_driverinit_adapterdesc`).
  Mock a chunk named `"DriverInit"` with a *direct* `AdapterDesc` child whose
  `Description = "Intel HD Graphics"`; one GPU named `"Intel HD Graphics"`.
  Assert that GPU is returned. Purpose: confirm the existing depth-1
  `AdapterDesc` legacy-marker path still resolves under the NEW recursive walker
  and that the retained markers (`"DriverInit"` etc.) are not dropped.

- [ ] `test_find_adapter_description_depth1_still_works` — `Description` is a
  direct child of the chunk (depth 1). Assert it is returned. Green pre-fix;
  guards shallow captures against the recursive rewrite.

- [ ] `test_find_adapter_description_depth2_adapter_child` — `AdapterDesc` is a
  direct child of the chunk and `Description` its child (depth 2). Assert the
  value is returned. Green pre-fix (this is the exact path the current code and
  existing tests already cover); guards the original depth-2 case.

- [ ] `test_name_substring_fallback_when_no_device_id` — chunk has a
  `Description` but no `DeviceId` child; two GPUs with distinct names (each with
  a concrete `deviceID`). Assert the GPU whose name substring-matches the
  Description is returned. Green pre-fix (substring path already works); guards
  the secondary signal when DeviceId is absent.

- [ ] `test_fallback_still_works_when_no_chunk` — `sd=None`; two GPUs: AMD
  (`vendor=2`) and NVIDIA (`vendor=6`). Assert NVIDIA is returned via
  vendor-priority fallback. Green pre-fix (#226 fallback); guards the tertiary
  path.

- [ ] `test_vulkan_path_unchanged` — chunk named
  `"vkEnumeratePhysicalDevices"` with `physProps.deviceName = "AMD RX 7900 XT"`;
  two GPUs. Assert the AMD GPU is returned. Green pre-fix; guards the Vulkan
  branch from D3D12 changes.

- [ ] `test_single_gpu_short_circuit` — `len(gpus) == 1`, no structured data.
  Assert that GPU is returned immediately without tree traversal. Green pre-fix;
  guards the single-GPU short-circuit from #226.

- [ ] `test_empty_gpu_list_returns_none` — `gpus=[]`. Assert return value is
  `None` with no exception raised. Green pre-fix; guards the empty-list edge.

- [ ] `test_zero_device_id_does_not_bind_warp` — **WARP-sentinel guard.** Real
  mock SD shapes: GPUs `[WARP Rasterizer vendor=9 deviceID=0,
  NVIDIA RTX 4500 Ada Generation vendor=6 deviceID=10161]`; canonical
  `Internal::Driver Initialisation Parameters` → InitParams → AdapterDesc with
  `Description="NVIDIA RTX 4500 Ada Generation"` and `DeviceId=0`. Assert the
  NVIDIA GPU is returned (NOT WARP): a present-but-zero `DeviceId` is the
  software/WARP sentinel and must fall through tier-1 to name-substring, which
  resolves NVIDIA. Pins the FIX-1 truthiness gate + `deviceID == 0` candidate
  skip so a real non-zero id can never coincidentally bind the WARP adapter.
