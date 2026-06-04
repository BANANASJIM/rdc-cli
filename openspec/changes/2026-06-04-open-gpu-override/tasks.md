# Tasks: Add `--gpu` override to `rdc open`

- [x] `daemon_server.py`: add `_resolve_gpu_pref()` (index / deviceID / name substring)
- [x] `daemon_server.py`: add `pref` param to `_match_capture_gpu()`; short-circuit before auto-match, warn + fall back when no match
- [x] `daemon_server.py`: `--gpu` arg, `DaemonState.gpu_pref`, pass `state.gpu_pref` at local + remote call sites
- [x] `services/session_service.py`: `start_daemon(gpu=...)` appends `--gpu`; forward through `open_session` / `listen_open_session`
- [x] `commands/session.py`: `--gpu` option on `open_cmd`; warn-and-ignore with `--connect`; pass to open paths
- [x] `openspec/specs/daemon/spec.md`: apply Spec Delta to the "Multi-GPU capture replay" scenario (user `--gpu` precedence + unresolved fallback)
- [x] Unit tests: `_resolve_gpu_pref` forms; `_match_capture_gpu` pref precedence + no-match fallback warning; `start_daemon` argv; CLI passthrough + `--connect` warning
- [x] Update existing fakes broken by new signature/attr (`test_remote_replay_passes_sd` spy, sigterm-handler `mock_args`)
- [x] `pixi run check` green (lint + typecheck + tests)
- [ ] Fresh review of the diff
- [ ] Open PR targeting `master`
- [ ] Archive this OpenSpec folder after merge
