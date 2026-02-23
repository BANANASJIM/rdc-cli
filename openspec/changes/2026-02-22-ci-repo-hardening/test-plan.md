# Test Plan: ci-repo-hardening

## Scope

- In scope: all config-only files — workflow YAMLs, `.gitignore`, `LICENSE`, `README.md`, `SECURITY.md`, `.github/CODEOWNERS`, `.github/dependabot.yml`.
- Out of scope: runtime behaviour of `src/`, unit tests, GPU tests.

## Test Matrix

- Unit: none (no src changes).
- Validation: static file inspection + CI run observation.

## Cases

### P0-SEC-2 SHA pinning
- `ci.yml` contains no mutable tags (`@v4`, `@v2`, `@release/v1`, `@v6`): grep `uses:.*@v` returns 0 matches.
- Every `uses:` line contains a 40-character hex SHA.
- Every SHA line has an inline comment with the human-readable version (e.g., `# v4`).
- `commitlint.yml` same assertions.

### P0-LEGAL-1 LICENSE
- `LICENSE` exists in repo root.
- File contains the string `MIT License`.
- File contains `Copyright`.

### P1-REPO-1 .gitignore additions
- `.gitignore` contains `.claude/`.
- `.gitignore` contains `docs/`.
- `.gitignore` contains `scripts/*.py`.
- After adding entries, `git status` no longer shows `.claude/`, `docs/`, or `scripts/*.py` as untracked.

### P1-CI-1 Dependabot + pip-audit
- `.github/dependabot.yml` exists and contains `package-ecosystem: "github-actions"`.
- `ci.yml` contains a job named `pip-audit` (or similar).
- The `pip-audit` job runs `uvx pip-audit` (or equivalent invocation).
- `pip-audit` job depends on `test` job so it only runs on a clean install.

### P2-CI-1 Concurrency + uv cache
- `ci.yml` top-level or per-job `concurrency:` key is present with `cancel-in-progress: true`.
- `commitlint.yml` `concurrency:` key is present.
- Every `astral-sh/setup-uv` step in `ci.yml` includes `enable-cache: true`.

### P2-REPO-1 README stats
- `README.md` line containing command count reads `54 commands`.
- `README.md` line containing test/coverage stats reads `1609 tests, 95.29% coverage`.

### P2-REPO-2 SECURITY.md + CODEOWNERS
- `SECURITY.md` exists in repo root and contains a vulnerability reporting section.
- `.github/CODEOWNERS` exists and contains `* @BANANASJIM`.
