# Tasks: ci-repo-hardening

## Test-first tasks

- [ ] Write a shell/CI validation script (or manual checklist) asserting no mutable `@vN` tags remain in workflow files after pinning.

## Implementation tasks

### P0 — Critical

- [ ] **P0-SEC-2** Pin `ci.yml`: replace all 7 mutable action tags with SHA + inline comment.
  - `actions/checkout@v4` → `@11bd71901bbe5b1630ceea73d27597364c9af683 # v4`  (5 occurrences: lint, typecheck, test, build-and-verify, release)
  - `astral-sh/setup-uv@v4` → `@0c5e2b8115b621ce0f33d5a680e4b55c186dfada # v4`  (4 occurrences)
  - `actions/upload-artifact@v4` → `@4cec3d8aa04e39d1a68397de0c4cd6fb9dce8ec1 # v4`  (1 occurrence)
  - `actions/download-artifact@v4` → `@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4`  (1 occurrence)
  - `pypa/gh-action-pypi-publish@release/v1` → `@76f52bc884231f62b54a4f72f37000484c4a47b2 # release/v1`  (highest risk — id-token: write)
  - `softprops/action-gh-release@v2` → `@c95fe1489396fe8a9eb87c0abf8aa5b2ef267fce # v2`
- [ ] **P0-SEC-2** Pin `commitlint.yml`: replace 2 mutable tags.
  - `actions/checkout@v4` → `@11bd71901bbe5b1630ceea73d27597364c9af683 # v4`
  - `wagoid/commitlint-github-action@v6` → `@a6e35e22f4c53a4aa4e16d1e87f2c7b87e5a7a5b # v6`
- [ ] **P0-LEGAL-1** Create `LICENSE` — standard MIT text, `Copyright (c) 2024-present Jim Z`.

### P1 — High

- [ ] **P1-REPO-1** Append to `.gitignore`:
  ```
  .claude/
  docs/
  scripts/*.py
  ```
- [ ] **P1-CI-1** Create `.github/dependabot.yml` with `package-ecosystem: "github-actions"`, `directory: "/"`, `schedule: weekly`.
- [ ] **P1-CI-1** Add `pip-audit` job to `ci.yml` after the `test` job:
  - `needs: [test]`
  - single step: `uvx pip-audit`

### P2 — Medium

- [ ] **P2-CI-1** Add `concurrency` block to `ci.yml` (top-level, group by `github.ref`, `cancel-in-progress: true`).
- [ ] **P2-CI-1** Add `concurrency` block to `commitlint.yml` (same pattern).
- [ ] **P2-CI-1** Add `enable-cache: true` to every `astral-sh/setup-uv` step in `ci.yml` (4 occurrences).
- [ ] **P2-REPO-1** Update `README.md`:
  - Line 13: `33 commands` → `54 commands`
  - Line 98: `653 tests, 92% coverage` → `1609 tests, 95.29% coverage`
- [ ] **P2-REPO-2** Create `SECURITY.md` — supported versions table + "report via GitHub Security Advisories" instruction.
- [ ] **P2-REPO-2** Create `.github/CODEOWNERS` — single line: `* @BANANASJIM`.
