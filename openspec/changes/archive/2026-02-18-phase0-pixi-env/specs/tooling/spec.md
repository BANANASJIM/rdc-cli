## ADDED Requirements

### Requirement: Pixi dev environment
The project MUST provide a pixi environment file for reproducible developer setup.

#### Scenario: Contributor uses pixi tasks
- **WHEN** a contributor runs `pixi run check`
- **THEN** lint, typecheck, and tests run with project-pinned tooling
