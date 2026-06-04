# Fix #225: Test Plan

## Unit tests — `tests/unit/test_daemon_server_unit.py`

- [ ] `test_single_gpu_returns_it` — given `len(gpus) == 1` with any `sd` value
  (including `None`), assert that GPU is returned without inspecting structured data

- [ ] `test_vulkan_match_by_devicename` — regression guard for the existing Vulkan
  path; mock structured data containing a `vkEnumeratePhysicalDevices` chunk with a
  `DeviceName` field matching one of two GPU names; assert the matching GPU is
  returned

- [ ] `test_d3d12_match_via_driverinit_adapterdesc` — mock structured data with a
  `DriverInit` chunk whose `AdapterDesc` child has a `Description` field matching
  one GPU among three (iGPU, discrete, WARP); assert the discrete GPU is returned

- [ ] `test_d3d12_fallback_skips_warp_prefers_nvidia` — no structured-data match;
  three GPUs with vendors Software (WARP), AMD (iGPU), nVidia (discrete); assert
  the nVidia GPU is returned

- [ ] `test_d3d12_fallback_amd_over_intel` — no structured-data match; vendors
  [Intel, AMD, Software]; assert the AMD GPU is returned

- [ ] `test_no_structured_data_uses_fallback_not_gpu0` — `sd=None`; two GPUs in
  order [AMD iGPU, NVIDIA discrete]; assert NVIDIA is returned, reproducing the
  literal issue #225 scenario (iGPU was previously returned as `gpus[0]`)

- [ ] `test_empty_gpu_list_returns_none` — `gpus=[]`; assert return value is `None`
  (no exception raised)

- [ ] `test_remote_replay_passes_sd` — mock the `_match_capture_gpu` call site at
  the remote-replay path (line 368); assert it is invoked with a non-`None` `sd`
  argument when structured data is available
