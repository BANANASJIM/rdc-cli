# Tasks: AUR Deploy Action Pin v4.1.1 → v4.1.3

- [ ] Opus review of `proposal.md` and `test-plan.md`; revise as needed
- [ ] `.github/workflows/aur.yml` line 25: bump action pin from `2ac5a4c1d7035885d46b10e3193393be8460b6f1 # v4.1.1` to `da03e160361ce01bf087e790b6ffd196d7dccff7 # v4.1.3`
- [ ] `.github/workflows/aur.yml` line 72: same pin bump (job `aur-stable`)
- [ ] Static checks: grep confirms new SHA appears exactly twice, old SHA absent, both jobs retain `force_push: true` and `post_process: git checkout -B master`, YAML parses cleanly
- [ ] Fresh review of the two-line diff
- [ ] Open PR targeting `master`
- [ ] After merge: trigger `AUR Publish` via `workflow_dispatch` with `version=0.5.5`
- [ ] Verify job `Publish rdc-cli (stable)` succeeds (no `bash: --command` crash)
- [ ] Verify AUR `rdc-cli` package shows `pkgver=0.5.5`
- [ ] Archive this OpenSpec folder
