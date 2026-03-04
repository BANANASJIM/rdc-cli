# W6: Test Plan

## BUG-2: Relative path resolution

- [ ] Unit: `test_capture_core.py` — mock `ExecuteAndInject`, pass relative path, assert resolved absolute path is forwarded
- [ ] Manual (Windows VM): `rdc capture -o out.rdc -- .local/vulkan-samples/vulkan_samples.exe` no longer returns "Failed to launch process"

## BUG-1: MSYS path recovery

- [ ] Unit: `_recover_msys_path("C:/Program Files/Git/info")` returns `/info`
- [ ] Unit: `_recover_msys_path("C:/Program Files/Git")` returns `/`
- [ ] Unit: `_recover_msys_path("/info")` returns `/info` (passthrough)
- [ ] Unit: `_recover_msys_path("C:/Users/Jim/file.txt")` returns unchanged (not MSYS)
- [ ] Manual (Git Bash): `rdc ls /`, `rdc cat /info`, `rdc tree /` work without `MSYS_NO_PATHCONV=1`

## BUG-4: pytest tmp_path

- [ ] Manual (Windows VM): `pixi run test` — zero PermissionError on tmp_path

## BUG-3: Diagnostic logging

- [ ] Unit: verify `run_target_control_loop` runs without error (existing tests still pass)
- [ ] Manual (Windows VM): `rdc capture` with `--verbose` shows message types in debug output
