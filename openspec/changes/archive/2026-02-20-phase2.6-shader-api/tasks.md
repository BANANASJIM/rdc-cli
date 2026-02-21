# Tasks — Phase 2.6 Shader API Fixes

- [x] Write test file `tests/unit/test_daemon_shader_api_fix.py`
- [x] Fix `shader_source` handler in `daemon_server.py` (Issue 4)
- [x] Fix `shader_disasm` handler in `daemon_server.py` (Issue 4)
- [x] Add `/shaders` cache-build guard in `_handle_vfs_ls` (Issue 5)
- [x] Add `/shaders` cache-build guard in `_handle_vfs_tree` (Issue 5)
- [x] Add `_collect_pass_draw_eids` helper to `query_service.py` (Issue 5b)
- [x] Populate `/passes/*/draws` in `build_vfs_skeleton` (Issue 5b)
- [x] `pixi run check` passes (lint + typecheck + test)
