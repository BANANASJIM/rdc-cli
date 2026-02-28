# Phase R2: Tasks

## R2.1 Shared `make_daemon_state()` builder [1.5h]

- [ ] Add `make_daemon_state()` to `tests/unit/conftest.py` with signature:
  `make_daemon_state(ctrl=None, *, capture="test.rdc", eid=0, token="tok", api_name=None, max_eid=None, rd_mod=None, **kwargs) -> DaemonState`
  `**kwargs` forwards to DaemonState for uncommon fields (structured_file, vfs_tree, disasm_cache, built_shaders, is_remote, etc.)
- [ ] Replace `_make_state()` in `tests/unit/test_capturefile_handlers.py` — note: uses `SimpleNamespace`, not `DaemonState`; skip or adapt separately
- [ ] Replace `_make_state()` in `tests/unit/test_vfs_daemon.py`
- [ ] Replace `_make_state()` in `tests/unit/test_draws_daemon.py`
- [ ] Replace `_make_state()` in `tests/unit/test_fix1_draws_pass_name.py`
- [ ] Replace `_make_state()` in `tests/unit/test_daemon_pipeline_extended.py`
- [ ] Replace `_make_state()` in `tests/unit/test_tex_stats_handler.py`
- [ ] Replace `_make_state()` in `tests/unit/test_handlers_remote.py`
- [ ] Replace `_make_state()` in `tests/unit/test_script_handler.py`
- [ ] Replace `_make_state()` in `tests/unit/test_pipeline_section_routing.py`
- [ ] Replace `_make_state()` in `tests/unit/test_draws_events_daemon.py`
- [ ] Replace `_make_state()` in `tests/unit/test_daemon_output_quality.py`
- [ ] Replace `_make_state()` in `tests/unit/test_pixel_history_daemon.py`
- [ ] Replace `_make_state()` in `tests/unit/test_pipeline_daemon.py`
- [ ] Replace `_make_state()` in `tests/unit/test_pick_pixel_daemon.py`
- [ ] Replace `_make_state()` in `tests/unit/test_debug_handlers.py`
- [ ] Replace `_make_state()` in `tests/unit/test_shader_edit_handlers.py`
- [ ] Replace `_make_state_with_temp()` in `tests/unit/test_binary_daemon.py`
- [ ] Replace `_make_state_with_pipe()` in `tests/unit/test_descriptors_daemon.py`
- [ ] Replace `_make_state_with_*()` variants in `tests/unit/test_daemon_shader_api_fix.py` (3 variants: _ps, _cbuffer, _vfs)
- [ ] Verify `test_daemon_handlers_real.py` is untouched (different pattern — real adapter)

## R2.2 CLI monkeypatch helper [1h]

- [ ] Add `mock_cli_session()` fixture to `tests/unit/conftest.py` that patches
  `rdc.commands._helpers.load_session` and `rdc.commands._helpers.send_request`
  and accepts a `response` dict; returns a `CliRunner` instance
- [ ] Replace local `_patch()` helpers in:
  - `tests/unit/test_capturefile_commands.py`
  - `tests/unit/test_info_commands.py`
  - `tests/unit/test_pipeline_commands.py`
  - `tests/unit/test_pipeline_cli_phase27.py`
  - `tests/unit/test_resources_commands.py`
  - `tests/unit/test_resources_filter.py`
  - `tests/unit/test_search.py`
  - `tests/unit/test_unix_helpers_commands.py`
- [ ] Update string-based monkeypatches in:
  - `tests/unit/test_draws_events_cli.py`
  - `tests/unit/test_pixel_history_commands.py`
  - `tests/unit/test_snapshot_command.py`

## R2.3 Output assertion helpers [0.5h]

- [ ] Add `assert_json_output(result, *, exit_code=0)` to `tests/unit/conftest.py`:
  parses result.output as JSON, asserts exit_code, returns parsed dict
- [ ] Add `assert_jsonl_output(result, *, exit_code=0)` to `tests/unit/conftest.py`:
  splits lines, parses each as JSON, asserts exit_code, returns list of dicts
- [ ] Add `assert_tsv_output(result, *, exit_code=0, has_header=True)` to `tests/unit/conftest.py`:
  splits lines, validates tab-separated structure, returns list of rows
- [ ] Add `assert_quiet_output(result, *, exit_code=0)` to `tests/unit/conftest.py`:
  asserts exit_code and output is empty or whitespace-only
- [ ] Replace ad-hoc inline JSON parse + exit_code assertions in at least 5 test files
  to validate the helpers work; no requirement to replace all instances

## Validation [0.25h]

- [ ] `pixi run lint` — zero new warnings
- [ ] `pixi run test` — no regressions, coverage unchanged
