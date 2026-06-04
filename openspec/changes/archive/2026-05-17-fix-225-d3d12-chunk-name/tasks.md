# Fix #225 (fix-forward): Tasks

- [ ] Opus review of `proposal.md` and `test-plan.md`; revise as needed
- [ ] `daemon_server.py`: add `"Driver Initialisation Parameters"` to `d3d_markers` (keep existing three entries)
- [ ] `daemon_server.py`: rewrite `_find_adapter_description` with bounded recursive descent (depth ≤ 5); return `(description, device_id)` named tuple (`VendorId` deliberately not parsed)
- [ ] `daemon_server.py`: update `_match_capture_gpu` selection logic — exact `DeviceId` match primary (with `0` treated as software/WARP sentinel: tier-1 gated on truthiness and `deviceID == 0` candidates skipped), name-substring secondary, vendor-priority tertiary
- [ ] `daemon_server.py`: add FIX-3 diagnostic `_log.warning` for chunk-name version drift (multi-GPU + sd present + no recognized vk/d3d marker chunk seen)
- [ ] `openspec/specs/daemon/spec.md`: apply Spec Delta from `proposal.md` to the "Multi-GPU capture replay" scenario
- [ ] `tests/unit/test_daemon_server_unit.py`: implement all 14 test cases from `test-plan.md` (5 red-first defect proofs + 9 regression guards, incl. the WARP-sentinel guard); confirm each red-first test fails against current `daemon_server.py` BEFORE editing source; the existing `_gpu` helper hardcodes `deviceID=0`, so DeviceId tests must build GPUs with explicit distinct `deviceID` values
- [ ] `pixi run lint && pixi run test` passes
- [ ] Fresh Opus review of implementation diff
- [ ] Adversarial review: walk the real canonical dump tree by hand against the new code path; confirm guard fires on `"Internal::Driver Initialisation Parameters"` and `DeviceId=10161` selects NVIDIA
- [ ] Base/target branch is `master` — verified, not assumed: `git -C <repo> symbolic-ref refs/remotes/origin/HEAD` resolves to `refs/remotes/origin/master`, and `git remote show origin` reports `HEAD branch: master` (rdc-cli project convention). Branch off `master`; do not assume `main`
- [ ] Open PR targeting `master`; tag @YunHsiao for hardware re-verification
