# ci Specification

## Purpose
CI pipeline requirements for code quality, packaging validation, and release automation.
## Requirements
### Requirement: Commit message linting in CI
The repository MUST validate commit messages with Conventional Commits in CI.

#### Scenario: Commitlint workflow runs on PR
- **WHEN** a pull request is opened or updated
- **THEN** CI runs commitlint checks for commit messages
- **AND** non-conforming messages fail the workflow

### Requirement: Multi-version test matrix
CI MUST test against Python 3.10, 3.12, and 3.14 on every PR.

### Requirement: Package build validation
CI MUST build and verify wheel/sdist on every PR (uv build + twine check + install smoke test).

### Requirement: Automated release on tag push
Tag push matching `v*` MUST trigger PyPI publish (trusted publisher OIDC) + GitHub Release creation,
gated by all quality jobs passing.

