## ADDED Requirements

### Requirement: Environment bootstrap commands
The CLI MUST provide baseline environment and capture bootstrap commands for Phase 0.

#### Scenario: Doctor provides baseline checks
- **WHEN** the user runs `rdc doctor`
- **THEN** the CLI reports python, platform, renderdoc module, replay API surface, and renderdoccmd checks
- **AND** exits with code `1` if any critical check fails

#### Scenario: Capture API discovery
- **WHEN** the user runs `rdc capture --list-apis`
- **THEN** the CLI calls `renderdoccmd capture --list-apis`
- **AND** returns the underlying command exit code
