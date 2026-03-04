# W6: Tasks

- [ ] `capture_core.py`: resolve `app` to absolute path before `ExecuteAndInject`
- [ ] `capture_core.py`: add `logging.debug` to `run_target_control_loop`
- [ ] `commands/vfs.py`: add `_recover_msys_path()` helper + apply to VFS path arguments
- [ ] `pyproject.toml`: add `tmp_path_retention_policy = "none"`
- [ ] `test_capture_core.py`: test relative path is resolved
- [ ] `test_vfs.py` or new: test MSYS path recovery
- [ ] `pixi run lint && pixi run test` passes
