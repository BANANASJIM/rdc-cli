## ADDED Requirements

### Requirement: Fixture and docker tooling
The project MUST include tooling for fixture capture and reproducible Linux build environment.

#### Scenario: Fixture helper script exists
- **WHEN** a developer needs a capture fixture
- **THEN** they can run a helper script that wraps `renderdoccmd capture`

#### Scenario: Docker dev image exists
- **WHEN** a developer needs clean Linux setup
- **THEN** project provides Dockerfile with Python and uv toolchain
