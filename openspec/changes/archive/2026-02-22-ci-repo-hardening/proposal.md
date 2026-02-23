# Proposal: ci-repo-hardening

## Goal

Fix all repository and CI hygiene issues found in the Feb 2026 audit: supply-chain security
(SHA-pinned actions), legal compliance (LICENSE file), gitignore gaps, Dependabot, CI
performance, and stale README stats.

## Scope

- **P0-SEC-2**: Pin all `uses:` directives in `ci.yml` and `commitlint.yml` to immutable
  commit SHAs with an inline version comment. Actions affected:
  - `actions/checkout@v4` → `11bd71901bbe5b1630ceea73d27597364c9af683`
  - `astral-sh/setup-uv@v4` → `0c5e2b8115b621ce0f33d5a680e4b55c186dfada`
  - `actions/upload-artifact@v4` → `4cec3d8aa04e39d1a68397de0c4cd6fb9dce8ec1`
  - `actions/download-artifact@v4` → `d3f86a106a0bac45b974a628896c90dbdf5c8093`
  - `pypa/gh-action-pypi-publish@release/v1` → `76f52bc884231f62b54a4f72f37000484c4a47b2`
  - `softprops/action-gh-release@v2` → `c95fe1489396fe8a9eb87c0abf8aa5b2ef267fce`
  - `wagoid/commitlint-github-action@v6` → `a6e35e22f4c53a4aa4e16d1e87f2c7b87e5a7a5b`
- **P0-LEGAL-1**: Add `LICENSE` (standard MIT, copyright Jim Z, 2024-2026).
- **P1-REPO-1**: Add `.claude/`, `docs/`, and `scripts/*.py` to `.gitignore`.
- **P1-CI-1**: Add `.github/dependabot.yml` (GitHub Actions + pip, weekly). Add `pip-audit`
  job to `ci.yml` that runs `uvx pip-audit` against the installed environment.
- **P2-CI-1**: Add `concurrency` group to both workflow files (cancel in-progress on same
  ref). Add `enable-cache: true` to every `setup-uv` step.
- **P2-REPO-1**: Update README.md line 13 (`33 commands` → `54 commands`) and line 98
  (`653 tests, 92% coverage` → `1609 tests, 95.29% coverage`).
- **P2-REPO-2**: Add `SECURITY.md` (minimal: supported versions + private disclosure via
  GitHub Security Advisories). Add `.github/CODEOWNERS` (single rule: `* @BANANASJIM`).

## Non-goals

- No changes to `src/` or `tests/`.
- No new CI jobs beyond `pip-audit`.
- No changelog entry or version bump.
- Not switching to a different CI platform.
