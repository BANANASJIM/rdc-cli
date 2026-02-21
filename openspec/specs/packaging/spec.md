# packaging Specification

## Purpose
Distribution and packaging requirements for rdc-cli across PyPI, GitHub Releases, and AUR.

## Requirements

### Requirement: Python version compatibility
rdc-cli MUST support Python >= 3.10. CI validates against 3.10, 3.12, and 3.14.

#### Scenario: Multi-version CI matrix
- **WHEN** a PR is opened or updated
- **THEN** lint, typecheck, and test jobs run on Python 3.10, 3.12, and 3.14
- **AND** all versions must pass before merge

### Requirement: Build validation on every PR
CI MUST validate wheel/sdist artifacts on every PR push.

#### Scenario: Package build and verification
- **WHEN** CI runs the build job
- **THEN** `uv build` produces wheel + sdist
- **AND** `twine check` validates metadata
- **AND** `check-wheel-contents` validates completeness
- **AND** clean install + `rdc --version` + import check pass

### Requirement: Tag-triggered release pipeline
A version tag push MUST trigger automated PyPI + GitHub Release publishing.

#### Scenario: Release on tag push
- **WHEN** a tag matching `v*` is pushed
- **THEN** all CI jobs (lint, typecheck, test, build) must pass first
- **AND** tag version is verified against pyproject.toml
- **AND** wheel + sdist are published to PyPI via trusted publisher OIDC
- **AND** GitHub Release is created with artifacts and auto-generated notes

### Requirement: Shell completion support
`rdc completion [bash|zsh|fish]` MUST generate native shell completion scripts.

#### Scenario: Completion script generation
- **WHEN** `rdc completion zsh` is run
- **THEN** a valid zsh completion script is written to stdout
- **AND** shell auto-detection from `$SHELL` works when no argument is given

### Requirement: Doctor build guidance
`rdc doctor` MUST display actionable renderdoc build instructions when the module is missing.

### Requirement: AUR package
`aur/PKGBUILD` MUST build renderdoc Python module from source (v1.41 pinned) and install rdc-cli with shell completions.

#### Scenario: AUR package build
- **GIVEN** `makepkg -si` in `aur/` directory
- **THEN** renderdoc is built with `-DENABLE_PYRENDERDOC=ON` only (no Qt/GL)
- **AND** LTO flags are stripped (breaks SWIG bindings)
- **AND** renderdoc.so + librenderdoc.so are installed to site-packages
- **AND** shell completions are installed to system paths
- **AND** `rdc doctor` reports all checks passing
