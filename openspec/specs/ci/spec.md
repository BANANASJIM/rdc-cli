# ci Specification

## Purpose
TBD - created by archiving change ci-hardening. Update Purpose after archive.
## Requirements
### Requirement: Commit message linting in CI
The repository MUST validate commit messages with Conventional Commits in CI.

#### Scenario: Commitlint workflow runs on PR
- **WHEN** a pull request is opened or updated
- **THEN** CI runs commitlint checks for commit messages
- **AND** non-conforming messages fail the workflow

