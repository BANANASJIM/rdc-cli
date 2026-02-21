# Tasks: Release CI Pipeline

- [x] Add `tags: ["v*"]` trigger to CI workflow
- [x] Add `build` job: uv build + twine check + check-wheel-contents + upload artifact
- [x] Add `release` job: tag-version verify + PyPI publish (OIDC) + GitHub Release
- [x] Set correct permissions (id-token: write, contents: write)
- [x] Verify YAML structure and job dependencies
