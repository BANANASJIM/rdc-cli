# Phase 2.5 OpenSpec #3: Release CI Pipeline

## Summary

Add CI jobs for building wheel/sdist artifacts on every PR and publishing
to PyPI + GitHub Releases on tag push.

## Motivation

- Need automated release pipeline: `git tag v0.2.0 && git push --tags`
  should build, verify, and publish without manual intervention
- Trusted Publisher (OIDC) eliminates stored API tokens

## Design

### Build job (every PR + push)
- `uv build` → wheel + sdist
- `twine check` for metadata validation
- `check-wheel-contents` for completeness
- Artifacts uploaded for downstream jobs

### Release job (tag push only)
- Gated by `if: startsWith(github.ref, 'refs/tags/v')`
- Depends on all CI jobs passing (lint, typecheck, test, build)
- Verifies tag version matches pyproject.toml version
- Publishes to PyPI via trusted publisher OIDC
- Creates GitHub Release with dist artifacts and auto-generated notes

## Files Changed

- `.github/workflows/ci.yml` — add `build` and `release` jobs, tag trigger
