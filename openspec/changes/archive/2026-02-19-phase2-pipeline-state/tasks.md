# Tasks: phase2-pipeline-state

> **Merge order**: This branch merges FIRST. OpenSpec #2 (buffer-decode) rebases on top.
> Shared types (VertexInputAttribute, BoundVBuffer, BoundIBuffer, GetVertexInputs,
> GetVBuffers, GetIBuffer) are owned by this branch.

## Phase A: Mock API additions (tests first)

- [ ] Update existing MockPipeState methods: GetViewport (add minDepth/maxDepth), GetScissor (add enabled field)
- [ ] Add new PipeState methods to MockPipeState: GetColorBlends, GetStencilFaces, GetVertexInputs, GetSamplers, GetVBuffers, GetIBuffer
- [ ] Add helper structs to mock_renderdoc.py: ColorBlend, BlendEquation, StencilFace, SamplerData, BoundVBuffer, BoundIBuffer, VertexInputAttribute
- [ ] Add Topology enum to mock_renderdoc.py (if not already present as string)
- [ ] Add GetPostVSData to MockReplayController + MeshFormat struct
- [ ] Add struct/enum pairs to test_mock_api_sync.py
- [ ] Verify mock API sync passes

## Phase B: VFS routes + tree cache

- [ ] Add 10 new routes to router.py (topology, viewport, scissor, blend, stencil, vertex-inputs, samplers, vbuffers, ibuffer, postvs)
- [ ] Add route resolution tests to test_vfs_router.py
- [ ] Update tree_cache.py: add pipeline child nodes (topology, viewport, scissor, blend, stencil, vertex-inputs, samplers, vbuffers, ibuffer) + postvs
- [ ] Add tree cache tests

## Phase C: Daemon handlers (tests first)

- [ ] Write test_pipeline_state.py with mock DaemonState (all 10 handlers)
- [ ] Implement pipe_topology handler
- [ ] Implement pipe_viewport handler
- [ ] Implement pipe_scissor handler
- [ ] Implement pipe_blend handler
- [ ] Implement pipe_stencil handler
- [ ] Implement pipe_vinputs handler
- [ ] Implement pipe_samplers handler
- [ ] Implement pipe_vbuffers handler
- [ ] Implement pipe_ibuffer handler
- [ ] Implement postvs handler (metadata-only first, full vertex decode later)
- [ ] Verify all handler tests pass
- [ ] Add `rdc cat /draws/<eid>/pipeline/<sub>` integration test

## Phase D: Integration + verification

- [ ] Run `pixi run lint && pixi run test` — all pass
- [ ] Run GPU tests against real capture
- [ ] Code review
