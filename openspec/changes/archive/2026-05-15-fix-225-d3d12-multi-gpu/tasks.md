# Fix #225: Tasks

- [ ] `daemon_server.py`: add D3D12 structured-data matching to `_match_capture_gpu` (walk `DriverInit`/`EnumAdapters`/`CreateDXGIFactory` chunks, match `AdapterDesc.Description`/`DeviceName` against `gpu.name`)
- [ ] `daemon_server.py`: add vendor-preference fallback (drop Software/WARP, prefer nVidia > AMD > Intel via `getattr` on `rd.GPUVendor`)
- [ ] `daemon_server.py`: add single-GPU short-circuit at top of `_match_capture_gpu`
- [ ] `daemon_server.py`: add `rd` parameter to `_match_capture_gpu` signature; update both call sites (lines 223 and 368)
- [ ] `daemon_server.py`: pass `sd` at the remote-replay call site (line 368)
- [ ] `openspec/specs/daemon/spec.md`: append "Multi-GPU capture replay" scenario under **Requirement: Replay lifecycle**
- [ ] `tests/unit/test_daemon_server_unit.py`: implement all 8 unit test cases from `test-plan.md`
- [ ] `pixi run lint && pixi run test` passes
