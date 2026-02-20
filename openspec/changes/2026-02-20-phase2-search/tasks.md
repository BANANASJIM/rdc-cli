# Tasks: phase2-search

## Phase A: Mock + disassembly cache infrastructure

- [ ] Add `DisassembleShader(pipeline, refl, target)` to MockPipeState/MockReplayController
- [ ] Add `GetDisassemblyTargets(withPipeline)` to MockReplayController
- [ ] Add `disasm_cache` field to DaemonState
- [ ] Write `_build_disasm_cache(state)` helper in daemon_server.py
- [ ] Test: cache builds correctly from mock shaders, returns expected text
- [ ] Test: second call returns same cache (no rebuild)

## Phase B: `search` daemon handler

- [ ] Write `search` handler in `_handle_request`
- [ ] Support params: pattern, stage, case_sensitive, limit, context
- [ ] Test: basic pattern match returns correct fields
- [ ] Test: case-insensitive (default) and case-sensitive modes
- [ ] Test: stage filter
- [ ] Test: limit + truncated flag
- [ ] Test: context lines (before/after)
- [ ] Test: invalid regex → error -32602
- [ ] Test: no adapter → error -32002
- [ ] Test: no matches → empty list

## Phase C: VFS `/shaders/` namespace

- [ ] Update `build_vfs_skeleton` to populate `/shaders/<id>/` nodes
- [ ] Add `/shaders/<id>/info` and `/shaders/<id>/disasm` to tree_cache
- [ ] Add VFS routes in router.py for `/shaders/` paths
- [ ] Wire `vfs_cat /shaders/<id>/disasm` to disasm cache or on-demand disassembly
- [ ] Wire `vfs_cat /shaders/<id>/info` to shader metadata
- [ ] Test: `/shaders/` lists all unique shader IDs
- [ ] Test: `/shaders/<id>/info` returns correct data
- [ ] Test: `/shaders/<id>/disasm` returns disassembly text
- [ ] Test: VFS route resolution for shader paths

## Phase D: CLI `rdc search` command

- [ ] Add `search.py` in `src/rdc/commands/`
- [ ] Register in CLI group
- [ ] TSV output: SHADER, STAGE, EID, LINE, TEXT columns
- [ ] Support `--stage`, `--target`, `-i/--case-sensitive`, `--limit`, `-C/--context`
- [ ] Test: CliRunner happy path output
- [ ] Test: no matches message

## Phase E: Integration + lint

- [ ] `pixi run check` passes (lint + mypy + pytest)
- [ ] Verify mock API sync test includes new mock methods
- [ ] Update test_mock_api_sync struct pairs if needed
