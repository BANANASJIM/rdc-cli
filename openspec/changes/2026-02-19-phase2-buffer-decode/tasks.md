# Tasks: phase2-buffer-decode

> **Merge order**: This branch rebases on #3 (pipeline-state) AFTER it merges.
> Shared types (VertexInputAttribute, BoundVBuffer, BoundIBuffer, GetVertexInputs,
> GetVBuffers, GetIBuffer) are owned by #3. This branch adds only buffer-decode
> specific types (ShaderVariable, GetCBufferVariableContents).

## Phase A: Mock API additions (tests first)

- [ ] Add ShaderVariable dataclass to mock_renderdoc.py (name, type, rows, columns, value, members)
- [ ] Add GetCBufferVariableContents to MockReplayController
- [ ] Add struct pairs to test_mock_api_sync.py (ShaderVariable)
- [ ] Verify mock API sync passes

## Phase B: VFS routes + tree cache

- [ ] Add routes to router.py: `/draws/<eid>/cbuffer`, `/draws/<eid>/cbuffer/<set>/<binding>`, `/draws/<eid>/vbuffer`, `/draws/<eid>/ibuffer`
- [ ] Add route resolution tests to test_vfs_router.py
- [ ] Update tree_cache.py: add cbuffer/vbuffer/ibuffer nodes to draw subtree
- [ ] Add tree cache tests to test_vfs_tree_cache.py

## Phase C: Daemon handlers (tests first)

- [ ] Write test_buffer_decode.py with mock DaemonState
- [ ] Implement cbuffer_decode handler: GetCBufferVariableContents → TSV
- [ ] Implement vbuffer_decode handler: GetVBuffers + GetBufferData + IA decode → TSV
- [ ] Implement ibuffer_decode handler: GetIBuffer + GetBufferData → TSV
- [ ] Verify all handler tests pass

## Phase D: CLI commands

- [ ] Write CLI test: test_cli_buffer_decode.py
- [ ] Implement `rdc cbuffer` command (thin VFS wrapper)
- [ ] Implement `rdc vbuffer` command (thin VFS wrapper)
- [ ] Implement `rdc ibuffer` command (thin VFS wrapper)

## Phase E: Integration + verification

- [ ] Run `pixi run lint && pixi run test` — all pass
- [ ] Run GPU tests against real capture
- [ ] Code review
