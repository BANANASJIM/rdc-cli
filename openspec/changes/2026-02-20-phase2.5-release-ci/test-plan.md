# Test Plan: Release CI Pipeline

## Scope

### In scope
- CI YAML structure and job dependencies
- Tag trigger configuration
- Tag-version verification logic
- PyPI publish action configuration (OIDC permissions)
- GitHub Release action configuration

### Out of scope
- Actual PyPI publishing (requires trusted publisher setup on pypi.org)
- Actual tag creation (done in #80)
- Build validation details (already covered in #73/#76)

## Test Matrix

| Layer | Target | Method |
|-------|--------|--------|
| Static | YAML syntax | CI runs on PR |
| Static | Job dependency graph | Review: release needs [lint, typecheck, test, build] |
| Static | Tag-version check script | Review: bash script compares GITHUB_REF_NAME vs tomllib |
| Integration | Build job artifacts | PR CI runs build job |

## Cases

1. PR push → build job runs, release job skipped (no tag)
2. Tag push `v0.2.0` with matching pyproject.toml → all jobs run → release publishes
3. Tag push `v0.3.0` with mismatched pyproject.toml → release fails at verify step

## Assertions

- `build` job uploads `dist/` artifact
- `release` job has `id-token: write` permission (required for OIDC)
- `release` job has `contents: write` permission (required for GitHub Release)
- Tag-version script: strips `v` prefix, compares against tomllib-parsed version

## Risks

- PyPI trusted publisher must be configured on pypi.org before first release
- `tomllib` requires Python 3.11+ on CI runner (Ubuntu latest has 3.12+)
