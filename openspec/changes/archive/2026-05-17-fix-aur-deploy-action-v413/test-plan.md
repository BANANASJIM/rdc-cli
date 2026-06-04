# Test Plan: AUR Deploy Action Pin v4.1.1 → v4.1.3

There are no unit tests for a workflow YAML change. Verification is static
inspection followed by a live workflow run.

## Static verification (pre-merge)

1. **Pin appears exactly twice.** `grep` for
   `da03e160361ce01bf087e790b6ffd196d7dccff7` in
   `.github/workflows/aur.yml` returns exactly 2 lines, one per job.

2. **Old pin is absent.** `grep` for `2ac5a4c1d7035885d46b10e3193393be8460b6f1`
   or `v4.1.1` returns no matches.

3. **Version comment is present on both lines.** Both occurrences of the new SHA
   are followed by the comment `# v4.1.3`.

4. **Preserved inputs — both jobs.** `grep` confirms both jobs retain:
   - `force_push: true`
   - `post_process: git checkout -B master`

5. **YAML parses cleanly.** `python3 -c "import yaml, sys; yaml.safe_load(sys.stdin)"
   < .github/workflows/aur.yml` exits 0. (The repo does not include actionlint or
   yamllint; Python's yaml module is the available static check.)

## Live verification (post-merge)

6. **workflow_dispatch v0.5.5 succeeds.** Trigger `AUR Publish` via
   `workflow_dispatch` with input `version=0.5.5`. Job `Publish rdc-cli (stable)`
   must complete with a green check — specifically, the `entrypoint.sh` crash
   (`bash: --command: invalid option`) must not appear.

7. **AUR package updated.** After the dispatch run, the AUR `rdc-cli` package page
   shows `pkgver=0.5.5`. This is the acceptance gate.
